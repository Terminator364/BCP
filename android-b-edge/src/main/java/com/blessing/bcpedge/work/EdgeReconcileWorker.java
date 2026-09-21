package com.blessing.bcpedge.work;

import android.content.Context;

import androidx.annotation.NonNull;
import androidx.work.Data;
import androidx.work.ListenableWorker;
import androidx.work.Worker;
import androidx.work.WorkerParameters;

import com.blessing.bcpedge.BcpClient;
import com.blessing.bcpedge.EdgeLocalExecutor;
import com.blessing.bcpedge.storage.EdgeDatabase;

import org.json.JSONObject;

public final class EdgeReconcileWorker extends Worker {
    public EdgeReconcileWorker(@NonNull Context context, @NonNull WorkerParameters params) {
        super(context, params);
    }

    @NonNull
    @Override
    public Result doWork() {
        return execute(getApplicationContext(), getRunAttemptCount(), getInputData().getString("trigger_reason"));
    }

    public static ListenableWorker.Result execute(Context context, int runAttemptCount, String triggerReason) {
        try {
            BcpClient client = new BcpClient(context);
            client.recordEvent("EDGE_RECONCILE_START", triggerReason == null ? "UNSPECIFIED" : triggerReason);
            JSONObject local = EdgeLocalExecutor.drain(context, client);
            JSONObject sync = client.syncOrchestrationState();
            sync.put("local_executor", local);
            int pending = EdgeDatabase.get(context).edgeDao().countPendingJobs();
            boolean offline = sync.optBoolean("offline", false);
            JSONObject sentinel = client.sentinelStatus();
            Data out = new Data.Builder()
                    .putInt("pending_jobs", pending)
                    .putString("mode", sync.optString("mode", "EDGE_ONLY"))
                    .putBoolean("offline", offline)
                    .putString("sentinel_state", sentinel.optString("state", "NOT_OBSERVED"))
                    .putInt("sentinel_failures", sentinel.optInt("consecutive_failures", 0))
                    .putBoolean("resume_pending", sentinel.optBoolean("resume_pending", false))
                    .putString("resume_request_id", sentinel.optString("resume_request_id", ""))
                    .putBoolean("durable_reconcile_executed", true)
                    .putInt("local_jobs_attempted", local.optInt("attempted", 0))
                    .putInt("local_jobs_sent", local.optInt("sent", 0))
                    .putInt("local_jobs_waiting", local.optInt("waiting", 0))
                    .putString("trigger_reason", triggerReason == null ? "UNSPECIFIED" : triggerReason)
                    .build();
            return Result.success(out);
        } catch (Throwable t) {
            return runAttemptCount < 3 ? Result.retry() : Result.failure();
        }
    }
}
