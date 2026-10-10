package com.blessing.medbrain

import android.app.Service
import android.content.Intent
import android.os.*
import kotlinx.coroutines.*
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

/** Isolated native inference; keep a single warm GGUF while the Activity is bound. */
class InferenceService:Service() {
    companion object { const val REQUEST=51; const val REPLY=52; const val CANCEL=53; const val PARTIAL=54 }
    private val scope=CoroutineScope(SupervisorJob()+Dispatchers.IO)
    private val serial=Mutex()
    private var backend:InferenceBackend?=null
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
                var metric=""
                try{
                    serial.withLock {
                        val model=ModelVault.file(this@InferenceService)
                        require(model.exists()){"Importe d'abord un modèle GGUF."}
                        val pref=getSharedPreferences("medbrain",MODE_PRIVATE)
                        val ctx=pref.getInt("context_size",2048).coerceIn(1024,2048)
                        val threads=pref.getInt("cpu_threads",4).coerceIn(2,4)
                        val engine=backend ?: BlockingVendorBackend(this@InferenceService)
                            .also{backend=it}
                        val request=NeuralRequest(model.absolutePath,model.length(),
                            model.lastModified(),ctx,threads,prompt+"\n/no_think",
                            instruction+" Réponds directement en français sans raisonnement interne affiché.",budget)
                        val result=engine.complete(request){delta->
                            if(engine.capabilities.safeStreaming && delta.isNotEmpty()){
                                callback.send(Message.obtain(null,PARTIAL).apply{
                                    data=Bundle().apply{
                                        putInt("request_id",requestId)
                                        putBoolean("safe_output",true)
                                        putString("delta",delta.take(500))
                                    }
                                })
                            }
                        }
                        answer=GenerationDiagnostics.annotate(
                            ModelOutputPolicy.clean(result.text),result.tokens,budget)
                        metric=GenerationDiagnostics.summary(result.tokens,budget,
                            result.prefillMs,result.decodeMs,result.tokensPerSecond)
                    }
                }catch(e:Throwable){error=e.javaClass.simpleName+": "+(e.message?:"inférence indisponible")}
                try{
                    callback.send(Message.obtain(null,REPLY).apply{
                        data=Bundle().apply{
                            putInt("request_id",requestId)
                            putString("result",answer)
                            putString("error",error)
                            putString("metric",metric)
                        }
                    })
                }catch(_:RemoteException){}
            }
        }
    })
    override fun onBind(intent:Intent?):IBinder=messenger.binder
    override fun onDestroy(){
        scope.cancel()
        try{backend?.release()}catch(_:Throwable){}
        backend=null
        super.onDestroy()
    }
}
