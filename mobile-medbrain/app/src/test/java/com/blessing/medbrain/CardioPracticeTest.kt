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
class CardioPracticeTest {
    @Test fun studyAndPracticeUseOriginalFiche(){
        val ctx=ApplicationProvider.getApplicationContext<Context>()
        val fiches=CardioCurriculum.all(ctx)
        val first=fiches.first()
        val selected=CardioPractice.match(first.id,first.title,fiches)
        assertNotNull(selected)
        assertEquals(first.content,selected!!.content)
        assertTrue(CardioPractice.questions(selected).contains(first.recall.first()))
        assertTrue(CardioPractice.comparison(selected,"Mon raisonnement").contains(first.essential.first()))
        assertTrue(CardioPractice.source(selected).contains(first.sourceLocator))
    }
    @Test fun newTopicCannotUseStaleFiche(){
        val f=CardioCurriculum.all(ApplicationProvider.getApplicationContext<Context>())
        val first=f.first()
        assertNull(CardioPractice.match(first.id,"Hémorragie digestive aiguë",f))
        assertNull(CardioPractice.match("nonexistent",first.title,f))
        assertNull(CardioPractice.match(null,first.title,f))
    }
    @Test fun groundedComparisonIsNotAutomatedGrade(){
        val f=CardioCurriculum.all(ApplicationProvider.getApplicationContext<Context>()).first()
        val out=CardioPractice.comparison(f,"Réponse libre")
        assertTrue(out.contains("grille de comparaison"))
        assertTrue(out.contains("pas une correction automatique"))
        assertFalse(out.contains("20/20"))
    }
}
