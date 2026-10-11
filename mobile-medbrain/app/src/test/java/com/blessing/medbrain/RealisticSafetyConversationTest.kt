package com.blessing.medbrain
import org.junit.Assert.*
import org.junit.Test
class RealisticSafetyConversationTest {
 @Test fun realPatientsNeverWaitForSlowModel(){
  val acute=listOf(
    "J'ai une douleur thoracique et je transpire beaucoup",
    "Ma mère a une douleur thoracique et respire mal",
    "Mon enfant ne respire plus",
    "Ma soeur convulse devant moi",
    "Je fais une hémorragie",
    "J'ai soudainement un côté du corps paralysé",
    "Mon père ne répond plus et ne respire pas"
  )
  acute.forEach{assertTrue("Urgent symptom not routed: "+it,ConversationPolicy.isUrgent(it))}
 }
 @Test fun academicClinicalExercisesMustRemainLessons(){
  val academic=listOf(
    "Explique la physiopathologie de l'AVC",
    "Cours d'obstétrique : hémorragie du post-partum",
    "Cas clinique : la patiente a une douleur thoracique",
    "Quelles sont les étiologies d'une convulsion ?",
    "Conduite à tenir en stage devant un traumatisé"
  )
  academic.forEach{assertFalse("Academic case flagged as emergency: "+it,
      ConversationPolicy.isUrgent(it))}
 }
 @Test fun urgentCasesDoNotRequireMedicalBookRetrieval(){
    assertFalse(ChatRoutingPolicy.searchDocuments(
        "Ma mère a une douleur thoracique","general",false))
    assertTrue(ConversationPolicy.firstAid("je saigne").contains("pression directe"))
 }
}