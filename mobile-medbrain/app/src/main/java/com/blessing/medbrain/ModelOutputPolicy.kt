package com.blessing.medbrain

/** Fail closed when Qwen3 returns private thinking without a final answer. */
object ModelOutputPolicy {
    const val NO_FINAL="Le modèle n'a pas fourni de réponse finale. Reformule la question ou essaie le mode rapide."
    fun clean(raw:String):String {
        var out=raw.trim()
        if(out.isEmpty())return NO_FINAL
        out=out.replace(Regex("<think>[\\s\\S]*?</think>",RegexOption.IGNORE_CASE),"").trim()
        if(out.contains("<think>",true))return NO_FINAL
        if(out.contains("</think>",true))out=out.substringAfterLast("</think>").trim()
        out=out.replace(Regex("<\\|(?:im_start|im_end|endoftext|fim_suffix)\\|>"),"").trim()
        if(Regex("(?i)^(first,? i should|wait,? the user|also,? the user|i need to|let me (think|structure)|i should (outline|make sure))").containsMatchIn(out))
            return NO_FINAL
        return out.ifBlank{NO_FINAL}
    }
}
