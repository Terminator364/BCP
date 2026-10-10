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
            var launched=0
            for(record in store.documents()) {
                if(record.state=="QUEUED"||record.state=="READING") {
                    val next=OneTimeWorkRequestBuilder<IngestWorker>().setInputData(
                        Data.Builder().putString("id",record.id).build()).build()
                    WorkManager.getInstance(applicationContext).enqueueUniqueWork(
                        "learn-${record.id}",ExistingWorkPolicy.KEEP,next)
                    launched++
                }
            }
            val prefs=applicationContext.getSharedPreferences("medbrain",Context.MODE_PRIVATE)
            val folder=prefs.getString("local_tree",null)
            val now=System.currentTimeMillis()
            if(folder!=null&&now-prefs.getLong("last_tree_scan",0)>6*60*60*1000L){
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
