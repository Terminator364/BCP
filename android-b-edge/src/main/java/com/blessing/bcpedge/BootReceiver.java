package com.blessing.bcpedge;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

import androidx.core.content.ContextCompat;

import com.blessing.bcpedge.work.EdgeWorkScheduler;

public final class BootReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        String action = intent == null ? "" : String.valueOf(intent.getAction());
        if (!Intent.ACTION_BOOT_COMPLETED.equals(action)
                && !Intent.ACTION_MY_PACKAGE_REPLACED.equals(action)) {
            return;
        }
        EdgeWorkScheduler.schedulePeriodic(context);
        EdgeWorkScheduler.requestImmediate(context, "BOOT_OR_PACKAGE_REPLACED");
        try {
            ContextCompat.startForegroundService(
                    context,
                    new Intent(context, EdgeRelayService.class));
        } catch (Throwable ignored) {}
    }
}
