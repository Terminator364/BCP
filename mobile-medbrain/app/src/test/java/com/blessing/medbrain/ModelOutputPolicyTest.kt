package com.blessing.medbrain
import org.junit.Assert.*
import org.junit.Test
class ModelOutputPolicyTest {
    @Test fun hidesThinkingAndKeepsFinal(){
        assertEquals("La circulation transporte le sang.",
            ModelOutputPolicy.clean("<think>Internal draft</think>La circulation transporte le sang."))
    }
    @Test fun unfinishedThinkingIsNotAResponse(){
        assertEquals(ModelOutputPolicy.NO_FINAL,
            ModelOutputPolicy.clean("<think>Wait, the user might be a layperson"))
    }
    @Test fun hidesLeakedEnglishPlanning(){
        assertEquals(ModelOutputPolicy.NO_FINAL,
            ModelOutputPolicy.clean("Wait, the user might be a layperson, I should explain this"))
    }
    @Test fun legitimateFrenchTextSurvives(){
        assertEquals("Bonjour !",ModelOutputPolicy.clean("Bonjour !"))
    }
}
