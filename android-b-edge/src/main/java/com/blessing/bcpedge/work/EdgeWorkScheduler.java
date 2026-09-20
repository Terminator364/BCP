package com.blessing.bcpedge.work;

import android.content.Context;

import androidx.work.Constraints;
import androidx.work.ExistingPeriodicWorkPolicy;
import androidx.work.ExistingWorkPolicy;
import androidx.work.NetworkType;
import androidx.work.OneTimeWorkRequest;
import androidx.work.PeriodicWorkRequest;
import androidx.work.WorkManager;

import java.util.concurrent.TimeUnit;

public final class EdgeWorkScheduler {
    public static final String UNIQUE_PERIODIC = "bcp-edge-v2-shadow-reconcile";
    public static final String UNIQUE_NOW = "bcp-edge-v2-shadow-reconcile-now";

    private EdgeWorkScheduler() {}

    public static void schedulePeriodic(Context context) {
        Constraints constraints = new Constraints.Builder()
                .setRequiredNetworkType(NetworkType.NOT_REQUIRED)
                .build();
        PeriodicWorkRequest work = new PeriodicWorkRequest.Builder(
                EdgeReconcileWorker.class, 15, TimeUnit.MINUTES, 5, TimeUnit.MINUTES)
                .setConstraints(constraints)
                .build();
        WorkManager.getInstance(context.getApplicationContext())
                .enqueueUniquePeriodicWork(
                        UNIQUE_PERIODIC,
                        ExistingPeriodicWorkPolicy.UPDATE,
                        work);
    }

    public static void requestImmediate(Context context) {
        OneTimeWorkRequest work = new OneTimeWorkRequest.Builder(EdgeReconcileWorker.class).build();
        WorkManager.getInstance(context.getApplicationContext())
                .enqueueUniqueWork(UNIQUE_NOW, ExistingWorkPolicy.KEEP, work);
    }
}
