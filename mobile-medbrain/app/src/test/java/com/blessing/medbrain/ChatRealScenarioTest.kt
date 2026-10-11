package com.blessing.medbrain
import org.junit.Assert.*
import org.junit.Test

class ChatRealScenarioTest{
 @Test fun versionQuestionsNeverReadRandomMedicalSources(){
  listOf("tu es quel version ?","tu es quelle version ?","quelle version de MedBrain ?",
    "quel modèle es-tu ?","comment tu fonctionnes ?").forEach{q->
   assertFalse(q,ChatRoutingPolicy.searchDocuments(q,"auto",false))
   val out=ChatRoutingPolicy.quickPersonalResponse(q,"0.5.0",true)
   assertNotNull(q,out);assertTrue(out!!.contains("0.5.0"))
  }
 }
 @Test fun socialDialogueDoesNotRunFts(){
  listOf("salut","hein","tu sais quoi","oft tu sais quoi","ca va","merci",
   "qu'en penses-tu ?","raconte une histoire","j'ai une idée",
   "organisons ma journée","comment tu t'appelles ?").forEach{
    assertFalse(it,ChatRoutingPolicy.searchDocuments(it,"auto",false))
  }
 }
 @Test fun medicalRetrievalRemainsAvailable(){
  listOf("Insuffisance cardiaque","Physiopathologie de l'hémorragie",
   "Biochimie clinique","Causes de la prééclampsie","Mécanisme des anticoagulants",
   "Sémiologie respiratoire","Définition du syndrome néphrotique",
   "Mes livres parlent-ils de l'hypertension ?").forEach{
    assertTrue(it,ChatRoutingPolicy.searchDocuments(it,"auto",false))
  }
 }
 @Test fun explicitModeAndFollowupTakePrecedence(){
  assertFalse(ChatRoutingPolicy.searchDocuments("hemorragie","general",false))
  assertTrue(ChatRoutingPolicy.searchDocuments("quelle version","sources",false))
  assertFalse(ChatRoutingPolicy.searchDocuments("continue donc","auto",true))
 }
 @Test fun longChatUIIsBoundedAndStoredContentUntouched(){
  val full="x".repeat(25000)
  val preview=ChatWindowPolicy.preview(full)
  assertTrue(preview.length<1900)
  assertEquals(25000,full.length)
  assertTrue(preview.contains("Voir le message complet"))
 }
}
