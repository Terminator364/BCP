package com.blessing.bcpedge.work;

import android.content.Context;

import androidx.annotation.NonNull;
import androidx.work.Worker;
import androidx.work.WorkerParameters;

import com.blessing.bcpedge.TelegramConfigStore;
import com.blessing.bcpedge.TelegramObservabilityPoller;

public final class TelegramObservabilityWorker extends Worker {
    public TelegramObservabilityWorker(@NonNull Context context, @NonNull WorkerParameters params) {
        super(context, params);
    }

    @NonNull
    @Override public Result doWork() {
        TelegramConfigStore config = new TelegramConfigStore(getApplicationContext());
        if (!config.isEnabled() || !config.hasBotToken()) return Result.success();
        try {
            new TelegramObservabilityPoller(getApplicationContext()).pollOnce(1);
            return Result.success();
        } catch (Throwable t) {
            return Result.retry();
        }
    }
}
