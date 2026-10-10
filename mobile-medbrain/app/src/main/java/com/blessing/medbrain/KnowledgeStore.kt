package com.blessing.medbrain

import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import java.text.Normalizer

data class DocumentRecord(val id:String,val title:String,val uri:String,val done:Int,val total:Int,val state:String,val error:String)
data class Passage(val title:String,val page:Int,val text:String,val method:String) {
    fun citation() = "$title — page $page ($method)"
}

/** Owns persistent evidence and checkpoints; schema 2 upgrades alpha v1 without data loss. */
class KnowledgeStore(ctx:Context):SQLiteOpenHelper(ctx,"medbrain-v1.sqlite",null,4),java.io.Closeable {
    override fun onCreate(db:SQLiteDatabase) {
        db.execSQL("CREATE TABLE docs(id TEXT PRIMARY KEY,title TEXT NOT NULL,uri TEXT NOT NULL,processed INTEGER NOT NULL DEFAULT 0,total INTEGER NOT NULL DEFAULT 0,state TEXT NOT NULL DEFAULT 'QUEUED',error TEXT NOT NULL DEFAULT '',updated_at INTEGER NOT NULL DEFAULT 0)")
        db.execSQL("CREATE TABLE pages(doc_id TEXT NOT NULL,page INTEGER NOT NULL,body TEXT NOT NULL,extraction_method TEXT NOT NULL DEFAULT 'TEXT',PRIMARY KEY(doc_id,page))")
        db.execSQL("CREATE TABLE events(id INTEGER PRIMARY KEY AUTOINCREMENT,ts INTEGER NOT NULL,kind TEXT NOT NULL,detail TEXT NOT NULL)")
        db.execSQL("CREATE TABLE reviews(id INTEGER PRIMARY KEY AUTOINCREMENT,ts INTEGER NOT NULL,topic TEXT NOT NULL,grade TEXT NOT NULL)")
        db.execSQL("CREATE INDEX page_doc_idx ON pages(doc_id,page)")
        db.execSQL("CREATE VIRTUAL TABLE pages_fts USING fts4(doc_id,page,body,tokenize=unicode61)")
        db.execSQL("CREATE TABLE scan_nodes(tree_uri TEXT NOT NULL,node_uri TEXT NOT NULL,depth INTEGER NOT NULL,name TEXT NOT NULL,mime TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'PENDING',PRIMARY KEY(tree_uri,node_uri))")
        db.execSQL("CREATE TABLE chats(id INTEGER PRIMARY KEY AUTOINCREMENT,thread_id TEXT NOT NULL,kind TEXT NOT NULL,body TEXT NOT NULL,source_refs TEXT NOT NULL DEFAULT '',created_at INTEGER NOT NULL)")
        db.execSQL("CREATE INDEX chat_thread_idx ON chats(thread_id,id)")
    }
    override fun onUpgrade(db:SQLiteDatabase,oldVersion:Int,newVersion:Int) {
        if(oldVersion<=1 && newVersion>=2) {
            db.execSQL("ALTER TABLE docs ADD COLUMN error TEXT NOT NULL DEFAULT ''")
            db.execSQL("ALTER TABLE docs ADD COLUMN updated_at INTEGER NOT NULL DEFAULT 0")
            db.execSQL("ALTER TABLE pages ADD COLUMN extraction_method TEXT NOT NULL DEFAULT 'TEXT'")
            db.execSQL("CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,ts INTEGER NOT NULL,kind TEXT NOT NULL,detail TEXT NOT NULL)")
            db.execSQL("CREATE TABLE IF NOT EXISTS reviews(id INTEGER PRIMARY KEY AUTOINCREMENT,ts INTEGER NOT NULL,topic TEXT NOT NULL,grade TEXT NOT NULL)")
            db.execSQL("CREATE VIRTUAL TABLE IF NOT EXISTS pages_fts USING fts4(doc_id,page,body,tokenize=unicode61)")
            db.execSQL("INSERT INTO pages_fts(doc_id,page,body) SELECT doc_id,page,body FROM pages")
        }
        if(oldVersion<=2 && newVersion>=3){
            db.execSQL("CREATE TABLE IF NOT EXISTS scan_nodes(tree_uri TEXT NOT NULL,node_uri TEXT NOT NULL,depth INTEGER NOT NULL,name TEXT NOT NULL,mime TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'PENDING',PRIMARY KEY(tree_uri,node_uri))")
        }
        if(oldVersion<=3 && newVersion>=4){
            db.execSQL("CREATE TABLE IF NOT EXISTS chats(id INTEGER PRIMARY KEY AUTOINCREMENT,thread_id TEXT NOT NULL,kind TEXT NOT NULL,body TEXT NOT NULL,source_refs TEXT NOT NULL DEFAULT '',created_at INTEGER NOT NULL)")
            db.execSQL("CREATE INDEX IF NOT EXISTS chat_thread_idx ON chats(thread_id,id)")
        }
    }
    fun register(id:String,title:String,uri:String) {
        writableDatabase.execSQL("INSERT OR IGNORE INTO docs(id,title,uri,updated_at) VALUES(?,?,?,?)",arrayOf(id,title,uri,System.currentTimeMillis()))
        event("IMPORT",title.take(180))
    }
    fun start(id:String):Int {
        readableDatabase.rawQuery("SELECT processed FROM docs WHERE id=?",arrayOf(id)).use {
            return if(it.moveToFirst()) it.getInt(0) else 0
        }
    }
    fun title(id:String):String {
        readableDatabase.rawQuery("SELECT title FROM docs WHERE id=?",arrayOf(id)).use {
            return if(it.moveToFirst()) it.getString(0) else "Document"
        }
    }
    fun document(id:String):DocumentRecord? {
        readableDatabase.rawQuery("SELECT id,title,uri,processed,total,state,error FROM docs WHERE id=?",arrayOf(id)).use {
            return if(it.moveToFirst()) DocumentRecord(it.getString(0),it.getString(1),it.getString(2),it.getInt(3),it.getInt(4),it.getString(5),it.getString(6)) else null
        }
    }
    fun documents():List<DocumentRecord> {
        val out=ArrayList<DocumentRecord>()
        readableDatabase.rawQuery("SELECT id,title,uri,processed,total,state,error FROM docs ORDER BY updated_at DESC",null).use {
            while(it.moveToNext()) out.add(DocumentRecord(it.getString(0),it.getString(1),it.getString(2),it.getInt(3),it.getInt(4),it.getString(5),it.getString(6)))
        }
        return out
    }
    fun save(id:String,page:Int,body:String,processed:Int,total:Int,state:String,method:String="TEXT") {
        val db=writableDatabase
        db.beginTransaction()
        try {
            if(body.isNotBlank()) {
                val safeBody=body.take(75000)
                db.execSQL("INSERT OR REPLACE INTO pages(doc_id,page,body,extraction_method) VALUES(?,?,?,?)",arrayOf(id,page,safeBody,method))
                db.execSQL("DELETE FROM pages_fts WHERE doc_id=? AND page=?",arrayOf(id,page))
                db.execSQL("INSERT INTO pages_fts(doc_id,page,body) VALUES(?,?,?)",arrayOf(id,page,safeBody))
            }
            db.execSQL("UPDATE docs SET processed=?,total=?,state=?,error='',updated_at=? WHERE id=?",arrayOf(processed,total,state,System.currentTimeMillis(),id))
            db.setTransactionSuccessful()
        } finally {db.endTransaction()}
    }
    fun markState(id:String,state:String,error:String="") {
        writableDatabase.execSQL("UPDATE docs SET state=?,error=?,updated_at=? WHERE id=?",arrayOf(state,error.take(350),System.currentTimeMillis(),id))
        event("STATE", "$id : $state ${error.take(80)}")
    }
    fun indexedPages(id:String):Int {
        readableDatabase.rawQuery("SELECT COUNT(*) FROM pages WHERE doc_id=?",arrayOf(id)).use {return if(it.moveToFirst())it.getInt(0) else 0}
    }
    fun counts():String {
        val d=documents()
        val n=d.sumOf{it.done}; val all=d.sumOf{it.total}
        var withText=0
        readableDatabase.rawQuery("SELECT COUNT(*) FROM pages",null).use {if(it.moveToFirst())withText=it.getInt(0)}
        return "${d.size} livres • $n/$all pages analysées • $withText pages indexées"
    }
    fun progress():String = documents().take(6).joinToString("\n"){"${it.title.take(42)} • ${it.done}/${it.total} • ${it.state}"}
    fun event(kind:String,detail:String) {
        writableDatabase.execSQL("INSERT INTO events(ts,kind,detail) VALUES(?,?,?)",arrayOf(System.currentTimeMillis(),kind.take(50),detail.take(500)))
        writableDatabase.execSQL("DELETE FROM events WHERE id NOT IN (SELECT id FROM events ORDER BY id DESC LIMIT 600)")
    }
    fun lastEvents():String {
        val out=mutableListOf<String>()
        readableDatabase.rawQuery("SELECT kind,detail FROM events ORDER BY id DESC LIMIT 12",null).use {
            while(it.moveToNext())out.add("${it.getString(0)} : ${it.getString(1)}")
        }
        return out.joinToString("\n")
    }
    /** Durable discovery queue without arbitrary 500-file truncation. */
    fun startFolderScan(treeUri:String,rootUri:String,force:Boolean=false) {
        if(force)writableDatabase.execSQL("DELETE FROM scan_nodes WHERE tree_uri=?",arrayOf(treeUri))
        addScanNode(treeUri,rootUri,0,"Dossier racine","vnd.android.document/directory")
    }
    fun addScanNode(treeUri:String,docUri:String,depth:Int,name:String,mime:String) {
        writableDatabase.execSQL(
            "INSERT OR IGNORE INTO scan_nodes(tree_uri,node_uri,depth,name,mime) VALUES(?,?,?,?,?)",
            arrayOf(treeUri,docUri,depth,name.take(250),mime.take(120))
        )
    }
    data class ScanNode(val uri:String,val depth:Int,val name:String,val mime:String)
    fun nextScanNode(treeUri:String):ScanNode?{
        readableDatabase.rawQuery("SELECT node_uri,depth,name,mime FROM scan_nodes WHERE tree_uri=? AND status='PENDING' ORDER BY depth,node_uri LIMIT 1",arrayOf(treeUri)).use{
            return if(it.moveToFirst()) ScanNode(it.getString(0),it.getInt(1),it.getString(2),it.getString(3)) else null
        }
    }
    fun scanNodeDone(treeUri:String,docUri:String){
        writableDatabase.execSQL("UPDATE scan_nodes SET status='DONE' WHERE tree_uri=? AND node_uri=?",arrayOf(treeUri,docUri))
    }
    fun scanNodeFailed(treeUri:String,docUri:String){
        writableDatabase.execSQL("UPDATE scan_nodes SET status='ERROR' WHERE tree_uri=? AND node_uri=?",arrayOf(treeUri,docUri))
    }
    fun pendingScanNodes(treeUri:String):Int{
        readableDatabase.rawQuery("SELECT COUNT(*) FROM scan_nodes WHERE tree_uri=? AND status='PENDING'",arrayOf(treeUri)).use{
            return if(it.moveToFirst()) it.getInt(0) else 0
        }
    }
    fun scanSummary():String {
        val parts=mutableListOf<String>()
        readableDatabase.rawQuery("SELECT COUNT(*),SUM(CASE WHEN status='PENDING' THEN 1 ELSE 0 END),SUM(CASE WHEN status='ERROR' THEN 1 ELSE 0 END) FROM scan_nodes",null).use{
            if(it.moveToFirst()) parts.add("${it.getInt(0)} éléments explorés/enregistrés · ${it.getInt(1)} à parcourir · ${it.getInt(2)} erreurs")
        }
        return parts.joinToString("")
    }
    fun review(topic:String,grade:String) {
        writableDatabase.execSQL("INSERT INTO reviews(ts,topic,grade) VALUES(?,?,?)",arrayOf(System.currentTimeMillis(),topic.take(200),grade.take(30)))
        event("REVISION", "$topic : $grade")
    }
    fun reviewCounts():String {
        var n=0
        readableDatabase.rawQuery("SELECT COUNT(*) FROM reviews",null).use {if(it.moveToFirst())n=it.getInt(0)}
        return "$n révisions enregistrées"
    }
    data class ChatMessage(val id:Long,val kind:String,val body:String,val sources:String,val timestamp:Long)
    fun addChat(kind:String,body:String,sources:String="",threadId:String="default"){
        writableDatabase.execSQL("INSERT INTO chats(thread_id,kind,body,source_refs,created_at) VALUES(?,?,?,?,?)",
            arrayOf(threadId,kind.take(20),body.take(25000),sources.take(15000),System.currentTimeMillis()))
        writableDatabase.execSQL("DELETE FROM chats WHERE id NOT IN (SELECT id FROM chats ORDER BY id DESC LIMIT 1000)")
    }
    fun messages(threadId:String="default",limit:Int=70):List<ChatMessage>{
        val out=ArrayList<ChatMessage>()
        readableDatabase.rawQuery("SELECT id,kind,body,source_refs,created_at FROM chats WHERE thread_id=? ORDER BY id DESC LIMIT ?",arrayOf(threadId,limit.coerceIn(1,200).toString())).use{c->
            while(c.moveToNext())out.add(ChatMessage(c.getLong(0),c.getString(1),c.getString(2),c.getString(3),c.getLong(4)))
        }
        return out.asReversed()
    }
    fun clearChat(threadId:String="default"){
        writableDatabase.execSQL("DELETE FROM chats WHERE thread_id=?",arrayOf(threadId))
        event("CHAT_CLEAR","User confirmed chat history deletion")
    }
    /** Precision-first retrieval: no obstetrics snippets for a cardiac anatomy query. */
    fun retrieve(question:String,limit:Int=5):List<Passage> {
        val tokens=SearchPolicy.terms(question)
        if(tokens.isEmpty()) return emptyList()
        // Normalize search terms to FTS unicode61, allow spelling variants only from known word families.
        val queries=SearchPolicy.expand(tokens).distinct().take(14)
        val match=queries.joinToString(" OR "){"$it*"}
        val ranked=ArrayList<Pair<Double,Passage>>()
        readableDatabase.rawQuery(
            "SELECT d.title,pages_fts.page,pages_fts.body,p.extraction_method FROM pages_fts JOIN docs d ON d.id=pages_fts.doc_id LEFT JOIN pages p ON p.doc_id=pages_fts.doc_id AND p.page=CAST(pages_fts.page AS INTEGER) WHERE pages_fts MATCH ? LIMIT 180",
            arrayOf(match)
        ).use{c->
            while(c.moveToNext()){
                val title=c.getString(0)
                val body=c.getString(2)
                val score=SearchPolicy.score(question,title,body)
                if(score>0){
                    val offset=SearchPolicy.firstPosition(tokens,body)
                    val begin=(offset-150).coerceAtLeast(0)
                    val excerpt=body.substring(begin,minOf(body.length,begin+950))
                    ranked.add(score to Passage(title,c.getInt(1),excerpt,c.getString(3)?:"TEXT"))
                }
            }
        }
        return ranked.sortedByDescending{it.first}.take(limit.coerceIn(1,8)).map{it.second}
    }
    fun passages(question:String,limit:Int=5):String = retrieve(question,limit).joinToString("\n\n"){
        "[${it.citation()}]\n${it.text}"
    }
}
