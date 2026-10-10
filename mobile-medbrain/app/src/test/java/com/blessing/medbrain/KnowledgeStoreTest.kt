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
    @Test fun resumableFolderIndexHasNoFiveHundredFileCeiling(){
        val ctx=ApplicationProvider.getApplicationContext<Context>()
        ctx.deleteDatabase("medbrain-v1.sqlite")
        KnowledgeStore(ctx).use { store ->
            store.startFolderScan("tree:library","node:root",true)
            for(i in 0 until 750)store.addScanNode("tree:library","node:$i",1,"book_$i.pdf","application/pdf")
            assertEquals("node:root",store.nextScanNode("tree:library")!!.uri)
            store.scanNodeDone("tree:library","node:root")
            assertEquals(750,store.pendingScanNodes("tree:library"))
            store.scanNodeDone("tree:library","node:5")
            assertEquals(749,store.pendingScanNodes("tree:library"))
        }
    }
    @Test fun oldCandidateV2BooksSurviveSchemaThree(){
        val ctx=ApplicationProvider.getApplicationContext<Context>()
        ctx.deleteDatabase("medbrain-v1.sqlite")
        val db=ctx.openOrCreateDatabase("medbrain-v1.sqlite",Context.MODE_PRIVATE,null)
        db.execSQL("CREATE TABLE docs(id TEXT PRIMARY KEY,title TEXT NOT NULL,uri TEXT NOT NULL,processed INTEGER NOT NULL DEFAULT 0,total INTEGER NOT NULL DEFAULT 0,state TEXT NOT NULL DEFAULT 'QUEUED',error TEXT NOT NULL DEFAULT '',updated_at INTEGER NOT NULL DEFAULT 0)")
        db.execSQL("CREATE TABLE pages(doc_id TEXT NOT NULL,page INTEGER NOT NULL,body TEXT NOT NULL,extraction_method TEXT NOT NULL DEFAULT 'TEXT',PRIMARY KEY(doc_id,page))")
        db.execSQL("CREATE VIRTUAL TABLE pages_fts USING fts4(doc_id,page,body,tokenize=unicode61)")
        db.execSQL("INSERT INTO docs(id,title,uri,processed,total,state) VALUES('old2','Livre v2','content://doc/2',1,1,'INDEXED')")
        db.execSQL("INSERT INTO pages(doc_id,page,body) VALUES('old2',1,'Le myocarde contient des cellules musculaires.')")
        db.execSQL("INSERT INTO pages_fts(doc_id,page,body) VALUES('old2',1,'Le myocarde contient des cellules musculaires.')")
        db.version=2
        db.close()
        KnowledgeStore(ctx).use { store ->
            assertEquals("Livre v2",store.document("old2")!!.title)
            assertEquals(1,store.retrieve("myocarde").size)
            store.startFolderScan("tree:new","node:root")
            assertEquals(1,store.pendingScanNodes("tree:new"))
        }
    }

}
