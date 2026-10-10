package com.blessing.medbrain
import org.junit.Assert.*
import org.junit.Test

class SafeStreamBufferTest{
    @Test fun rejectsWrongRequestOrUnattestedPrivateThinking(){
        val b=SafeStreamBuffer(22)
        assertNull(b.accept(21,true,"wrong conversation",1000))
        assertNull(b.accept(22,false,"model private thoughts",1000))
        assertEquals("Réponse médicale",b.accept(22,true,"Réponse médicale",1000))
    }
    @Test fun limitsRefreshRateAndKeepsRecentContext(){
        val b=SafeStreamBuffer(12)
        assertEquals("Bonjour",b.accept(12,true,"Bonjour",1000))
        assertNull(b.accept(12,true," docteur",1100))
        assertEquals("Bonjour docteur",b.accept(12,true,"",1400).let{it} ?: "")
        val tail=b.accept(12,true,"X".repeat(4500),2000)
        assertNotNull(tail)
        assertTrue(tail!!.length<=2500)
    }
    @Test fun noBufferChangeWhenTokenOriginIsUntrusted(){
        val b=SafeStreamBuffer(3)
        assertNull(b.accept(3,false,"<think>hidden</think>",1000))
        assertEquals("Bonjour",b.accept(3,true,"Bonjour",1400))
    }
}
