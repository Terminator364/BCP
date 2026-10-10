package com.blessing.medbrain

import org.junit.Assert.*
import org.junit.Test

class AnswerContinuationPolicyTest {
    @Test fun detailedRequestHasAtMostTwoBoundedChunks() {
        assertEquals(2,AnswerContinuationPolicy.plan("Explique en détail l'insuffisance cardiaque",80).maxChunks)
        assertEquals(1,AnswerContinuationPolicy.plan("Quelle est la fréquence cardiaque normale ?",80).maxChunks)
        assertEquals(1,AnswerContinuationPolicy.plan("Explique le diagnostic",10).maxChunks)
    }
    @Test fun onlyTrueTokenCutoffTriggersContinuation() {
        val p=AnswerContinuationPolicy.Plan(160,2)
        val incomplete=GenerationDiagnostics.annotate("1. Définition 2. Signes",160,160)
        assertTrue(AnswerContinuationPolicy.shouldContinue(incomplete,1,p))
        assertFalse(AnswerContinuationPolicy.shouldContinue(incomplete,2,p))
        assertFalse(AnswerContinuationPolicy.shouldContinue("Réponse terminée.",1,p))
        assertFalse(AnswerContinuationPolicy.shouldContinue(ModelOutputPolicy.NO_FINAL,1,p))
    }
    @Test fun continuationPromptDoesNotExpandUnlimitedContext(){
        val src="Références médicales vérifiées ".repeat(500)
        val p=AnswerContinuationPolicy.continuationPrompt(src,"Symptômes . ".repeat(300))
        assertTrue(p.length<=1550)
        assertTrue(p.contains("Ne répète pas"))
        assertTrue(p.contains("Continue directement"))
    }
    @Test fun combinedTextRemovesCutoffAndPreservesSecondPart(){
        val first="1. Définition clinique."+GenerationDiagnostics.TRUNCATED_NOTICE
        val second="2. Diagnostic puis traitement."
        val result=AnswerContinuationPolicy.combine(first,second)
        assertTrue(result.contains("Définition clinique"))
        assertTrue(result.contains("Diagnostic puis traitement"))
        assertFalse(result.contains("limite de génération"))
    }
    @Test fun twoCutoffsRemainsExplicitlyIncomplete(){
        val first="1. Introduction."+GenerationDiagnostics.TRUNCATED_NOTICE
        val next="2. Démarche."+GenerationDiagnostics.TRUNCATED_NOTICE
        assertTrue(AnswerContinuationPolicy.combine(first,next).contains("peut être incomplète"))
    }
    @Test fun failedContinuationDoesNotReplaceValidFirstPart(){
        val first="1. Mesures initiales."+GenerationDiagnostics.TRUNCATED_NOTICE
        val result=AnswerContinuationPolicy.combine(first,"Inférence indisponible : Timeout")
        assertTrue(result.contains("Mesures initiales"))
        assertTrue(result.contains("reste partiel"))
        assertFalse(result.contains("Inférence indisponible"))
    }
}
