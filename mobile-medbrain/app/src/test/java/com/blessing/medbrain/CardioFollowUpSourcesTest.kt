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
class CardioFollowUpSourcesTest{
    @Test fun continuationUsesPreviousRecordedFicheNotNewDocumentSearch(){
        val ctx=ApplicationProvider.getApplicationContext<Context>()
        val f=CardioCurriculum.findRelevant(ctx,"Insuffisance cardiaque",1).first()
        val sources=CardioCurriculum.references(listOf(f))
        val matched=CardioCurriculum.fromPreviousReferences(ctx,sources)
        assertEquals(listOf(f.id),matched.map{it.id})
        val previous=listOf(
            KnowledgeStore.ChatMessage(1,"user","Explique l'insuffisance cardiaque","",100),
            KnowledgeStore.ChatMessage(2,"assistant","Voici les causes et symptômes.",sources,200)
        )
        val prompt=DialoguePlanner.prompt("Continue, parle du traitement",previous,emptyList(),"auto",matched)
        assertTrue(prompt.contains("Référence confirmée"))
        assertTrue(prompt.contains(f.sourceLocator.take(60)))
        assertTrue(prompt.contains("Continue, parle du traitement"))
        assertTrue(prompt.length<=1350)
    }
    @Test fun citationCannotBeRecoveredFromUnrelatedOrInventedReferences(){
        val ctx=ApplicationProvider.getApplicationContext<Context>()
        assertTrue(CardioCurriculum.fromPreviousReferences(ctx,
            "Accidents des anticoagulants.pdf, p. 9").isEmpty())
        assertTrue(CardioCurriculum.fromPreviousReferences(ctx,
            "[MedRebuild, Google Docs, Tome 2, fiche CARDIO.T2.M999.F01]").isEmpty())
        assertTrue(CardioCurriculum.fromPreviousReferences(ctx,"").isEmpty())
    }
    @Test fun failedFollowupShowsOriginalSourceButDoesNotClaimModelContinuation(){
        val ctx=ApplicationProvider.getApplicationContext<Context>()
        val f=CardioCurriculum.findRelevant(ctx,"Insuffisance cardiaque",1).first()
        val txt=DialoguePlanner.fallback(emptyList(),true,listOf(f),"continue")
        assertTrue(txt.contains(f.sourceTitle))
        assertTrue(txt.contains("pas la suite rédigée par l'IA"))
    }
}
