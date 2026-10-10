package com.blessing.medbrain
import org.junit.Assert.*
import org.junit.Test

class ConversationRecoveryPolicyTest {
    private fun msg(id:Long,kind:String,text:String)=
        KnowledgeStore.ChatMessage(id,kind,text,"",id)
    @Test fun allowsRetryOnlyAfterUnansweredUserMessage(){
        val h=listOf(msg(1,"user","Explique l'hémorragie"))
        assertEquals("Explique l'hémorragie",ConversationRecoveryPolicy.pending(h,false)?.body)
        assertNull(ConversationRecoveryPolicy.pending(h,true))
        assertTrue(ConversationRecoveryPolicy.canRetry(h.last(),"Explique l'hémorragie"))
    }
    @Test fun completedConversationHasNoRecovery(){
        val h=listOf(msg(1,"user","Exemple"),msg(2,"assistant","Réponse"))
        assertNull(ConversationRecoveryPolicy.pending(h,false))
    }
    @Test fun interruptedGenerationIsResumedWithoutDuplicatingUserTurn(){
        val h=listOf(msg(1,"assistant","Résumé"),
            msg(2,"user","Continue à partir du point 4"))
        assertTrue(ConversationRecoveryPolicy.canRetry(h.last(),"Continue à partir du point 4"))
        assertFalse(ConversationRecoveryPolicy.canRetry(h.last(),"Autre question"))
    }
    @Test fun emptyHistoryDoesNotExposeFalsePending(){
        assertNull(ConversationRecoveryPolicy.pending(emptyList(),false))
    }
}
