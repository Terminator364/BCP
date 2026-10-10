package com.blessing.medbrain

import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper

/** Persistent provenance-first corpus. One row per PDF page; no invented citations. */
class KnowledgeStore(ctx: Context) : SQLiteOpenHelper(ctx, "medbrain-v1.sqlite", null, 1) {
    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL("CREATE TABLE docs(id TEXT PRIMARY KEY,title TEXT NOT NULL,uri TEXT NOT NULL,processed INTEGER NOT NULL DEFAULT 0,total INTEGER NOT NULL DEFAULT 0,state TEXT NOT NULL DEFAULT 'QUEUED')")
        db.execSQL("CREATE TABLE pages(doc_id TEXT NOT NULL,page INTEGER NOT NULL,body TEXT NOT NULL,PRIMARY KEY(doc_id,page))")
        db.execSQL("CREATE INDEX page_doc_idx ON pages(doc_id,page)")
    }
    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
        // Migrations will be versioned; never silently drop user knowledge.
        throw IllegalStateException("Database migration not defined: $oldVersion -> $newVersion")
    }
    fun register(id: String, title: String, uri: String) {
        writableDatabase.execSQL(
            "INSERT OR IGNORE INTO docs(id,title,uri) VALUES(?,?,?)",
            arrayOf(id, title, uri)
        )
    }
    fun start(id: String): Int {
        readableDatabase.rawQuery("SELECT processed FROM docs WHERE id=?", arrayOf(id)).use {
            return if (it.moveToFirst()) it.getInt(0) else 0
        }
    }
    fun title(id: String): String {
        readableDatabase.rawQuery("SELECT title FROM docs WHERE id=?", arrayOf(id)).use {
            return if (it.moveToFirst()) it.getString(0) else "Document"
        }
    }
    fun save(id: String, page: Int, text: String, processed: Int, total: Int, state: String) {
        val db = writableDatabase
        db.beginTransaction()
        try {
            if (text.isNotBlank()) db.execSQL(
                "INSERT OR REPLACE INTO pages(doc_id,page,body) VALUES(?,?,?)",
                arrayOf(id, page, text)
            )
            db.execSQL("UPDATE docs SET processed=?, total=?, state=? WHERE id=?",
                arrayOf(processed, total, state, id))
            db.setTransactionSuccessful()
        } finally { db.endTransaction() }
    }
    fun counts(): String {
        var docs = 0; var pages = 0; var all = 0
        readableDatabase.rawQuery(
            "SELECT COUNT(*),COALESCE(SUM(processed),0),COALESCE(SUM(total),0) FROM docs", null
        ).use { if (it.moveToFirst()) { docs=it.getInt(0); pages=it.getInt(1); all=it.getInt(2) } }
        var extracted = 0
        readableDatabase.rawQuery("SELECT COUNT(*) FROM pages", null).use {
            if (it.moveToFirst()) extracted = it.getInt(0)
        }
        return "$docs document(s) · $pages/$all pages parcourues · $extracted pages textuelles indexées"
    }
    fun progress(): String {
        val lines = mutableListOf<String>()
        readableDatabase.rawQuery(
            "SELECT title,processed,total,state FROM docs ORDER BY rowid DESC LIMIT 6",null
        ).use { c -> while (c.moveToNext()) {
            lines.add("${c.getString(0)} : ${c.getInt(1)}/${c.getInt(2)} — ${c.getString(3)}")
        } }
        return lines.joinToString("\n")
    }
    /** Deliberately bounded lexical retrieval; this is NOT a semantic embedding search. */
    fun passages(question: String, limit: Int = 4): String {
        val words = Regex("[\\p{L}\\p{N}]{4,}").findAll(question.lowercase())
            .map { it.value }.distinct().take(6).toList()
        if (words.isEmpty()) return ""
        val out = ArrayList<String>()
        val where = words.joinToString(" OR ") { "LOWER(p.body) LIKE ? ESCAPE '!'" }
        val args = words.map { "%"+it.replace("!","!!").replace("%","!%").replace("_","!_")+"%" }.toTypedArray()
        readableDatabase.rawQuery(
            "SELECT d.title,p.page,p.body FROM pages p JOIN docs d ON d.id=p.doc_id WHERE $where LIMIT ${limit*8}",
            args
        ).use { c ->
            val matches = mutableListOf<Triple<Int,String,String>>()
            while (c.moveToNext()) {
                val body=c.getString(2)
                val score=words.count { body.contains(it,ignoreCase=true) }
                matches.add(Triple(score,"${c.getString(0)} — p.${c.getInt(1)}",body))
            }
            matches.sortedByDescending { it.first }.take(limit).forEach {
                out.add("[${it.second}]\n${it.third.take(1300)}")
            }
        }
        return out.joinToString("\n\n")
    }
}
