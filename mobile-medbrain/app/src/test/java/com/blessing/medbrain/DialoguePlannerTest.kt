package com.blessing.medbrain

import org.junit.Assert.*
import org.junit.Test

class DialoguePlannerTest {
    private fun msg(kind:String,body:String)=KnowledgeStore.ChatMessage(1L,kind,body,"",0L)
    private val history=listOf(
        msg("user","Que faire devant un saignement important ?"),
        msg("assistant","1. Évalue la gravité. 2. Exerce une pression directe. 3. Appelle les secours. 4. Évite de manipuler la plaie.")
    )
    @Test fun deicticMessagesDoNotTriggerRandomBookSearch() {
        listOf("donc?","Donc ?","et alors ?","continue","tu t'es arrêté au point 4 continue",
            "parle moi en détail","ensuite ?","et les causes ?").forEach {
            val plan=DialoguePlanner.route(it,history)
            assertTrue("Not a follow-up: "+it,plan.followUp)
            assertNull("Follow-up must not be issued as FTS query: "+it,plan.searchQuery)
        }
    }
    @Test fun medicalTopicStartsNewSearch() {
        val p=DialoguePlanner.route("Quels sont les signes de l'insuffisance cardiaque ?",history)
        assertFalse(p.followUp)
        assertNotNull(p.searchQuery)
    }
    @Test fun continuesPointFourWithoutIrrelevantAnticoagulantCitation() {
        val unrelated=listOf(Passage("ACCIDENTS DES ANTICOAGULANTS",9,"Un autre sujet.","TEXT"))
        val prompt=DialoguePlanner.prompt("tu t'es arrêté au point 4 continue",history,unrelated,"auto")
        assertTrue(prompt.contains("4. Évite de manipuler"))
        assertTrue(prompt.contains("saignement important"))
        assertFalse(prompt.contains("ACCIDENTS DES ANTICOAGULANTS"))
        assertTrue(prompt.length<=1350)
    }
    @Test fun timeoutNotRepeatedAsLastUsefulAnswer() {
        val h=history+msg("assistant","Le moteur local n'a pas terminé en 95 secondes. Il a été relancé sans toucher à tes données.")
        val p=DialoguePlanner.prompt("donc?",h,emptyList(),"auto")
        assertTrue(p.contains("pression directe"))
        assertFalse(p.contains("95 secondes"))
    }
    @Test fun documentTextBoundedEvenWithHugeSources(){
        val long="Cardiologie ".repeat(1200)
        val p=DialoguePlanner.prompt("Explique l'insuffisance cardiaque",history,
            listOf(Passage("Tome 1",14,long,"TEXT"),Passage("Tome 2",41,long,"TEXT")),"sources")
        assertTrue("Prompt too long: "+p.length,p.length<=1380)
        assertTrue(p.contains("p. 14"))
        assertTrue(p.contains("p. 41"))
    }
    @Test fun followupDoesNotInventBookProvenance(){
        assertFalse(DialoguePlanner.fallback(emptyList(),true).contains("anticoagulant",true))
        assertTrue(DialoguePlanner.fallback(emptyList(),true).contains("fil de discussion"))
    }
    @Test fun noPreviousAnswerYieldsClarificationInsteadOfFTS(){
        val p=DialoguePlanner.route("donc?",emptyList())
        assertTrue(p.followUp)
        assertFalse(p.hasHistory)
    }
}
