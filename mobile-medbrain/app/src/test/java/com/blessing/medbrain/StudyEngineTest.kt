package com.blessing.medbrain

import org.junit.Assert.*
import org.junit.Test

class StudyEngineTest {
    private val evidence = listOf(Passage("Cardiologie Tome I",142,
        "L'examen clinique mesure notamment la fréquence cardiaque et recherche les oedèmes.","TEXT"))
    @Test fun realProvenanceInPrompts(){
        val output=StudyEngine.summaryPrompt("insuffisance cardiaque",evidence)
        assertTrue(output.contains("Cardiologie Tome I — page 142 (TEXT)"))
        assertTrue(output.contains("insuffisance cardiaque"))
    }
    @Test fun correctionIncludesOriginalResponse(){
        val output=StudyEngine.correctionPrompt("Quels signes ?","tachycardie",evidence)
        assertTrue(output.contains("tachycardie"))
        assertTrue(output.contains("Cardiologie Tome I"))
    }
}
