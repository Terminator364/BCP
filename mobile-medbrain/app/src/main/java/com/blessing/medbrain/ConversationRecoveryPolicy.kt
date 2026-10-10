package com.blessing.medbrain

/** Protect a user's last unacknowledged message across Android process death. */
object ConversationRecoveryPolicy {
    fun pending(messages:List<KnowledgeStore.ChatMessage>,currentlyGenerating:Boolean)
        :KnowledgeStore.ChatMessage?{
        if(currentlyGenerating)return null
        val last=messages.lastOrNull() ?: return null
        return last.takeIf{it.kind=="user" && it.body.isNotBlank()}
    }
    fun canRetry(last:KnowledgeStore.ChatMessage?,text:String):Boolean =
        last!=null && last.kind=="user" && last.body==text.trim()
}
