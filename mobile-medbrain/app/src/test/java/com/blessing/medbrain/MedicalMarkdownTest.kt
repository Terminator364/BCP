package com.blessing.medbrain

import android.graphics.Typeface
import android.text.Spanned
import android.text.style.StyleSpan
import android.text.style.TypefaceSpan
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk=[28])
class MedicalMarkdownTest {
    @Test fun medicalHeadingsAndBoldAreReadableRatherThanRawStars(){
        val s=MedicalMarkdown.render("## Diagnostic\n**Signes** : dyspnée, orthopnée.")
        assertEquals("Diagnostic\nSignes : dyspnée, orthopnée.",s.toString())
        val styled=s as Spanned
        assertTrue(styled.getSpans(0,s.length,StyleSpan::class.java)
            .any{it.style==Typeface.BOLD})
    }
    @Test fun inlineTechnicalTermsUseMonospace(){
        val tick=0x60.toChar()
        val s=MedicalMarkdown.render("Lecture de la valeur "+tick+"FEVG"+tick+" à l'échographie.")
        assertTrue(s.toString().contains("FEVG"))
        assertFalse(s.toString().contains(tick.toString()))
        assertEquals(1,(s as Spanned).getSpans(
            0,s.length,TypefaceSpan::class.java).size)
    }
    @Test fun unmatchedMarkdownMarkersRemainVisible(){
        assertEquals("Plan **non terminé",MedicalMarkdown.render("Plan **non terminé").toString())
        assertEquals("**",MedicalMarkdown.render("**").toString())
    }
    @Test fun paragraphsAndNumberedMedicalStepsArePreserved(){
        val raw="1. Interrogatoire\n2. Examen clinique\n\nConclusion"
        assertEquals(raw,MedicalMarkdown.render(raw).toString())
    }
}
