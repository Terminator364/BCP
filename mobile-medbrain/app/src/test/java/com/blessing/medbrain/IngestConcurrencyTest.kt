package com.blessing.medbrain

import org.junit.Assert.*
import org.junit.Test

class IngestConcurrencyTest {
    @Test fun inferenceClaimsPriorityAcrossNextPdfPage(){
        assertTrue(IngestConcurrency.shouldYield(100L,200L))
        assertTrue(IngestConcurrency.shouldYield(199L,200L))
        assertFalse(IngestConcurrency.shouldYield(200L,200L))
        assertFalse(IngestConcurrency.shouldYield(201L,200L))
        assertFalse(IngestConcurrency.shouldYield(100L,0L))
    }
}
