package com.blessing.medbrain
import org.junit.Assert.*
import org.junit.Test
class ConversationScenarioTest {
    @Test fun oneThousandGroundedRoutingScenarios(){
        val subjects=listOf("coeur","rein","poumon","foie","cerveau","artere","rate","estomac","peau","sang")
        val prompts=listOf("Explique le","Décris les fonctions du","Quelles sont les pathologies du","Définis le","Anatomie du","Comment fonctionne le","Pourquoi le","Parle moi du","Physiologie du","Je révise le")
        var verified=0
        for(subject in subjects)for(prefix in prompts)for(variant in 0..9){
            val q="$prefix $subject variante$variant"
            val terms=SearchPolicy.terms(q)
            assertTrue("No concept extracted for $q",terms.contains(subject))
            assertFalse("Wrong emergency flag $q",ConversationPolicy.isUrgent(q))
            verified++
        }
        assertEquals(1000,verified)
    }
    @Test fun greetingsAndMetaQuestionsAreHumanized(){
        listOf("salut","Salut !","Bonjour MedBrain","coucou","Eo","hello").forEach{
            assertTrue("Missed greeting $it",ConversationPolicy.isGreeting(it))
        }
        assertFalse(ConversationPolicy.isGreeting("Salut, explique le cœur"))
        assertTrue(ConversationPolicy.isModelQuestion("Que peux-tu faire ?"))
        assertTrue(ConversationPolicy.modelExplanation(false).contains("GGUF"))
    }
    @Test fun urgentMessagesDoNotWaitForDocumentSearch(){
        assertTrue(ConversationPolicy.isUrgent("Je saigne beaucoup, que faire ?"))
        assertTrue(ConversationPolicy.isUrgent("je saigne que faire ?"))
        assertTrue(ConversationPolicy.isUrgent("Douleur thoracique intense"))
        assertFalse(ConversationPolicy.isUrgent("Conduite à tenir devant un patient qui tousse en stage"))
        assertTrue(ConversationPolicy.firstAid("Je saigne beaucoup").contains("pression directe"))
    }
}
