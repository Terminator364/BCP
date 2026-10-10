package com.blessing.medbrain

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.SQLiteMode

@RunWith(RobolectricTestRunner::class)
@Config(sdk=[28])
@SQLiteMode(SQLiteMode.Mode.NATIVE)
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
    @Test fun oldAlphaDataSurvivesVersionTwo(){
        val ctx=ApplicationProvider.getApplicationContext<Context>()
        ctx.deleteDatabase("medbrain-v1.sqlite")
        val db=ctx.openOrCreateDatabase("medbrain-v1.sqlite",Context.MODE_PRIVATE,null)
        db.execSQL("CREATE TABLE docs(id TEXT PRIMARY KEY,title TEXT NOT NULL,uri TEXT NOT NULL,processed INTEGER NOT NULL DEFAULT 0,total INTEGER NOT NULL DEFAULT 0,state TEXT NOT NULL DEFAULT 'QUEUED')")
        db.execSQL("CREATE TABLE pages(doc_id TEXT NOT NULL,page INTEGER NOT NULL,body TEXT NOT NULL,PRIMARY KEY(doc_id,page))")
        db.execSQL("INSERT INTO docs(id,title,uri,processed,total,state) VALUES('old','Ancien cours','content://old',1,1,'TEXT_DONE')")
        db.execSQL("INSERT INTO pages(doc_id,page,body) VALUES('old',1,'Les signes cliniques sont répertoriés.')")
        db.version=1
        db.close()
        KnowledgeStore(ctx).use { store ->
            assertEquals("Ancien cours",store.document("old")!!.title)
            assertEquals(1,store.retrieve("cliniques").size)
            assertEquals(1,store.indexedPages("old"))
        }
    }
}
