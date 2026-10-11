package com.blessing.medbrain

import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import java.text.Normalizer

data class DocumentRecord(val id:String,val title:String,val uri:String,val done:Int,val total:Int,val state:String,val error:String)
data class ChatThread(val id:String,val title:String,val updatedAt:Long)
data class Passage(val title:String,val page:Int,val text:String,val method:String) {
    fun citation() = "$title — page $page ($method)"
}

/** Owns persistent evidence and checkpoints; schema 2 upgrades alpha v1 without data loss. */
class KnowledgeStore(ctx:Context):SQLiteOpenHelper(ctx,"medbrain-v1.sqlite",null,5),java.io.Closeable {
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
        db.execSQL("CREATE TABLE chat_threads(id TEXT PRIMARY KEY,title TEXT NOT NULL,created_at INTEGER NOT NULL,updated_at INTEGER NOT NULL)")
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
        if(oldVersion<=4 && newVersion>=5){
            db.execSQL("CREATE TABLE IF NOT EXISTS chat_threads(id TEXT PRIMARY KEY,title TEXT NOT NULL,created_at INTEGER NOT NULL,updated_at INTEGER NOT NULL)")
            // Legacy messages stay byte-for-byte; only a new metadata row is added.
            db.execSQL("INSERT OR IGNORE INTO chat_threads(id,title,created_at,updated_at) SELECT thread_id, 'Conversation précédente', MIN(created_at), MAX(created_at) FROM chats GROUP BY thread_id")
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
        val pct=if(all>0) " • "+((100L*withText)/all).coerceIn(0L,100L)+" % des pages recensées indexées" else ""
        return "${d.size} livres • $n/$all pages analysées • $withText pages indexées"+pct
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
    /** Conversation metadata: messages are never copied or erased when switching threads. */
    fun createThread():String {
        val id=java.util.UUID.randomUUID().toString()
        val now=System.currentTimeMillis()
        writableDatabase.execSQL(
            "INSERT INTO chat_threads(id,title,created_at,updated_at) VALUES(?,?,?,?)",
            arrayOf(id,"Nouvelle conversation",now,now))
        return id
    }
    fun threads(limit:Int=50):List<ChatThread> {
        val results=mutableListOf<ChatThread>()
        readableDatabase.rawQuery(
            "SELECT id,title,updated_at FROM chat_threads ORDER BY updated_at DESC LIMIT ?",
            arrayOf(limit.coerceIn(1,100).toString())).use{cursor->
            while(cursor.moveToNext())results.add(ChatThread(
                cursor.getString(0),cursor.getString(1),cursor.getLong(2)))
        }
        return results
    }
    /** Search stored chat titles and texts, using bound SQL parameters. */
    fun findThreads(query:String,limit:Int=40):List<ChatThread>{
        val term=query.trim().take(80)
        if(term.isBlank())return threads(limit)
        val pattern="%"+term.replace("\\","\\\\").replace("%","\\%")
            .replace("_","\\_")+"%"
        val results=mutableListOf<ChatThread>()
        readableDatabase.rawQuery(
            "SELECT t.id,t.title,t.updated_at FROM chat_threads t "+
            "WHERE t.title LIKE ? ESCAPE '\\' OR EXISTS "+
            "(SELECT 1 FROM chats c WHERE c.thread_id=t.id AND c.body LIKE ? ESCAPE '\\') "+
            "ORDER BY t.updated_at DESC LIMIT ?",
            arrayOf(pattern,pattern,limit.coerceIn(1,100).toString())).use{cursor->
            while(cursor.moveToNext())results.add(ChatThread(
                cursor.getString(0),cursor.getString(1),cursor.getLong(2)))
        }
        return results
    }
    fun renameThread(id:String,title:String){
        val name=title.trim().take(90)
        if(name.isNotBlank())writableDatabase.execSQL(
            "UPDATE chat_threads SET title=? WHERE id=?",arrayOf(name,id))
    }
    fun deleteThread(id:String){
        val db=writableDatabase
        db.beginTransaction()
        try{
            db.execSQL("DELETE FROM chats WHERE thread_id=?",arrayOf(id))
            db.execSQL("DELETE FROM chat_threads WHERE id=?",arrayOf(id))
            db.setTransactionSuccessful()
        }finally{db.endTransaction()}
        // Deliberate action only, caller must obtain explicit user confirmation.
    }
    fun ensureThread(id:String){
        val now=System.currentTimeMillis()
        writableDatabase.execSQL(
            "INSERT OR IGNORE INTO chat_threads(id,title,created_at,updated_at) VALUES(?,?,?,?)",
            arrayOf(id,if(id=="default")"Conversation précédente" else "Nouvelle conversation",now,now))
    }
    data class ChatMessage(val id:Long,val kind:String,val body:String,val sources:String,val timestamp:Long)
    fun addChat(kind:String,body:String,sources:String="",threadId:String="default"){
        val db=writableDatabase
        val now=System.currentTimeMillis()
        db.beginTransaction()
        try{
            db.execSQL("INSERT OR IGNORE INTO chat_threads(id,title,created_at,updated_at) VALUES(?,?,?,?)",
                arrayOf(threadId,if(threadId=="default")"Conversation précédente" else "Nouvelle conversation",now,now))
            db.execSQL("INSERT INTO chats(thread_id,kind,body,source_refs,created_at) VALUES(?,?,?,?,?)",
                arrayOf(threadId,kind.take(20),body.take(25000),sources.take(15000),now))
            if(kind=="user"){
                db.execSQL("UPDATE chat_threads SET title=? WHERE id=? AND title='Nouvelle conversation'",
                    arrayOf(body.trim().replace(Regex("\\s+")," ").take(64),threadId))
            }
            db.execSQL("UPDATE chat_threads SET updated_at=? WHERE id=?",arrayOf(now,threadId))
            db.setTransactionSuccessful()
        }finally{db.endTransaction()}
        // Retention must not silently erase older user conversations.
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
    /**
     * Multi-stage retrieval prevents early OR-only FTS results from crowding out
     * a clinically relevant page in a large indexed library.
     * Read-only search: database schema and all document checkpoints are unchanged.
     */
    fun retrieve(question:String,limit:Int=5):List<Passage> {
        val stages=SearchPolicy.candidateQueries(question)
        if(stages.isEmpty())return emptyList()
        val cap=limit.coerceIn(1,8)
        val evidence=LinkedHashMap<String,Pair<Double,Passage>>()
        for(match in stages) {
            readableDatabase.rawQuery(
                "SELECT pages_fts.doc_id,d.title,pages_fts.page," +
                     "snippet(pages_fts,'','',' ... ',-1,42)," +
                    "COALESCE(p.extraction_method,'TEXT') FROM pages_fts " +
                    "JOIN docs d ON d.id=pages_fts.doc_id " +
                    "LEFT JOIN pages p ON p.doc_id=pages_fts.doc_id " +
                    "AND p.page=CAST(pages_fts.page AS INTEGER) " +
                    "WHERE pages_fts MATCH ? LIMIT 150",
                arrayOf(match)
            ).use { c->
                while(c.moveToNext()) {
                    val title=c.getString(1)
                    val body=c.getString(3)
                    val score=SearchPolicy.score(question,title,body)
                    if(score>0) {
                        val offset=SearchPolicy.firstPosition(SearchPolicy.terms(question),body)
                        val begin=(offset-150).coerceAtLeast(0)
                        val excerpt=body.substring(begin,minOf(body.length,begin+950))
                        val page=c.getInt(2)
                        val key=c.getString(0)+":"+page
                        val passage=Passage(title,page,excerpt,c.getString(4))
                        if(evidence[key]?.first?.let{score>it} != false)
                            evidence[key]=score to passage
                    }
                }
            }
            // Collect a small diversity reserve, then avoid a potentially noisy OR scan.
            if(evidence.size>=cap*3)break
        }
        val ranked=evidence.values.sortedWith(
            compareByDescending<Pair<Double,Passage>>{it.first}
                .thenBy{it.second.title}.thenBy{it.second.page}
        )
        // Reserve room for different books before taking more than two pages from one title.
        // This does not claim consensus: only actually retrieved pages may be cited.
        val selected=ArrayList<Pair<Double,Passage>>()
        val titleUse=HashMap<String,Int>()
        for(candidate in ranked){
            if(selected.size==cap)break
            val title=candidate.second.title
            if((titleUse[title]?:0)<2){
                selected.add(candidate)
                titleUse[title]=(titleUse[title]?:0)+1
            }
        }
        if(selected.size<cap)for(candidate in ranked){
            if(selected.size==cap)break
            if(candidate !in selected)selected.add(candidate)
        }
        return selected.map{it.second}
    }
    fun passages(question:String,limit:Int=5):String = retrieve(question,limit).joinToString("\n\n"){
        "[${it.citation()}]\n${it.text}"
    }
}
