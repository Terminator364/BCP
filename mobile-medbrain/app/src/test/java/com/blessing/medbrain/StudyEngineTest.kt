package com.blessing.medbrain

import org.junit.Assert.*
import org.junit.Test

class StudyEngineTest {
    @Test fun quickEvidenceIsGroundedInActualPages(){
        val p=Passage("Cardiologie",18,"Le coeur assure la perfusion systémique.","TEXT")
        val text=StudyEngine.quickEvidence("physiologie cardiaque",listOf(p))
        org.junit.Assert.assertTrue(text.contains("Cardiologie"))
        org.junit.Assert.assertTrue(text.contains("p. 18"))
        org.junit.Assert.assertTrue(text.contains("perfusion systémique"))
    }

    private val evidence = listOf(Passage("Cardiologie Tome I",142,
        "L'examen clinique mesure notamment la fréquence cardiaque et recherche les oedèmes.","TEXT"))
    @Test fun longIndexedPagesCannotStarveStudyInference(){
        val big="Traitement physiologique documenté. ".repeat(200)
        val pages=(1..5).map{Passage("Cardiologie Tome 2",it,big,"TEXT")}
        val prompt=StudyEngine.summaryPrompt("insuffisance cardiaque",pages)
        assertTrue("Study prompt too large: "+prompt.length,prompt.length<1600)
        assertTrue(prompt.contains("p. 1"))
        assertTrue(prompt.contains("p. 2"))
        assertFalse(prompt.contains("p. 5"))
    }
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
