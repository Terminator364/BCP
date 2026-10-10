package com.blessing.medbrain
import org.junit.Assert.*
import org.junit.Test

class GenerationDiagnosticsTest{
    @Test fun tokenBudgetCutoffMustBeVisible(){
        val out=GenerationDiagnostics.annotate("1. Évaluer 2. Presser 3. Appeler 4. Vérifier",
            96,96)
        assertTrue(out.contains("4. Vérifier"))
        assertTrue(out.contains("peut être incomplète"))
        assertTrue(out.contains("continue"))
    }
    @Test fun earlyEosIsNotLabeledTruncated(){
        assertEquals("Terminé.",GenerationDiagnostics.annotate("Terminé.",40,96))
        assertFalse(GenerationDiagnostics.likelyTruncated(40,96))
    }
    @Test fun noFinalIsNeverPretendedComplete(){
        assertEquals(ModelOutputPolicy.NO_FINAL,
            GenerationDiagnostics.annotate(ModelOutputPolicy.NO_FINAL,96,96))
    }
    @Test fun reportsNumericTimingWithoutPatientText(){
        val metric=GenerationDiagnostics.summary(96,96,4200,15700,6.1f)
        assertTrue(metric.contains("prefill_ms=4200"))
        assertTrue(metric.contains("decode_ms=15700"))
        assertTrue(metric.contains("limit_reached=true"))
        assertFalse(metric.contains("saignement"))
    }
}
