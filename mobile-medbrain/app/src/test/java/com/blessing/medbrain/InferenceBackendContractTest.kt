package com.blessing.medbrain

import org.junit.Assert.*
import org.junit.Test

class InferenceBackendContractTest{
    @Test fun streamingGateRequiresBothTokenDeltasAndNoThinkingGuarantee(){
        assertFalse(BackendCapabilities(false,false,false).safeStreaming)
        assertFalse(BackendCapabilities(true,false,true).safeStreaming)
        assertFalse(BackendCapabilities(false,true,true).safeStreaming)
        assertTrue(BackendCapabilities(true,true,true).safeStreaming)
    }
    @Test fun requestContainsExplicitBoundedInferenceParameters(){
        val req=NeuralRequest("/data/local/model.gguf",1234L,456L,
            2048,4,"Question clinique","Réponds en français",144)
        assertEquals(144,req.maxTokens)
        assertEquals(2048,req.contextSize)
        assertTrue(req.modelPath.endsWith(".gguf"))
    }
}
