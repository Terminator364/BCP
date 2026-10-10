package com.blessing.medbrain

import android.content.Context
import android.net.Uri
import androidx.work.CoroutineWorker
import androidx.work.ExistingWorkPolicy
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.tom_roush.pdfbox.android.PDFBoxResourceLoader
import com.tom_roush.pdfbox.pdmodel.PDDocument
import com.tom_roush.pdfbox.text.PDFTextStripper
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/** Bounded, restartable ingestion. A retry processes the next 8 pages. */
class IngestWorker(ctx: Context, params: WorkerParameters) : CoroutineWorker(ctx, params) {
    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        val uriString = inputData.getString("uri") ?: return@withContext Result.failure()
        val id = inputData.getString("id") ?: return@withContext Result.failure()
        val uri = Uri.parse(uriString)
        val store = KnowledgeStore(applicationContext)
        try {
            val offset = store.start(id)
            val mime = applicationContext.contentResolver.getType(uri).orEmpty().lowercase()
            if (mime == "application/pdf" || store.title(id).lowercase().endsWith(".pdf")) {
                PDFBoxResourceLoader.init(applicationContext)
                applicationContext.contentResolver.openInputStream(uri).use { stream ->
                    requireNotNull(stream) { "Cannot open document" }
                    PDDocument.load(stream).use { pdf ->
                        val total = pdf.numberOfPages
                        val last = minOf(total,offset+8)
                        for (page in offset+1..last) {
                            val stripper = PDFTextStripper().apply { startPage = page; endPage = page }
                            val text = stripper.getText(pdf).trim()
                            store.save(id,page,text,page,total,if (page==total) "TEXT_DONE" else "READING")
                        }
                        if (last < total) {
                            val next = OneTimeWorkRequestBuilder<IngestWorker>()
                                .setInputData(inputData).build()
                            WorkManager.getInstance(applicationContext).enqueueUniqueWork(
                                "learn-$id", ExistingWorkPolicy.APPEND_OR_REPLACE, next
                            )
                        } else {
                            val hasText = store.indexedPages(id) > 0
                            store.markState(id, if(hasText) "TEXT_DONE" else "OCR_REQUIRED")
                        }
                        return@withContext Result.success()
                    }
                }
            } else {
                applicationContext.contentResolver.openInputStream(uri).use { stream ->
                    requireNotNull(stream) { "Cannot open document" }
                    // Text import bounded to prevent accidentally exhausting RAM.
                    val buffer=ByteArray(2_000_000+1)
                    var n=0
                    while(n<buffer.size) {
                        val r=stream.read(buffer,n,buffer.size-n)
                        if(r<0) break
                        n+=r
                    }
                    if(n==buffer.size) throw IllegalArgumentException("Text >2 MB: import by smaller parts")
                    val text=String(buffer,0,n,Charsets.UTF_8)
                    val chunks=text.chunked(5000)
                    chunks.forEachIndexed { i, part -> store.save(id,i+1,part,i+1,chunks.size,"TEXT_DONE") }
                    Result.success()
                }
            }
        } catch (ex: Exception) {
            android.util.Log.e("MedBrain","Ingestion failed for "+id,ex)
            // Retain checkpoint and distinguish temporary failures from actual expertise.
            if (runAttemptCount<3) Result.retry() else {
                store.save(id,0,"",store.start(id),0,"FAILED: ${ex.javaClass.simpleName}")
                Result.failure()
            }
        } finally { store.close() }
    }
}
