package com.blessing.medbrain

/** Explicitly bounded continuation of a locally truncated answer.
 *  No model weights are changed: the next chunk reparses short context.
 */
object AnswerContinuationPolicy {
    data class Plan(val chunkTokens:Int,val maxChunks:Int)
    private val detail=Regex("(?i)\\b(d[eé]tail|approfond|cours|explique|d[eé]velop|complet|longue?|exhaustif|parle.moi|continue)\\b")
    fun plan(question:String,battery:Int):Plan {
        val detailed=detail.containsMatchIn(question)
        return if(detailed && battery>=25)Plan(160,2)
            else Plan(144,1)
    }
    fun isFailure(text:String):Boolean {
        val s=text.trim()
        return s.isBlank()||s==ModelOutputPolicy.NO_FINAL||
            s.startsWith("Inférence indisponible")||
            s.startsWith("Le moteur local n'a pas terminé")||
            s.startsWith("Le moteur local a été interrompu")||
            s.startsWith("Service local indisponible")||
            s.startsWith("Moteur local inaccessible")||
            s.startsWith("Deux tâches déjà en attente")
    }
    fun stripNotice(text:String):String =
        text.removeSuffix(GenerationDiagnostics.TRUNCATED_NOTICE).trimEnd()
    fun isTruncated(text:String):Boolean =
        !isFailure(text) && text.endsWith(GenerationDiagnostics.TRUNCATED_NOTICE)
    fun shouldContinue(answer:String,chunkNumber:Int,plan:Plan):Boolean =
        chunkNumber<plan.maxChunks && isTruncated(answer)
    fun continuationPrompt(originalPrompt:String,part:String):String {
        val clean=stripNotice(part)
        return ("Suite d'une réponse en français. Utilise le contexte factuel ci-dessous; "+
            "aucune citation non fournie. Termine la phrase ou l'étape interrompue. "+
            "Ne répète pas ce qui a déjà été dit.\n"+
            "Demande et références initiales :\n"+originalPrompt.take(610)+"\n"+
            "Texte déjà affiché (fin) :\n"+clean.takeLast(340)+"\n"+
            "Continue directement la réponse, sans introduction ni raisonnement interne. /no_think"
        )
    }
    fun combine(first:String,next:String):String {
        val a=stripNotice(first)
        if(isFailure(next))return a+"\n\n⚠️ La suite automatique a échoué. Le texte ci-dessus reste partiel."
        val b=stripNotice(next)
        if(b.isBlank())return a+GenerationDiagnostics.TRUNCATED_NOTICE
        // Conservatively remove only identical character-level overlap, never invent content.
        val overlap=(minOf(120,a.length,b.length) downTo 18)
            .firstOrNull{a.takeLast(it)==b.take(it)} ?: 0
        val merged=a+"\n"+b.drop(overlap).trimStart()
        return if(isTruncated(next))merged+GenerationDiagnostics.TRUNCATED_NOTICE
            else merged
    }
}
