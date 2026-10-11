package com.blessing.medbrain
import org.junit.Assert.*
import org.junit.Test

class EvidenceQualityReplayTest {
 private val corrupted=Passage("Pharmacologie médicale.pdf",48,
    "cs itubilcurs intibe rapidemernl les eurunes onLrzux GATAA EulEnt.", "OCR")
 private val printed=Passage("Sémiologie médicale.pdf",17,
    "L'insuffisance cardiaque comporte des signes de congestion pulmonaire.", "TEXT")
 @Test fun syntheticTwoHourMedicalAnswersDoNotUseRawUnverifiedOcr(){
    val result=DialoguePlanner.prompt("Explique l'insuffisance cardiaque",
       emptyList(),listOf(corrupted,printed),"auto")
    assertFalse(result.contains("onLrzux"))
    assertTrue(result.contains("congestion pulmonaire"))
    assertTrue(result.contains("Sémiologie médicale"))
 }
 @Test fun medicalStudyPromptFiltersUnverifiedOcrButRetainsRealPdf(){
    val prompt=StudyEngine.summaryPrompt("Insuffisance cardiaque",listOf(corrupted,printed))
    assertFalse(prompt.contains("GATAA"))
    assertTrue(prompt.contains("congestion"))
 }
 @Test fun sourceBrowserStillProvidesTrueOcrProvenance(){
    val source=StudyEngine.references(listOf(corrupted))
    assertTrue(source.contains("Pharmacologie médicale.pdf"))
    assertTrue(source.contains("page 48"))
 }
 @Test fun embeddedEnglishReasoningIsNotDisplayedAsFrenchAnswer(){
    val privateDraft="Sure, I can help. Wait, the user might be a layperson. I should outline the steps first."
    assertEquals(ModelOutputPolicy.NO_FINAL,ModelOutputPolicy.clean(privateDraft))
 }
}