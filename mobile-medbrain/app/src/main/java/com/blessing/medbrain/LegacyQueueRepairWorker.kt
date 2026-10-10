package com.blessing.medbrain

import android.content.Context
import androidx.work.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.util.concurrent.TimeUnit

/** One-time bounded reset of legacy WorkManager fan-out (not document data). */
class LegacyQueueRepairWorker(ctx:Context,p:WorkerParameters):CoroutineWorker(ctx,p) {
    override suspend fun doWork():Result=withContext(Dispatchers.IO) {
        val prefs=applicationContext.getSharedPreferences("medbrain",Context.MODE_PRIVATE)
        if(prefs.getBoolean("queue_repaired_v1",false))return@withContext Result.success()
        val docs=KnowledgeStore(applicationContext).use{it.documents().map{d->d.id}.sorted()}
        val last=prefs.getString("queue_repair_last_id","").orEmpty()
        val batch=docs.filter{it>last}.take(24)
        val wm=WorkManager.getInstance(applicationContext)
        try {
            for(id in batch){
                if(isStopped)return@withContext Result.retry()
                wm.cancelUniqueWork("learn-$id").result.get(15,TimeUnit.SECONDS)
                prefs.edit().putString("queue_repair_last_id",id).commit()
            }
            if(docs.any{it>prefs.getString("queue_repair_last_id","").orEmpty()}){
                val next=OneTimeWorkRequestBuilder<LegacyQueueRepairWorker>()
                    .setBackoffCriteria(BackoffPolicy.LINEAR,30,TimeUnit.SECONDS).build()
                wm.enqueueUniqueWork("medbrain-queue-repair-v1",ExistingWorkPolicy.APPEND_OR_REPLACE,next)
            }else{
                prefs.edit().putBoolean("queue_repaired_v1",true)
                    .putBoolean("queue_repairing",false).remove("queue_repair_last_id").commit()
                KnowledgeStore(applicationContext).use{
                    it.event("QUEUE_REPAIRED","Anciens travaux d'ingestion annulés; progression des livres intacte")
                }
                MaintenanceWorker.enqueueBatch(applicationContext,2)
            }
            Result.success()
        }catch(e:Exception){
            KnowledgeStore(applicationContext).use{
                it.event("QUEUE_REPAIR_RETRY",e.javaClass.simpleName)
            }
            Result.retry()
        }
    }
    companion object {
        fun arm(ctx:Context){
            val prefs=ctx.getSharedPreferences("medbrain",Context.MODE_PRIVATE)
            if(prefs.getBoolean("queue_repaired_v1",false))return
            prefs.edit().putBoolean("queue_repairing",true).apply()
            val request=OneTimeWorkRequestBuilder<LegacyQueueRepairWorker>()
                .setConstraints(Constraints.Builder().setRequiresBatteryNotLow(true).build())
                .setBackoffCriteria(BackoffPolicy.LINEAR,30,TimeUnit.SECONDS).build()
            WorkManager.getInstance(ctx).enqueueUniqueWork(
                "medbrain-queue-repair-v1",ExistingWorkPolicy.KEEP,request)
        }
    }
}
