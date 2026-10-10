package com.blessing.medbrain

/** Metadata only: never logs patient questions or private text. */
object GenerationDiagnostics {
    const val TRUNCATED_NOTICE="\n\n↪ Cette réponse peut être incomplète : limite de génération atteinte. Demande « continue » pour poursuivre."
    fun likelyTruncated(tokensGenerated:Int,tokenBudget:Int):Boolean =
        tokenBudget>0 && tokensGenerated>=tokenBudget
    fun annotate(answer:String,tokensGenerated:Int,tokenBudget:Int):String {
        if(answer==ModelOutputPolicy.NO_FINAL)return answer
        return if(likelyTruncated(tokensGenerated,tokenBudget))
            answer.trimEnd()+TRUNCATED_NOTICE else answer
    }
    fun summary(tokensGenerated:Int,tokenBudget:Int,promptEvalMs:Long,
                generateMs:Long,tokensPerSecond:Float):String =
        "tokens="+tokensGenerated+"/"+tokenBudget+
        "; prefill_ms="+promptEvalMs.coerceAtLeast(0)+
        "; decode_ms="+generateMs.coerceAtLeast(0)+
        "; tps="+String.format(java.util.Locale.ROOT,"%.1f",tokensPerSecond)+
        "; limit_reached="+likelyTruncated(tokensGenerated,tokenBudget)
}
