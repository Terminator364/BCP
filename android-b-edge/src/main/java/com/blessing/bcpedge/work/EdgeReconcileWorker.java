package com.blessing.bcpedge.work;

import android.content.Context;

import androidx.annotation.NonNull;
import androidx.work.Data;
import androidx.work.Worker;
import androidx.work.WorkerParameters;

import com.blessing.bcpedge.BcpClient;
import com.blessing.bcpedge.storage.EdgeDatabase;

import org.json.JSONObject;

public final class EdgeReconcileWorker extends Worker {
    public EdgeReconcileWorker(@NonNull Context context, @NonNull WorkerParameters params) {
        super(context, params);
    }

    @NonNull
    @Override
    public Result doWork() {
        try {
            BcpClient client=new BcpClient(getApplicationContext());
            JSONObject sync=client.syncOrchestrationState();
            int pending=EdgeDatabase.get(getApplicationContext()).edgeDao().countPendingJobs();
            boolean offline=sync.optBoolean("offline",false);
            JSONObject sentinel=client.sentinelStatus();
            Data out=new Data.Builder()
                    .putInt("pending_jobs",pending)
                    .putString("mode",sync.optString("mode","EDGE_ONLY"))
                    .putBoolean("offline",offline)
                    .putString("sentinel_state",sentinel.optString("state","NOT_OBSERVED"))
                    .putInt("sentinel_failures",sentinel.optInt("consecutive_failures",0))
                    .putBoolean("resume_pending",sentinel.optBoolean("resume_pending",false))
                    .putString("resume_request_id",sentinel.optString("resume_request_id",""))
                    .putBoolean("durable_reconcile_executed",true)
                    .build();
            // Offline is a valid EDGE_ONLY/PC_UNAVAILABLE state, not a WorkManager
            // failure. Persist it and wait for the next bounded periodic cycle.
            return Result.success(out);
        } catch (Throwable t) {
            return getRunAttemptCount()<3 ? Result.retry() : Result.failure();
        }
    }
}
