package com.blessing.medbrain
import org.junit.Assert.*
import org.junit.Test

/** A medical student often switches subjects mid-sentence or returns to an old topic. */
class TopicSwitchAcceptanceTest {
 private val history=listOf(
  KnowledgeStore.ChatMessage(1,"user","Explique l'insuffisance cardiaque","",1),
  KnowledgeStore.ChatMessage(2,"assistant","L'insuffisance entraîne une congestion pulmonaire.","",2)
 )
 @Test fun nearIdenticalSentencesAreNotTheSameIntent(){
  val contextual=listOf(
   "Parle-moi du traitement ?", "Peux tu me donner les symptômes ?",
   "Peux-tu m'expliquer le point 3 ?",
   "Mais pour une femme enceinte ?", "Et pour le traitement ?",
   "Et chez les nourrissons ?", "Pourquoi ça arrive dans cette maladie ?")
  val explicit=listOf(
   "Pourquoi l'hémorragie est grave ?", "Peux tu m'expliquer la tuberculose ?",
   "Fais une synthèse de la pneumonie",
   "Et si on parlait de la méningite ?",
   "Et pour le paludisme ?", "Et pour la pneumonie ?",
   "Mais pour la prééclampsie ?")
  contextual.forEach{assertTrue("Lost active context: "+it,
      DialoguePlanner.route(it,history).followUp)}
  explicit.forEach{
   assertFalse("Missed new disease: "+it,DialoguePlanner.route(it,history).followUp)
   assertTrue("No medical retrieval: "+it,
     ChatRoutingPolicy.searchDocuments(it,"auto",false))
  }
 }
 @Test fun lastSubstantiveAnswerSurvivesVersionAndThanks(){
  val h=history+listOf(
    KnowledgeStore.ChatMessage(3,"user","Tu es quelle version ?","",3),
    KnowledgeStore.ChatMessage(4,"assistant","Je suis MedBrain 0.5.1","",4),
    KnowledgeStore.ChatMessage(5,"user","Merci","",5),
    KnowledgeStore.ChatMessage(6,"assistant","Avec plaisir.","",6)
  )
  val prompt=DialoguePlanner.prompt("Et les complications ?",h,emptyList(),"auto")
  assertTrue(prompt.contains("congestion pulmonaire"))
  assertFalse(prompt.contains("Dernière réponse utile (fin) : Avec plaisir"))
  assertTrue(prompt.contains("insuffisance cardiaque"))
 }
}
