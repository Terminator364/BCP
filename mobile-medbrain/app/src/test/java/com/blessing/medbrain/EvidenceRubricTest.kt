package com.blessing.medbrain

import org.junit.Assert.*
import org.junit.Test

class EvidenceRubricTest {
    private val standards=listOf(
        "La dyspnée d'effort traduit une augmentation de la pression veineuse pulmonaire.",
        "La turgescence jugulaire est un signe de congestion systémique.",
        "L'échocardiographie précise la fraction d'éjection ventriculaire."
    )
    @Test fun exactReferencedPhraseCanBeDetectedWithoutClaimingMedicalGrading(){
        val answer=standards[1]+"\n"+standards[2]
        val found=EvidenceRubric.findings(standards,answer)
        assertFalse(found[0].indicative)
        assertTrue(found[1].indicative)
        assertTrue(found[2].indicative)
        val output=EvidenceRubric.compare(standards,answer)
        assertTrue(output.contains("Notions non repérées"))
        assertTrue(output.contains("Notions possiblement évoquées"))
        assertTrue(output.contains("ni une note"))
        assertFalse(output.contains("20/20"))
    }
    @Test fun negatedOrReversedClaimMustNotBeCertifiedCorrect(){
        val wrong="La turgescence jugulaire n'est jamais un signe de congestion systémique."
        val feedback=EvidenceRubric.compare(standards,wrong)
        assertTrue(feedback.contains("négations"))
        assertTrue(feedback.contains("pas validés automatiquement"))
        assertFalse(feedback.contains("correcte ✅"))
    }
    @Test fun incompleteAnswerAndMissingCriteriaRemainExplicit(){
        assertTrue(EvidenceRubric.compare(standards,"").contains("Rédige une réponse"))
        assertEquals(0,EvidenceRubric.findings(standards,"sans réponse")
            .count{it.indicative})
        assertEquals(3,EvidenceRubric.findings(standards,"sans réponse").size)
    }
}
