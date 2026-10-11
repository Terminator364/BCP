package com.blessing.medbrain

import org.junit.Assert.*
import org.junit.Test

/**
 * Scripted acceptance by a demanding medical student, not an LLM quality benchmark.
 * These intentionally red regression cases represent real human conversational turns.
 */
class HumanConversationAcceptanceTest {
 private fun msg(n:Long,role:String,body:String)=
   KnowledgeStore.ChatMessage(n,role,body,"",n)

 @Test fun ellipsesAndReformulationsRetainActiveContext(){
   val h=listOf(
     msg(1,"user","Explique l'insuffisance cardiaque"),
     msg(2,"assistant","La congestion se manifeste par une dyspnée."),
   )
   val prompts=listOf(
     "Pourquoi ?",
     "Je n'ai pas compris",
     "Explique-le autrement",
     "Peux tu m'en parler plus en détail ?",
     "Mais chez une femme enceinte ?",
     "Et si c'est un nourrisson ?",
     "Fais une synthèse de ce que tu viens de dire",
     "Ça change quoi chez l'enfant ?",
     "Peux-tu m'expliquer le point 3 ?",
     "Je veux un exemple",
     "À quoi cela sert ?",
     "Comment en tenir compte ?"
   )
   for(q in prompts){
     val r=DialoguePlanner.route(q,h)
     assertTrue("Loses previous topic: $q",r.followUp)
     assertNull("Unrelated FTS triggered: $q",r.searchQuery)
     val p=DialoguePlanner.prompt(q,h,emptyList(),"auto")
     assertTrue("No original topic: $q => $p",p.contains("insuffisance cardiaque"))
     assertTrue("Lost current question: $q",p.contains(q.take(80)))
   }
 }
 @Test fun explicitNewPathologyAlwaysOverridesPreviousMedicalHistory(){
   val h=listOf(msg(1,"user","Explique l'insuffisance cardiaque"),
     msg(2,"assistant","Voici une réponse sur le coeur"))
   val q=listOf(
     "Et pour la pneumonie ?", "Et pour la tuberculose ?",
     "Quelle est la physiopathologie du paludisme ?",
     "Explique la méningite", "Comment diagnostiquer une appendicite ?",
     "Parle moi en détail de la prééclampsie"
   )
   for(message in q) {
     val route=DialoguePlanner.route(message,h)
     assertFalse("Conflated two diseases: $message",route.followUp)
     assertTrue("No independent book query: $message",
       ChatRoutingPolicy.searchDocuments(message,"auto",route.followUp))
   }
 }
 @Test fun medicalTopicSurvivesSocialInterruptionsWithoutBecomingAnAppVersion(){
   val h=listOf(
     msg(1,"user","Explique l'insuffisance cardiaque"),
     msg(2,"assistant","La congestion pulmonaire est un élément important."),
     msg(3,"user","Tu es quelle version ?"),
     msg(4,"assistant","Je suis MedBrain 0.5.1"),
     msg(5,"user","Merci"),
     msg(6,"assistant","Avec plaisir.")
   )
   val prompt=DialoguePlanner.prompt("Et ses complications ?",h,emptyList(),"auto")
   assertTrue("Social meta turn displaced clinical topic: $prompt",
      prompt.contains("insuffisance cardiaque"))
   assertFalse("Mistaken topic from meta: $prompt",
      prompt.contains("Question antérieure : Tu es quelle version"))
 }
 @Test fun socialFillerIsHandledByActualModelWhenAvailable(){
   for(q in listOf("tu sais quoi ?", "oft tu sais quoi", "hein", "donc quoi")){
     assertNull("Robotic canned answer prevents dialogue: $q",
       ChatRoutingPolicy.quickPersonalResponse(q,"0.5.1",true))
     assertFalse(ChatRoutingPolicy.searchDocuments(q,"auto",false))
     assertNotNull("Need offline/no-model fallback: $q",
       ChatRoutingPolicy.quickPersonalResponse(q,"0.5.1",false))
   }
 }
 @Test fun compactPromptStillContainsLastInstructionAfterLengthLimits(){
   val huge="Cardiologie et sémiologie. ".repeat(400)
   val h=listOf(msg(1,"user",huge),msg(2,"assistant",huge))
   val q="Continue directement au point 4, sans répéter."
   val p=DialoguePlanner.prompt(q,h,emptyList(),"auto")
   assertTrue(p.contains("Demande actuelle"))
   assertTrue(p.contains(q))
   assertTrue(p.contains("/no_think"))
   assertTrue(p.length<=1350)
 }
}
