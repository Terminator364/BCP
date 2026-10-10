package com.blessing.medbrain
import org.junit.Assert.*
import org.junit.Test
class SearchPolicyTest {
    @Test fun ignoresGreetingAndGenericWords(){ assertTrue(SearchPolicy.terms("Salut !").size==1);assertTrue(SearchPolicy.terms("quel est le").isEmpty()) }
    @Test fun excludesFalseObstetricHits(){
        val q="quelle est la taille du coeur ?"
        val bad=SearchPolicy.score(q,"Questions à choix multiples d'obstétrique.pdf",
            "La taille du sac gestationnel et les bruits du coeur foetal sont recherchés.")
        assertEquals(0.0,bad,0.001)
        val good=SearchPolicy.score(q,"Anatomie cardiovasculaire",
            "La taille du coeur est mesurée en centimètres selon les dimensions anatomiques.")
        assertTrue(good>0)
    }
    @Test fun supportsFrenchHeartSpelling(){
        assertEquals(SearchPolicy.normalized("cœur"),SearchPolicy.normalized("coeur"))
        assertTrue(SearchPolicy.score("taille du coeur","Cardiologie","La taille du cœur varie selon le morphotype.")>0)
    }
}