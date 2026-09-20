package com.blessing.bcpedge.work;

import android.content.Context;

import androidx.work.BackoffPolicy;
import androidx.work.Constraints;
import androidx.work.Data;
import androidx.work.ExistingPeriodicWorkPolicy;
import androidx.work.ExistingWorkPolicy;
import androidx.work.NetworkType;
import androidx.work.OneTimeWorkRequest;
import androidx.work.PeriodicWorkRequest;
import androidx.work.WorkManager;

import java.util.concurrent.TimeUnit;

public final class EdgeWorkScheduler {
    public static final String UNIQUE_PERIODIC = "bcp-edge-v3-reconcile-periodic";
    public static final String UNIQUE_NOW = "bcp-edge-v3-reconcile-now";
    private static final String LEGACY_PERIODIC = "bcp-edge-reconcile";
    private static final String LEGACY_NOW = "bcp-edge-reconcile-now";

    private EdgeWorkScheduler() {}

    private static Constraints connected() {
        return new Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build();
    }

    public static void schedulePeriodic(Context context) {
        WorkManager wm = WorkManager.getInstance(context.getApplicationContext());
        wm.cancelUniqueWork(LEGACY_PERIODIC);
        wm.cancelUniqueWork(LEGACY_NOW);
        PeriodicWorkRequest work = new PeriodicWorkRequest.Builder(
                EdgeReconcileWorker.class, 15, TimeUnit.MINUTES, 5, TimeUnit.MINUTES)
                .setConstraints(connected())
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
                .build();
        wm.enqueueUniquePeriodicWork(
                UNIQUE_PERIODIC,
                ExistingPeriodicWorkPolicy.UPDATE,
                work);
    }

    public static void requestImmediate(Context context) {
        requestImmediate(context, "UNSPECIFIED");
    }

    public static void requestImmediate(Context context, String reason) {
        Data input = new Data.Builder()
                .putString("trigger_reason", reason == null ? "UNSPECIFIED" : reason)
                .build();
        OneTimeWorkRequest work = new OneTimeWorkRequest.Builder(EdgeReconcileWorker.class)
                .setConstraints(connected())
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
                .setInputData(input)
                .build();
        WorkManager.getInstance(context.getApplicationContext())
                .enqueueUniqueWork(UNIQUE_NOW, ExistingWorkPolicy.KEEP, work);
    }
}
