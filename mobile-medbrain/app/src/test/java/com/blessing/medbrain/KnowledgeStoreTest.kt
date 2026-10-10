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
    @Test fun independentConversationThreadsPreserveMessages(){
        val ctx=ApplicationProvider.getApplicationContext<Context>()
        ctx.deleteDatabase("medbrain-v1.sqlite")
        KnowledgeStore(ctx).use{store->
            val first=store.createThread()
            val second=store.createThread()
            store.addChat("user","ECG et intervalle PR",threadId=first)
            store.addChat("assistant","Durée habituelle de l'intervalle PR.",threadId=first)
            store.addChat("user","Physiologie rénale",threadId=second)
            assertEquals(2,store.messages(first).size)
            assertEquals(1,store.messages(second).size)
            assertTrue(store.threads().any{it.id==first&&it.title.contains("ECG")})
            assertTrue(store.threads().any{it.id==second&&it.title.contains("Physiologie")})
            assertEquals(1,store.findThreads("intervalle PR").size)
            assertEquals(first,store.findThreads("intervalle PR").single().id)
            assertEquals(second,store.findThreads("rénale").single().id)
            store.renameThread(second,"Rénal — physiologie")
            assertEquals(second,store.findThreads("Rénal — physiologie").single().id)
        }
        KnowledgeStore(ctx).use{store->
            assertEquals(2,store.threads().size)
            val renal=store.threads().first{it.title.contains("Physiologie")}
            val cardiac=store.threads().first{it.title.contains("ECG")}
            store.clearChat(renal.id)
            assertTrue(store.messages(renal.id).isEmpty())
            assertEquals(2,store.messages(cardiac.id).size)
            store.deleteThread(renal.id)
            assertEquals(1,store.threads().size)
            assertEquals(2,store.messages(cardiac.id).size)
        }
    }
    @Test fun schemaFourMigratesChatsAndIndexedBooksWithoutLoss(){
        val ctx=ApplicationProvider.getApplicationContext<Context>()
        ctx.deleteDatabase("medbrain-v1.sqlite")
        // Create the full legacy v4 schema first using SQLite upgrade from v3.
        val old=ctx.openOrCreateDatabase("medbrain-v1.sqlite",Context.MODE_PRIVATE,null)
        old.execSQL("CREATE TABLE docs(id TEXT PRIMARY KEY,title TEXT NOT NULL,uri TEXT NOT NULL,processed INTEGER NOT NULL DEFAULT 0,total INTEGER NOT NULL DEFAULT 0,state TEXT NOT NULL DEFAULT 'QUEUED',error TEXT NOT NULL DEFAULT '',updated_at INTEGER NOT NULL DEFAULT 0)")
        old.execSQL("CREATE TABLE pages(doc_id TEXT NOT NULL,page INTEGER NOT NULL,body TEXT NOT NULL,extraction_method TEXT NOT NULL DEFAULT 'TEXT',PRIMARY KEY(doc_id,page))")
        old.execSQL("CREATE TABLE chats(id INTEGER PRIMARY KEY AUTOINCREMENT,thread_id TEXT NOT NULL,kind TEXT NOT NULL,body TEXT NOT NULL,source_refs TEXT NOT NULL DEFAULT '',created_at INTEGER NOT NULL)")
        old.execSQL("INSERT INTO docs(id,title,uri,processed,total,state) VALUES('biology','Biologie clinique','content://biology',1,1,'INDEXED')")
        old.execSQL("INSERT INTO pages(doc_id,page,body) VALUES('biology',1,'Une valeur de laboratoire doit être interprétée avec le contexte clinique.')")
        old.execSQL("INSERT INTO chats(thread_id,kind,body,created_at) VALUES('default','user','Parle-moi de la biologie clinique',100)")
        old.execSQL("INSERT INTO chats(thread_id,kind,body,created_at) VALUES('default','assistant','Début de l’explication',200)")
        old.version=4
        old.close()
        KnowledgeStore(ctx).use{store->
            assertEquals("Biologie clinique",store.document("biology")!!.title)
            assertEquals(1,store.indexedPages("biology"))
            assertEquals(2,store.messages("default").size)
            assertTrue(store.threads().any{it.id=="default"})
            val id=store.createThread()
            store.addChat("user","Autre conversation",threadId=id)
            assertEquals(2,store.messages("default").size)
        }
    }
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

    @Test fun chatHistorySurvivesDatabaseCloseAndReopen(){
        val ctx=ApplicationProvider.getApplicationContext<Context>()
        ctx.deleteDatabase("medbrain-v1.sqlite")
        KnowledgeStore(ctx).use {
            it.addChat("user","Salut !")
            it.addChat("assistant","Bonjour, je suis MedBrain.")
        }
        KnowledgeStore(ctx).use {
            val history=it.messages()
            assertEquals(2,history.size)
            assertEquals("Salut !",history[0].body)
            assertEquals("assistant",history[1].kind)
            assertTrue(it.documents().isEmpty())
        }
    }
    @Test fun versionThreeDataMigratesToConversationalFour(){
        val ctx=ApplicationProvider.getApplicationContext<Context>()
        ctx.deleteDatabase("medbrain-v1.sqlite")
        val db=ctx.openOrCreateDatabase("medbrain-v1.sqlite",Context.MODE_PRIVATE,null)
        db.execSQL("CREATE TABLE docs(id TEXT PRIMARY KEY,title TEXT NOT NULL,uri TEXT NOT NULL,processed INTEGER NOT NULL DEFAULT 0,total INTEGER NOT NULL DEFAULT 0,state TEXT NOT NULL DEFAULT 'QUEUED',error TEXT NOT NULL DEFAULT '',updated_at INTEGER NOT NULL DEFAULT 0)")
        db.execSQL("CREATE TABLE pages(doc_id TEXT NOT NULL,page INTEGER NOT NULL,body TEXT NOT NULL,extraction_method TEXT NOT NULL DEFAULT 'TEXT',PRIMARY KEY(doc_id,page))")
        db.execSQL("CREATE TABLE events(id INTEGER PRIMARY KEY AUTOINCREMENT,ts INTEGER NOT NULL,kind TEXT NOT NULL,detail TEXT NOT NULL)")
        db.execSQL("CREATE TABLE reviews(id INTEGER PRIMARY KEY AUTOINCREMENT,ts INTEGER NOT NULL,topic TEXT NOT NULL,grade TEXT NOT NULL)")
        db.execSQL("CREATE TABLE scan_nodes(tree_uri TEXT NOT NULL,node_uri TEXT NOT NULL,depth INTEGER NOT NULL,name TEXT NOT NULL,mime TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'PENDING',PRIMARY KEY(tree_uri,node_uri))")
        db.execSQL("CREATE VIRTUAL TABLE pages_fts USING fts4(doc_id,page,body,tokenize=unicode61)")
        db.execSQL("INSERT INTO docs(id,title,uri,processed,total,state) VALUES('keep','Cardiologie','content://cardio',1,1,'INDEXED')")
        db.execSQL("INSERT INTO pages(doc_id,page,body) VALUES('keep',1,'Le myocarde assure la contraction cardiaque.')")
        db.execSQL("INSERT INTO pages_fts(doc_id,page,body) VALUES('keep',1,'Le myocarde assure la contraction cardiaque.')")
        db.version=3
        db.close()
        KnowledgeStore(ctx).use {
            assertEquals("Cardiologie",it.document("keep")!!.title)
            it.addChat("user","Explique la physiologie du myocarde")
            assertEquals(1,it.messages().size)
        }
    }
    @Test fun retrievalDoesNotLoseCardiologyAfterTwoHundredUnrelatedPages(){
        val ctx=ApplicationProvider.getApplicationContext<Context>()
        ctx.deleteDatabase("medbrain-v1.sqlite")
        KnowledgeStore(ctx).use { store ->
            // FTS4 historically returned only the first 180 OR hits, hiding the answer.
            for(i in 1..240) {
                val id="obst-$i"
                store.register(id,"Cours d'obstétrique $i","content://fictitious/obst/$i")
                store.save(id,1,
                    "La taille du sac gestationnel et le coeur foetal sont étudiés en obstétrique.",
                    1,1,"INDEXED")
            }
            store.register("cardiology","Anatomie cardiovasculaire","content://fictitious/cardio")
            store.save("cardiology",1,
                "La taille du coeur adulte varie avec la morphologie et les dimensions cardiaques.",
                1,1,"INDEXED")
            assertTrue("The adult cardiac passage must have a positive relevance score",
                SearchPolicy.score("taille du coeur","Anatomie cardiovasculaire",
                    "La taille du coeur adulte varie avec la morphologie et les dimensions cardiaques.")>0)
            assertTrue("The search plan needs an ungrouped FTS4 OR fallback",
                SearchPolicy.candidateQueries("taille du coeur").last()
                    .startsWith("taille* OR coeur*"))
            val hits=store.retrieve("taille du coeur",4)
            assertTrue("Cardiac adult reference missing after FTS noise: $hits",
                hits.any { it.title=="Anatomie cardiovasculaire" })
            assertTrue("No fetal obstetric page should pass this adult cardiac query",
                hits.none { it.title.startsWith("Cours d'obstétrique") })
        }
    }

}
