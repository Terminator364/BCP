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
class CardioChatEvidenceTest{
    @Test fun originalCardiologyCourseIsSearchableWithoutImportingPdf(){
        val ctx=ApplicationProvider.getApplicationContext<Context>()
        val matches=CardioCurriculum.findRelevant(ctx,"Insuffisance cardiaque",2)
        assertTrue(matches.isNotEmpty())
        assertTrue(matches.first().title.contains("Insuffisance cardiaque",ignoreCase=true))
        assertTrue(matches.first().content.isNotBlank())
        assertTrue(CardioCurriculum.references(matches).contains("Google Docs"))
        assertTrue(CardioCurriculum.references(matches).contains("Repère :"))
    }
    @Test fun curatedChatPromptDoesNotFakePdfPages(){
        val ctx=ApplicationProvider.getApplicationContext<Context>()
        val q="Insuffisance cardiaque"
        val refs=CardioCurriculum.findRelevant(ctx,q,2)
        val prompt=DialoguePlanner.prompt(q,emptyList(),emptyList(),"auto",refs)
        assertTrue(prompt.contains("MedRebuild"))
        assertTrue(prompt.contains("Google Docs"))
        assertFalse(prompt.contains("p. 999"))
        assertTrue(prompt.length<=1410)
    }
    @Test fun nonCardiacTopicDoesNotReceiveStaleCardioCitation(){
        val ctx=ApplicationProvider.getApplicationContext<Context>()
        assertTrue(CardioCurriculum.findRelevant(ctx,"hémorragie digestive massive",2).isEmpty())
        assertTrue(CardioCurriculum.findRelevant(ctx,"Bonjour",2).isEmpty())
    }
}
