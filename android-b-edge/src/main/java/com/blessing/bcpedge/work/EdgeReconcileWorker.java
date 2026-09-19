package com.blessing.bcpedge.work;

import android.content.Context;

import androidx.annotation.NonNull;
import androidx.work.Data;
import androidx.work.Worker;
import androidx.work.WorkerParameters;

import com.blessing.bcpedge.storage.EdgeDatabase;

public final class EdgeReconcileWorker extends Worker {
    public EdgeReconcileWorker(@NonNull Context context, @NonNull WorkerParameters params) {
        super(context, params);
    }

    @NonNull
    @Override
    public Result doWork() {
        try {
            int pending = EdgeDatabase.get(getApplicationContext()).edgeDao().countPendingJobs();
            Data out = new Data.Builder()
                    .putInt("pending_jobs", pending)
                    .putBoolean("shadow_foundation_ready", true)
                    .build();
            return Result.success(out);
        } catch (Throwable t) {
            return Result.retry();
        }
    }
}
