package com.blessing.medbrain

import android.app.ActivityManager
import android.app.Service
import android.content.Intent
import android.os.*
import dev.ffmpegkit.llama.Llama
import dev.ffmpegkit.llama.LlamaConfig
import kotlinx.coroutines.*

/** Separate process: native model crash cannot terminate the main UI and SQLite worker process. */
class InferenceService:Service() {
    companion object { const val REQUEST=51; const val REPLY=52 }
    private val scope=CoroutineScope(SupervisorJob()+Dispatchers.Default)
    private val messenger=Messenger(object:Handler(Looper.getMainLooper()){
        override fun handleMessage(msg:Message) {
            if(msg.what!=REQUEST)return
            val callback=msg.replyTo ?: return
            val prompt=msg.data.getString("prompt").orEmpty().take(8500)
            val instruction=msg.data.getString("instruction").orEmpty().take(1100)
            scope.launch {
                var response=""
                var error=""
                var local:dev.ffmpegkit.llama.LlamaModel?=null
                try {
                    val memory=(getSystemService(ACTIVITY_SERVICE) as ActivityManager).let{
                        ActivityManager.MemoryInfo().also{info->it.getMemoryInfo(info)}
                    }
                    require(!memory.lowMemory){"Mémoire Android insuffisante : modèle suspendu pour protéger le téléphone."}
                    val model=ModelVault.file(this@InferenceService)
                    require(model.exists()){"Importe d'abord ton modèle GGUF."}
                    local=Llama.loadModel(model.absolutePath,LlamaConfig(contextSize=2048,threads=4,gpuLayers=0,temperature=0.2f))
                    val result=Llama.complete(local!!,prompt=prompt,systemPrompt=instruction,maxTokens=420)
                    response=result.text.trim()+"\n\n[Génération locale : "+String.format("%.1f",result.tokensPerSecond)+" tokens/s]"
                } catch(e:Throwable) {
                    error=e.javaClass.simpleName+": "+(e.message?:"inférence indisponible")
                } finally {
                    try{local?.let{Llama.releaseModel(it)}}catch(_:Throwable){}
                }
                val reply=Message.obtain(null,REPLY).apply{
                    data=Bundle().apply{putString("result",response);putString("error",error)}
                }
                try{callback.send(reply)}catch(_:RemoteException){}
            }
        }
    })
    override fun onBind(intent:Intent?):IBinder=messenger.binder
    override fun onDestroy(){scope.cancel();super.onDestroy()}
}
