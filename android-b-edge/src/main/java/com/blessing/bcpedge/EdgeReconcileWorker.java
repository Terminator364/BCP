package com.blessing.bcpedge;

import android.content.Context;

import androidx.annotation.NonNull;
import androidx.work.Worker;
import androidx.work.WorkerParameters;

/**
 * Compatibility shim for WorkManager rows created by pre-R41 releases.
 * Scheduling policy lives only in work.EdgeWorkScheduler.
 */
@Deprecated
public final class EdgeReconcileWorker extends Worker {
    public EdgeReconcileWorker(@NonNull Context context, @NonNull WorkerParameters params) {
        super(context, params);
    }

    @NonNull
    @Override
    public Result doWork() {
        return com.blessing.bcpedge.work.EdgeReconcileWorker.execute(
                getApplicationContext(),
                getRunAttemptCount(),
                "LEGACY_WORKMANAGER_ROW");
    }
}
