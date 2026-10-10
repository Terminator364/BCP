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
class CardioCurriculumTest {
    @Test fun originalMedRebuildThreeTomesAreReadableOffline() {
        val ctx=ApplicationProvider.getApplicationContext<Context>()
        val all=CardioCurriculum.all(ctx)
        assertEquals(156,all.size)
        assertEquals(47,CardioCurriculum.forTome(ctx,1).size)
        assertEquals(66,CardioCurriculum.forTome(ctx,2).size)
        assertEquals(43,CardioCurriculum.forTome(ctx,3).size)
        assertEquals(60,all.map{it.moduleId}.toSet().size)
        assertEquals(156,all.map{it.id}.toSet().size)
        assertTrue(all.all{it.content.isNotBlank()&&it.sourceTitle.isNotBlank()
            &&it.sourceLocator.isNotBlank()})
        assertTrue(all.all{it.objectives.isNotEmpty()&&it.recall.isNotEmpty()})
    }
    @Test fun deepReadingUsesUnchangedAdjacentSourceMaterial() {
        val ctx=ApplicationProvider.getApplicationContext<Context>()
        val items=CardioCurriculum.forTome(ctx,1)
        val pack=CardioCurriculum.session(ctx,items.first().id,true)
        assertEquals(3,pack.size)
        assertEquals(items.take(3).map{it.id},pack.map{it.id})
        assertEquals(items.first().content,pack.first().content)
        assertEquals(1,CardioCurriculum.session(ctx,items.first().id,false).size)
        assertTrue(CardioCurriculum.session(ctx,"unknown",true).isEmpty())
    }
    @Test fun navigationDoesNotCrossTomeBoundary() {
        val ctx=ApplicationProvider.getApplicationContext<Context>()
        for(t in 1..3){
            val last=CardioCurriculum.forTome(ctx,t).last()
            assertEquals(listOf(last.id),
                CardioCurriculum.session(ctx,last.id,true).map{it.id})
        }
    }
}
