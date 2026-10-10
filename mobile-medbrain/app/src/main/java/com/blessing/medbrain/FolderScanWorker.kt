package com.blessing.medbrain

import android.content.Context
import android.net.Uri
import android.provider.DocumentsContract
import androidx.work.*
import java.security.MessageDigest

/**
 * Resumable SAF tree crawler, not a full Google Drive OAuth API.
 * Every discovered file/directory has a persistent SQLite checkpoint.
 * Each work item handles max 36 nodes, not max 500 files in the library.
 */
class FolderScanWorker(ctx:Context,params:WorkerParameters):CoroutineWorker(ctx,params) {
    override suspend fun doWork():Result {
        val raw=inputData.getString("tree_uri")?:return Result.failure()
        val tree=Uri.parse(raw)
        val store=KnowledgeStore(applicationContext)
        return try {
            val rootId=DocumentsContract.getTreeDocumentId(tree)
            val root=DocumentsContract.buildDocumentUriUsingTree(tree,rootId)
            val force=inputData.getBoolean("rescan",false)
            store.startFolderScan(raw,root.toString(),force)
            val resolver=applicationContext.contentResolver
            var visited=0
            var imported=0
            while(visited<36 && !isStopped) {
                val node=store.nextScanNode(raw) ?: break
                try{
                    if(node.depth>50) {
                        store.event("SCAN_DEPTH","Maximum profondeur 50 atteinte : "+node.name)
                        store.scanNodeFailed(raw,node.uri)
                    }else if(node.mime==DocumentsContract.Document.MIME_TYPE_DIR) {
                        val current=Uri.parse(node.uri)
                        val docId=DocumentsContract.getDocumentId(current)
                        val children=DocumentsContract.buildChildDocumentsUriUsingTree(tree,docId)
                        resolver.query(children,arrayOf(
                            DocumentsContract.Document.COLUMN_DOCUMENT_ID,
                            DocumentsContract.Document.COLUMN_DISPLAY_NAME,
                            DocumentsContract.Document.COLUMN_MIME_TYPE),null,null,null).use {c->
                            requireNotNull(c){"Fournisseur de dossiers indisponible"}
                            while(c.moveToNext()) {
                                val child=DocumentsContract.buildDocumentUriUsingTree(tree,c.getString(0))
                                store.addScanNode(raw,child.toString(),node.depth+1,c.getString(1)?:"document",c.getString(2)?:"")
                            }
                        }
                        store.scanNodeDone(raw,node.uri)
                    }else{
                        val name=node.name
                        val supported=listOf(".pdf",".txt",".md",".jpg",".jpeg",".png")
                            .any{name.endsWith(it,true)}
                        if(supported){
                            val id=MessageDigest.getInstance("SHA-256").digest(node.uri.toByteArray())
                                .joinToString(""){"%02x".format(it)}
                            store.register(id,name,node.uri)
                            val work=OneTimeWorkRequestBuilder<IngestWorker>().setInputData(
                                Data.Builder().putString("id",id).build()).build()
                            WorkManager.getInstance(applicationContext).enqueueUniqueWork(
                                "learn-$id",ExistingWorkPolicy.KEEP,work)
                            imported++
                        }
                        store.scanNodeDone(raw,node.uri)
                    }
                }catch(e:Exception){
                    store.scanNodeFailed(raw,node.uri)
                    store.event("SCAN_NODE_FAILED",node.name.take(65)+" : "+e.javaClass.simpleName+" "+(e.message?:"").take(100))
                }
                visited++
            }
            val pending=store.pendingScanNodes(raw)
            store.event("SCAN_PROGRESS","$visited nœuds traités, $imported livres importés, $pending restants")
            if(pending>0 && !isStopped){
                val more=OneTimeWorkRequestBuilder<FolderScanWorker>().setInputData(
                    Data.Builder().putString("tree_uri",raw).putBoolean("rescan",false).build()).build()
                val key=MessageDigest.getInstance("SHA-256").digest(raw.toByteArray()).take(8)
                    .joinToString(""){"%02x".format(it)}
                WorkManager.getInstance(applicationContext).enqueueUniqueWork(
                    "folder-$key",ExistingWorkPolicy.APPEND_OR_REPLACE,more)
            }else if(pending==0){store.event("SCAN_COMPLETE","Parcours terminé; "+store.scanSummary())}
            Result.success()
        }catch(e:Exception){
            store.event("SCAN_ERROR",e.javaClass.simpleName+": "+(e.message?:"").take(150))
            if(runAttemptCount<2)Result.retry() else Result.failure()
        }finally{store.close()}
    }
}