package com.blessing.medbrain
import org.junit.Assert.*
import org.junit.Test

class NaturalConversationContinuityTest {
 private fun line(id:Long,role:String,body:String)=
    KnowledgeStore.ChatMessage(id,role,body,"",id)
 @Test fun ordinaryMessageIncludesRecentUserPreferences(){
    val history=listOf(
      line(1,"user","Je veux travailler ma cardiologie deux heures chaque matin."),
      line(2,"assistant","Nous pouvons préparer des séances progressives."),
      line(3,"user","Je préfère une formation interactive."),
      line(4,"assistant","Compris : questions ouvertes et cas cliniques.")
    )
    val prompt=DialoguePlanner.prompt("On commence lundi alors ?",history,emptyList(),"general")
    assertTrue("Prior conversation absent: "+prompt,prompt.contains("deux heures"))
    assertTrue(prompt.contains("formation interactive"))
    assertTrue(prompt.contains("On commence lundi"))
 }
 @Test fun newMedicalSubjectMustNotBorrowUnrelatedChatAsEvidence(){
    val history=listOf(
      line(1,"user","Parlons de philosophie."),
      line(2,"assistant","Une introduction à la réflexion éthique.")
    )
    val pdf=listOf(Passage("Cours de cardiologie.pdf",18,
      "Les signes de l'insuffisance cardiaque incluent la dyspnée.","TEXT"))
    val prompt=DialoguePlanner.prompt("Explique l'insuffisance cardiaque",
        history,pdf,"auto")
    assertTrue(prompt.contains("Cours de cardiologie.pdf"))
    assertFalse("Old topic could contaminate citations",prompt.contains("philosophie"))
 }
 @Test fun persistedFailureIsNotAConversationSummary(){
    val h=listOf(line(1,"user","Bonjour"),
       line(2,"assistant","Le modèle neuronal n'a pas produit de réponse fiable."),
       line(3,"user","On continue"))
    val result=DialoguePlanner.prompt("Tu es là ?",h,emptyList(),"general")
    assertFalse(result.contains("Le modèle neuronal n'a pas produit"))
 }
}