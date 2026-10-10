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
class KnowledgeStoreTest {
    @Test fun readsRealPageAndTracksReview(){
        val ctx=ApplicationProvider.getApplicationContext<Context>()
        ctx.deleteDatabase("medbrain-v1.sqlite")
        KnowledgeStore(ctx).use { store ->
            store.register("doc-1","Livre médical","content://library/book.pdf")
            store.save("doc-1",1,"L'insuffisance cardiaque peut entraîner un oedème pulmonaire.",1,2,"READING","TEXT")
            store.save("doc-1",2,"Le diagnostic doit être relié au contexte clinique.",2,2,"INDEXED","TEXT")
            val found=store.retrieve("cardiaque")
            assertEquals(1,found.first().page)
            assertEquals("Livre médical",found.first().title)
            assertEquals("INDEXED",store.document("doc-1")!!.state)
            store.review("insuffisance cardiaque","À_REVOIR")
            assertTrue(store.reviewCounts().contains("1 révisions"))
        }
    }
    @Test fun duplicatePageDoesNotIncreaseCount(){
        val ctx=ApplicationProvider.getApplicationContext<Context>()
        ctx.deleteDatabase("medbrain-v1.sqlite")
        KnowledgeStore(ctx).use { store ->
            store.register("doc-2","Livre","content://doc")
            store.save("doc-2",1,"Myocarde clinique.",1,1,"INDEXED")
            store.save("doc-2",1,"Myocarde examen.",1,1,"INDEXED")
            assertEquals(1,store.indexedPages("doc-2"))
            assertEquals(1,store.retrieve("myocarde").size)
        }
    }
}
