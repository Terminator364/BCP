package com.blessing.medbrain

import android.app.ActivityManager
import android.content.Context
import dev.ffmpegkit.llama.Llama
import dev.ffmpegkit.llama.LlamaConfig
import dev.ffmpegkit.llama.LlamaModel

data class NeuralRequest(
    val modelPath:String,val modelLength:Long,val modelModified:Long,
    val contextSize:Int,val threads:Int,val prompt:String,
    val systemPrompt:String,val maxTokens:Int
)
data class NeuralResult(
    val text:String,val tokens:Int,val prefillMs:Long,val decodeMs:Long,
    val tokensPerSecond:Float
)
data class BackendCapabilities(
    val tokenDeltas:Boolean,val hardNonThinking:Boolean,val persistentKv:Boolean
){
    val safeStreaming:Boolean get()=tokenDeltas&&hardNonThinking
}
interface InferenceBackend {
    val capabilities:BackendCapabilities
    /**
     * Deltas only when safeStreaming=true. Blocking backends MUST NOT fake progress.
     * A future llama.cpp backend implements token callbacks and hard non-thinking mode.
     */
    fun complete(request:NeuralRequest,onDelta:(String)->Unit):NeuralResult
    fun release()
}
/** Exact existing native vendor, preserved to keep 0.5.0 output parity. */
class BlockingVendorBackend(private val ctx:Context):InferenceBackend {
    override val capabilities=BackendCapabilities(
        tokenDeltas=false,hardNonThinking=false,persistentKv=false)
    private var model:LlamaModel?=null
    private var key=""
    override fun complete(request:NeuralRequest,onDelta:(String)->Unit):NeuralResult{
        val signature=request.modelPath+":"+request.modelLength+":"+
            request.modelModified+":"+request.contextSize+":"+request.threads
        if(model==null||signature!=key){
            val activity=ctx.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
            val memory=ActivityManager.MemoryInfo().also{activity.getMemoryInfo(it)}
            require(!memory.lowMemory){"Mémoire Android insuffisante pour Qwen."}
            release()
            model=Llama.loadModel(request.modelPath,LlamaConfig(
                contextSize=request.contextSize,threads=request.threads,
                gpuLayers=0,temperature=0.15f))
            key=signature
        }
        val result=Llama.complete(requireNotNull(model),
            prompt=request.prompt,systemPrompt=request.systemPrompt,
            maxTokens=request.maxTokens)
        // The vendor returns one finished result and clears KV on every call.
        // Do not invoke onDelta, which would misrepresent synchronous completion.
        return NeuralResult(result.text,result.tokensGenerated,
            result.promptEvalTimeMs,result.generateTimeMs,result.tokensPerSecond)
    }
    override fun release(){
        try{model?.let{Llama.releaseModel(it)}}finally{model=null;key=""}
    }
}
