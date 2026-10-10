package com.blessing.medbrain

import android.content.Context
import android.net.Uri
import androidx.documentfile.provider.DocumentFile
import androidx.work.*
import java.security.MessageDigest

/** Optional local folder import. Not equivalent to unrestricted Google Drive API access. */
class FolderScanWorker(ctx:Context,params:WorkerParameters):CoroutineWorker(ctx,params) {
    override suspend fun doWork():Result {
        val uri=inputData.getString("tree_uri")?:return Result.failure()
        val store=KnowledgeStore(applicationContext)
        return try {
            val root=DocumentFile.fromTreeUri(applicationContext,Uri.parse(uri))?:return Result.failure()
            val pending=ArrayDeque<Pair<DocumentFile,Int>>()
            pending.add(root to 0)
            var seen=0;var accepted=0
            while(pending.isNotEmpty() && seen<1200 && accepted<500) {
                val (node,depth)=pending.removeFirst()
                if(node.isDirectory && depth<=12) {
                    for(child in node.listFiles())pending.add(child to depth+1)
                } else if(node.isFile) {
                    seen++
                    val title=node.name ?: "document"
                    val eligible=title.endsWith(".pdf",true)||title.endsWith(".txt",true)||title.endsWith(".md",true)||title.endsWith(".png",true)||title.endsWith(".jpg",true)
                    if(eligible){
                        val key=MessageDigest.getInstance("SHA-256").digest(node.uri.toString().toByteArray()).joinToString(""){"%02x".format(it)}
                        store.register(key,title,node.uri.toString())
                        val request=OneTimeWorkRequestBuilder<IngestWorker>().setInputData(
                            Data.Builder().putString("id",key).build()).build()
                        WorkManager.getInstance(applicationContext).enqueueUniqueWork("learn-$key",ExistingWorkPolicy.KEEP,request)
                        accepted++
                    }
                }
            }
            store.event("DOSSIER","$accepted fichiers éligibles, exploration bornée à 1200 éléments")
            Result.success()
        }catch(e:Exception){
            store.event("DOSSIER_ERREUR",e.javaClass.simpleName+": "+e.message)
            Result.failure()
        }finally{store.close()}
    }
}
