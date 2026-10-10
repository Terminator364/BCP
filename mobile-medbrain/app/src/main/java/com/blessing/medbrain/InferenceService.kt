package com.blessing.medbrain

import android.app.ActivityManager
import android.app.Service
import android.content.Intent
import android.os.*
import dev.ffmpegkit.llama.Llama
import dev.ffmpegkit.llama.LlamaConfig
import dev.ffmpegkit.llama.LlamaModel
import kotlinx.coroutines.*
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

/** Isolated native inference; keep a single warm GGUF while the Activity is bound. */
class InferenceService:Service() {
    companion object { const val REQUEST=51; const val REPLY=52; const val CANCEL=53 }
    private val scope=CoroutineScope(SupervisorJob()+Dispatchers.IO)
    private val serial=Mutex()
    private var cached:LlamaModel?=null
    private var cacheKey=""
    private val messenger=Messenger(object:Handler(Looper.getMainLooper()){
        override fun handleMessage(msg:Message) {
            if(msg.what==CANCEL){
                // Only the isolated :inference process is terminated; SQLite/UI persist.
                Process.killProcess(Process.myPid());return
            }
            if(msg.what!=REQUEST)return
            val callback=msg.replyTo ?: return
            val prompt=msg.data.getString("prompt").orEmpty().take(6500)
            val instruction=msg.data.getString("instruction").orEmpty().take(1100)
            val requestId=msg.data.getInt("request_id")
            val budget=msg.data.getInt("max_tokens",144).coerceIn(64,280)
            scope.launch {
                var answer=""
                var error=""
                try{
                    serial.withLock {
                        val model=ModelVault.file(this@InferenceService)
                        require(model.exists()){"Importe d'abord un modèle GGUF."}
                        val pref=getSharedPreferences("medbrain",MODE_PRIVATE)
                        val ctx=pref.getInt("context_size",2048).coerceIn(1024,2048)
                        val threads=pref.getInt("cpu_threads",4).coerceIn(2,4)
                        val key=model.absolutePath+":"+model.length()+":"+model.lastModified()+":"+ctx+":"+threads
                        if(cached==null||key!=cacheKey){
                            val memory=(getSystemService(ACTIVITY_SERVICE) as ActivityManager).let{
                                ActivityManager.MemoryInfo().also{info->it.getMemoryInfo(info)}
                            }
                            require(!memory.lowMemory){"Mémoire Android insuffisante pour charger Qwen."}
                            cached?.let{Llama.releaseModel(it)}
                            cached=null
                            cached=Llama.loadModel(model.absolutePath,
                                LlamaConfig(contextSize=ctx,threads=threads,gpuLayers=0,temperature=0.15f))
                            cacheKey=key
                        }
                        val result=Llama.complete(requireNotNull(cached),
                            prompt=prompt+"\n/no_think",
                            systemPrompt=instruction+" Réponds directement en français sans raisonnement interne affiché.",
                            maxTokens=budget)
                        answer=ModelOutputPolicy.clean(result.text)
                    }
                }catch(e:Throwable){error=e.javaClass.simpleName+": "+(e.message?:"inférence indisponible")}
                try{
                    callback.send(Message.obtain(null,REPLY).apply{
                        data=Bundle().apply{
                            putInt("request_id",requestId)
                            putString("result",answer)
                            putString("error",error)
                        }
                    })
                }catch(_:RemoteException){}
            }
        }
    })
    override fun onBind(intent:Intent?):IBinder=messenger.binder
    override fun onDestroy(){
        scope.cancel()
        try{cached?.let{Llama.releaseModel(it)}}catch(_:Throwable){}
        cached=null
        super.onDestroy()
    }
}
