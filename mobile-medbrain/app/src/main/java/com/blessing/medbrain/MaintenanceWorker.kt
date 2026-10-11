package com.blessing.medbrain

import android.content.Context
import android.os.BatteryManager
import androidx.work.*
import java.util.concurrent.TimeUnit

/** Durable scheduling, always bounded and battery-aware. No separate orchestration authority. */
class MaintenanceWorker(ctx:Context,params:WorkerParameters):CoroutineWorker(ctx,params) {
    override suspend fun doWork():Result {
        val store=KnowledgeStore(applicationContext)
        return try {
            val launched=enqueueBatch(applicationContext,1)
            val prefs=applicationContext.getSharedPreferences("medbrain",Context.MODE_PRIVATE)
            val folder=prefs.getString("local_tree",null)
            val now=System.currentTimeMillis()
            if(folder!=null&&now-prefs.getLong("last_tree_scan",0)>6*60*60*1000L &&
                now>=prefs.getLong("inference_until",0L)){
                val scan=OneTimeWorkRequestBuilder<FolderScanWorker>().setInputData(
                    Data.Builder().putString("tree_uri",folder).putBoolean("rescan",true).build()).build()
                WorkManager.getInstance(applicationContext).enqueueUniqueWork(
                    "tree-check",ExistingWorkPolicy.KEEP,scan)
                prefs.edit().putLong("last_tree_scan",now).apply()
            }
            store.event("AUTO_CHECK","$launched reprises éligibles; acquisition locale bornée")
            Result.success()
        } catch(e:Exception){
            store.event("AUTO_ERROR",e.javaClass.simpleName+": "+e.message)
            Result.retry()
        } finally {store.close()}
    }
    companion object {
        /**
         * Round-robin of unfinished books, with only 1-2 new WorkRequests per pass.
         * NEVER reschedule NEEDS_ACCESS automatically: SAF permission is a human gate.
         */
        fun enqueueBatch(ctx:Context,limit:Int=2):Int {
            val prefs=ctx.getSharedPreferences("medbrain",Context.MODE_PRIVATE)
            if(System.currentTimeMillis()<prefs.getLong("inference_until",0L)||
                prefs.getBoolean("queue_repairing",false)||
                !ProcessingBudget.mayOpenPdf(ProcessingBudget.heapHeadroom(),false))return 0
            val eligible=KnowledgeStore(ctx).use{store->
                store.documents().filter{it.state=="QUEUED"||it.state=="READING"}
            }
            if(eligible.isEmpty())return 0
            val start=Math.floorMod(prefs.getInt("ingest_cursor",0),eligible.size)
            val picked=(0 until minOf(limit.coerceIn(1,1),eligible.size))
                .map{eligible[(start+it)%eligible.size]}
            prefs.edit().putInt("ingest_cursor",(start+picked.size)%eligible.size).apply()
            for(doc in picked) {
                val next=OneTimeWorkRequestBuilder<IngestWorker>()
                    .setConstraints(Constraints.Builder().setRequiresBatteryNotLow(true)
                        .setRequiresStorageNotLow(true).build())
                    .setBackoffCriteria(BackoffPolicy.LINEAR,30,TimeUnit.SECONDS)
                    .setInputData(workDataOf("id" to doc.id)).build()
                WorkManager.getInstance(ctx).enqueueUniqueWork(
                    "learn-${doc.id}",ExistingWorkPolicy.KEEP,next)
            }
            return picked.size
        }
        fun arm(ctx:Context) {
            val constraints=Constraints.Builder().setRequiresBatteryNotLow(true)
                .setRequiresStorageNotLow(true).build()
            val req=PeriodicWorkRequestBuilder<MaintenanceWorker>(1,TimeUnit.HOURS)
                .setConstraints(constraints).build()
            WorkManager.getInstance(ctx).enqueueUniquePeriodicWork(
                "medbrain-continuity-v1",ExistingPeriodicWorkPolicy.KEEP,req)
        }
    }
}
