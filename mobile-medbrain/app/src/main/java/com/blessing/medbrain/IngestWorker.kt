package com.blessing.medbrain

import android.content.Context
import android.graphics.Bitmap
import android.net.Uri
import androidx.work.*
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.latin.TextRecognizerOptions
import com.tom_roush.pdfbox.android.PDFBoxResourceLoader
import com.tom_roush.pdfbox.pdmodel.PDDocument
import com.tom_roush.pdfbox.rendering.PDFRenderer
import com.tom_roush.pdfbox.text.PDFTextStripper
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.coroutines.tasks.await
import java.io.FileNotFoundException

/** Resumable batches. Scan-only pages use bundled offline OCR; graphics still need visual review. */
class IngestWorker(ctx:Context,params:WorkerParameters):CoroutineWorker(ctx,params) {
    override suspend fun doWork():Result = withContext(Dispatchers.IO) {
        val id=inputData.getString("id")?:return@withContext Result.failure()
        val store=KnowledgeStore(applicationContext)
        val record=store.document(id)?:return@withContext Result.failure().also{store.close()}
        val pref=applicationContext.getSharedPreferences("medbrain",Context.MODE_PRIVATE)
        if(IngestConcurrency.shouldYield(System.currentTimeMillis(),
                pref.getLong("inference_until",0L))){
            store.close()
            return@withContext Result.retry()
        }
        IngestConcurrency.gate.acquire()
        try {
            val path=Uri.parse(record.uri)
            val mime=applicationContext.contentResolver.getType(path).orEmpty().lowercase()
            if(record.title.endsWith(".pdf",true)||mime=="application/pdf") ingestPdf(store,record,path)
            else if(mime.startsWith("image/") || record.title.endsWith(".jpg",true) ||record.title.endsWith(".png",true)) ingestImage(store,record,path)
            else ingestText(store,record,path)
        } catch(e:Throwable) {
            if(e is kotlinx.coroutines.CancellationException)throw e
            store.markState(id,if(e is SecurityException||e is FileNotFoundException) "NEEDS_ACCESS" else "ERROR",e.javaClass.simpleName+": "+(e.message?:""))
            if(e is OutOfMemoryError) return@withContext Result.failure()
            if(e is SecurityException || e is FileNotFoundException) return@withContext Result.failure()
            if(runAttemptCount<2) Result.retry() else Result.failure()
        } finally {
            // A single completed book opens exactly one additional document slot.
            val completed=try{store.document(id)?.state=="INDEXED"}catch(_:Exception){false}
            store.close()
            IngestConcurrency.gate.release()
            if(completed)MaintenanceWorker.enqueueBatch(applicationContext,1)
        }
    }
    private suspend fun ocr(bitmap:Bitmap):String {
        val recognizer=TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)
        return try {recognizer.process(InputImage.fromBitmap(bitmap,0)).await().text.trim()}
        finally {recognizer.close()}
    }
    private suspend fun ingestPdf(store:KnowledgeStore,record:DocumentRecord,uri:Uri):Result {
        PDFBoxResourceLoader.init(applicationContext)
        val offset=record.done
        val local=SourceCache.getOrFetch(applicationContext,record.id,uri)
        PDDocument.load(local).use {pdf ->
                val total=pdf.numberOfPages
                val end=minOf(total,offset+4)
                if (offset>=total) {store.markState(record.id,"INDEXED");return Result.success()}
                val prefs=applicationContext.getSharedPreferences("medbrain",Context.MODE_PRIVATE)
                for(page in offset+1..end) {
                    // WorkManager may have started this job just before the user opened Chat.
                    // Yield between pages; already persisted pages and PDF cache remain intact.
                    if(isStopped || IngestConcurrency.shouldYield(System.currentTimeMillis(),
                            prefs.getLong("inference_until",0L))){
                        store.event("INGEST_PAUSED","La génération neuronale est prioritaire; reprise page "+page)
                        return Result.retry()
                    }
                    val text=PDFTextStripper().apply {startPage=page;endPage=page}.getText(pdf).trim()
                    var found=text
                    var method="TEXT"
                    if(text.length<65) {
                        val bitmap=PDFRenderer(pdf).renderImageWithDPI(page-1,100f)
                        try { val scanned=ocr(bitmap);if(scanned.length>text.length){found=scanned;method="OCR"} }
                        finally {bitmap.recycle()}
                    }
                    store.save(record.id,page,found,page,total,if(page==total)"INDEXED" else "READING",method)
                }
                if(end<total) {
                    val next=OneTimeWorkRequestBuilder<IngestWorker>().setInputData(inputData).build()
                    WorkManager.getInstance(applicationContext).enqueueUniqueWork(
                        "learn-${record.id}",ExistingWorkPolicy.APPEND_OR_REPLACE,next)
                } else {
                    store.markState(record.id,if(store.indexedPages(record.id)>0)"INDEXED" else "OCR_REQUIRED")
                }
                if(end>=total)SourceCache.release(applicationContext,record.id)
                return Result.success()
        }
    }
    private suspend fun ingestImage(store:KnowledgeStore,record:DocumentRecord,uri:Uri):Result {
        val image=InputImage.fromFilePath(applicationContext,uri)
        val r=TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)
        try{
            val body=r.process(image).await().text
            store.save(record.id,1,body,1,1,if(body.isBlank())"VISUAL_REVIEW" else "INDEXED","OCR_IMAGE")
        } finally {r.close()}
        return Result.success()
    }
    private fun ingestText(store:KnowledgeStore,record:DocumentRecord,uri:Uri):Result {
        applicationContext.contentResolver.openInputStream(uri).use {stream->
            requireNotNull(stream)
            val bytes=stream.readBytes()
            require(bytes.size<=4_000_000){"Fichier texte >4 Mo"}
            val content=String(bytes,Charsets.UTF_8)
            val chunks=content.chunked(3500)
            for(i in record.done until chunks.size)store.save(record.id,i+1,chunks[i],i+1,chunks.size,if(i==chunks.lastIndex)"INDEXED" else "READING")
        }
        return Result.success()
    }
}
