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
class KnowledgeStore(ctx:Context):SQLiteOpenHelper(ctx,"medbrain-v1.sqlite",null,2) {
    override fun onCreate(db:SQLiteDatabase) {
        db.execSQL("CREATE TABLE docs(id TEXT PRIMARY KEY,title TEXT NOT NULL,uri TEXT NOT NULL,processed INTEGER NOT NULL DEFAULT 0,total INTEGER NOT NULL DEFAULT 0,state TEXT NOT NULL DEFAULT 'QUEUED',error TEXT NOT NULL DEFAULT '',updated_at INTEGER NOT NULL DEFAULT 0)")
        db.execSQL("CREATE TABLE pages(doc_id TEXT NOT NULL,page INTEGER NOT NULL,body TEXT NOT NULL,extraction_method TEXT NOT NULL DEFAULT 'TEXT',PRIMARY KEY(doc_id,page))")
        db.execSQL("CREATE TABLE events(id INTEGER PRIMARY KEY AUTOINCREMENT,ts INTEGER NOT NULL,kind TEXT NOT NULL,detail TEXT NOT NULL)")
        db.execSQL("CREATE TABLE reviews(id INTEGER PRIMARY KEY AUTOINCREMENT,ts INTEGER NOT NULL,topic TEXT NOT NULL,grade TEXT NOT NULL)")
        db.execSQL("CREATE INDEX page_doc_idx ON pages(doc_id,page)")
        db.execSQL("CREATE VIRTUAL TABLE pages_fts USING fts4(doc_id,page,body,tokenize=unicode61)")
    }
    override fun onUpgrade(db:SQLiteDatabase,oldVersion:Int,newVersion:Int) {
        if(oldVersion==1 && newVersion>=2) {
            db.execSQL("ALTER TABLE docs ADD COLUMN error TEXT NOT NULL DEFAULT ''")
            db.execSQL("ALTER TABLE docs ADD COLUMN updated_at INTEGER NOT NULL DEFAULT 0")
            db.execSQL("ALTER TABLE pages ADD COLUMN extraction_method TEXT NOT NULL DEFAULT 'TEXT'")
            db.execSQL("CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,ts INTEGER NOT NULL,kind TEXT NOT NULL,detail TEXT NOT NULL)")
            db.execSQL("CREATE TABLE IF NOT EXISTS reviews(id INTEGER PRIMARY KEY AUTOINCREMENT,ts INTEGER NOT NULL,topic TEXT NOT NULL,grade TEXT NOT NULL)")
            db.execSQL("CREATE VIRTUAL TABLE IF NOT EXISTS pages_fts USING fts4(doc_id,page,body,tokenize=unicode61)")
            db.execSQL("INSERT INTO pages_fts(doc_id,page,body) SELECT doc_id,page,body FROM pages")
        } else throw IllegalStateException("Migration unavailable $oldVersion->$newVersion")
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
    fun review(topic:String,grade:String) {
        writableDatabase.execSQL("INSERT INTO reviews(ts,topic,grade) VALUES(?,?,?)",arrayOf(System.currentTimeMillis(),topic.take(200),grade.take(30)))
        event("REVISION", "$topic : $grade")
    }
    fun reviewCounts():String {
        var n=0
        readableDatabase.rawQuery("SELECT COUNT(*) FROM reviews",null).use {if(it.moveToFirst())n=it.getInt(0)}
        return "$n révisions enregistrées"
    }
    fun retrieve(question:String,limit:Int=5):List<Passage> {
        val tokens=Regex("[\\p{L}\\p{N}]{4,}").findAll(question.lowercase()).map{it.value}.distinct().take(7).toList()
        if(tokens.isEmpty())return emptyList()
        val query=tokens.joinToString(" OR "){"$it*"}
        val out=mutableListOf<Triple<Int,Passage,Int>>()
        readableDatabase.rawQuery(
            "SELECT d.title,f.page,f.body,p.extraction_method FROM pages_fts JOIN docs d ON d.id=pages_fts.doc_id LEFT JOIN pages p ON p.doc_id=pages_fts.doc_id AND p.page=CAST(pages_fts.page AS INTEGER) WHERE pages_fts MATCH ? LIMIT 70",
            arrayOf(query)
        ).use {c->
            while(c.moveToNext()) {
                val text=c.getString(2)
                val score=tokens.count{text.contains(it,ignoreCase=true)}
                val ix=tokens.map{text.indexOf(it,ignoreCase=true)}.filter{it>=0}.minOrNull() ?: 0
                val begin=(ix-180).coerceAtLeast(0)
                val snippet=text.substring(begin,minOf(text.length,begin+1150))
                out.add(Triple(score,Passage(c.getString(0),c.getInt(1),snippet,c.getString(3)?:"TEXT"),ix))
            }
        }
        return out.sortedWith(compareByDescending<Triple<Int,Passage,Int>>{it.first}.thenBy{it.third}).take(limit).map{it.second}
    }
    fun passages(question:String,limit:Int=5):String = retrieve(question,limit).joinToString("\n\n"){
        "[${it.citation()}]\n${it.text}"
    }
}
