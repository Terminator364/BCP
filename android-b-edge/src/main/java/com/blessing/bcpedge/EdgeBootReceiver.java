package com.blessing.bcpedge;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

import androidx.core.content.ContextCompat;

import com.blessing.bcpedge.work.EdgeWorkScheduler;

/**
 * Restores the dedicated phone node after reboot or in-place app replacement.
 * It never invents a new pairing: the already-paired credential remains the
 * authority and the service will operate in degraded/local mode until a peer
 * is reachable.
 */
public final class EdgeBootReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        if (context == null) return;
        String action = intent == null ? "" : String.valueOf(intent.getAction());
        boolean packageReplaced = Intent.ACTION_MY_PACKAGE_REPLACED.equals(action);
        boolean bootCompleted = Intent.ACTION_BOOT_COMPLETED.equals(action);
        if (packageReplaced || bootCompleted) {
            EdgePermissionManager.setServerModeEnabled(context, true);
        } else if (!EdgePermissionManager.isServerModeEnabled(context)) {
            return;
        }
        try {
            Intent service = new Intent(context, EdgeRelayService.class);
            service.putExtra("boot_reason", action);
            ContextCompat.startForegroundService(context, service);
            new BcpClient(context).recordEvent("EDGE_SERVER_BOOT_START", action);
        } catch (Throwable t) {
            try {
                new BcpClient(context).recordEvent(
                        "EDGE_SERVER_BOOT_DEFERRED",
                        t.getClass().getSimpleName());
            } catch (Throwable ignored) {}
        }
        EdgeWorkScheduler.requestImmediate(context, "BOOT_OR_PACKAGE_REPLACED");
    }
}
