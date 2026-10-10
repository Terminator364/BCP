package com.blessing.medbrain

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.content.pm.ServiceInfo
import android.net.Uri
import androidx.work.*

/** Model copy is independent of Activity lifecycle and has a persistent Android notification. */
class ModelImportWorker(ctx:Context,params:WorkerParameters):CoroutineWorker(ctx,params) {
    private val channel="medbrain_import_v1"
    private fun note(message:String):Notification {
        val manager=applicationContext.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.createNotificationChannel(NotificationChannel(channel,"MedBrain : import du modèle",NotificationManager.IMPORTANCE_LOW))
        return Notification.Builder(applicationContext,channel)
            .setSmallIcon(android.R.drawable.stat_sys_download)
            .setContentTitle("MedBrain • modèle neuronal")
            .setContentText(message)
            .setOngoing(true).build()
    }
    private fun foreground(label:String):ForegroundInfo =
        ForegroundInfo(1096,note(label),ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
    override suspend fun doWork():Result {
        val uri=inputData.getString("uri")?:return Result.failure(workDataOf("error" to "URI manquante"))
        return try{
            setForeground(foreground("Préparation de l'import GGUF"))
            val receipt=ModelVault.import(applicationContext,Uri.parse(uri)){copied,total->
                setProgressAsync(workDataOf("copied" to copied,"total" to total))
                if(copied%(128L*1024L*1024L)<65536){
                    setForegroundAsync(foreground("${copied/1048576} Mio copiés"))
                }
            }
            KnowledgeStore(applicationContext).use{it.event("MODEL_IMPORT_OK",receipt.sha256.take(18))}
            Result.success(workDataOf("sha256" to receipt.sha256))
        } catch(e:Throwable){
            try{KnowledgeStore(applicationContext).use{
                it.event("MODEL_IMPORT_FAILED",e.javaClass.simpleName+": "+(e.message?:"").take(100))
            }}catch(_:Exception){}
            Result.failure(workDataOf("error" to (e.javaClass.simpleName+": "+(e.message?:"")).take(250)))
        }
    }
}