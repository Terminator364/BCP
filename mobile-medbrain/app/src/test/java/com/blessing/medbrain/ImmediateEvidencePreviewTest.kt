package com.blessing.medbrain

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk=[28])
class ImmediateEvidencePreviewTest{
    @Test fun showsOriginalCardiologyCourseBeforeSlowModelReply(){
        val ctx=ApplicationProvider.getApplicationContext<Context>()
        val f=CardioCurriculum.findRelevant(ctx,"Insuffisance cardiaque",1).first()
        val preview=StudyEngine.immediatePreview("Insuffisance cardiaque",listOf(f),emptyList())
        assertTrue(preview.contains(f.sourceTitle))
        assertTrue(preview.contains("Repère Google Docs"))
        assertTrue(preview.contains("sans synthèse IA"))
        assertTrue(preview.contains(CardioCurriculum.excerpt(f,"Insuffisance cardiaque",380)))
        assertFalse(preview.contains("p. 999"))
    }
    @Test fun showsRealPdfPageNotInventedCitation(){
        val item=Passage("Cours de clinique.pdf",18,
            "Les signes et symptômes sont décrits dans cette section.", "TEXT")
        val text=StudyEngine.immediatePreview("signes",emptyList(),listOf(item))
        assertTrue(text.contains("page 18"))
        assertTrue(text.contains("Cours de clinique.pdf"))
        assertTrue(text.contains("à ouvrir dans les sources"))
        assertFalse(text.contains("Les signes et symptômes sont décrits"))
    }
    @Test fun noneAvailableDoesNotFakeSources(){
        assertEquals("",StudyEngine.immediatePreview("bonjour",emptyList(),emptyList()))
    }
}
