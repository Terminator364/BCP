package com.blessing.medbrain

/**
 * Isolated, request-bound partial output. Only caller-attested safe fragments may
 * reach the UI. The installed synchronous vendor never emits these events.
 */
class SafeStreamBuffer(private val requestId:Int){
    private val recent=StringBuilder()
    private var lastEmit=-1_000L
    fun accept(id:Int,safe:Boolean,delta:String,nowMs:Long):String?{
        if(id!=requestId||!safe||(delta.isEmpty()&&recent.isEmpty()))return null
        recent.append(delta.take(500))
        if(recent.length>2500)recent.delete(0,recent.length-2500)
        if(nowMs-lastEmit<350)return null
        lastEmit=nowMs
        return recent.toString()
    }
}
