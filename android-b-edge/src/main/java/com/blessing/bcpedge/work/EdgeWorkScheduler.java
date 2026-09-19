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
    public static final String UNIQUE_TELEGRAM_PERIODIC = "bcp-telegram-observability-fallback";
    public static final String UNIQUE_TELEGRAM_NOW = "bcp-telegram-observability-now";

    private EdgeWorkScheduler() {}

    public static void schedulePeriodic(Context context) {
        Constraints constraints = new Constraints.Builder()
                .setRequiredNetworkType(NetworkType.NOT_REQUIRED)
                .build();
        PeriodicWorkRequest work = new PeriodicWorkRequest.Builder(
                EdgeReconcileWorker.class, 30, TimeUnit.MINUTES)
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

    public static void scheduleTelegramFallback(Context context) {
        Constraints constraints = new Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build();
        PeriodicWorkRequest work = new PeriodicWorkRequest.Builder(
                TelegramObservabilityWorker.class, 30, TimeUnit.MINUTES)
                .setConstraints(constraints)
                .build();
        WorkManager.getInstance(context.getApplicationContext())
                .enqueueUniquePeriodicWork(
                        UNIQUE_TELEGRAM_PERIODIC,
                        ExistingPeriodicWorkPolicy.UPDATE,
                        work);
    }

    public static void requestTelegramImmediate(Context context) {
        Constraints constraints = new Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build();
        OneTimeWorkRequest work = new OneTimeWorkRequest.Builder(
                TelegramObservabilityWorker.class)
                .setConstraints(constraints)
                .build();
        WorkManager.getInstance(context.getApplicationContext())
                .enqueueUniqueWork(UNIQUE_TELEGRAM_NOW, ExistingWorkPolicy.KEEP, work);
    }
}
