package com.blessing.bcpedge;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.os.IBinder;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

public final class TelegramObservabilityService extends Service {
    private static final String CHANNEL_ID = "bcp_telegram_observability";
    private static final int NOTIFICATION_ID = 7041;
    private final AtomicBoolean running = new AtomicBoolean(false);
    private ExecutorService executor;

    public static void start(Context context) {
        Intent i = new Intent(context, TelegramObservabilityService.class);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            context.startForegroundService(i);
        } else {
            context.startService(i);
        }
    }

    public static void stop(Context context) {
        context.stopService(new Intent(context, TelegramObservabilityService.class));
    }

    @Override public void onCreate() {
        super.onCreate();
        ensureChannel();
        startForeground(NOTIFICATION_ID, notification());
        executor = Executors.newSingleThreadExecutor();
    }

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        TelegramConfigStore config = new TelegramConfigStore(this);
        if (!config.isEnabled() || !config.hasBotToken()) {
            stopSelf();
            return START_NOT_STICKY;
        }
        if (running.compareAndSet(false, true)) {
            executor.submit(this::pollLoop);
        }
        return START_STICKY;
    }

    private void pollLoop() {
        long backoffMs = 1500L;
        BcpClient bcp = new BcpClient(this);
        while (running.get()) {
            TelegramConfigStore cfg = new TelegramConfigStore(this);
            if (!cfg.isEnabled() || !cfg.hasBotToken()) break;
            try {
                new TelegramObservabilityPoller(this).pollOnce(25);
                backoffMs = 1500L;
            } catch (Throwable t) {
                bcp.recordEvent("TELEGRAM_POLL_DEFERRED", t.getClass().getSimpleName());
                try {
                    Thread.sleep(backoffMs);
                } catch (InterruptedException ex) {
                    Thread.currentThread().interrupt();
                    break;
                }
                backoffMs = Math.min(60_000L, backoffMs * 2L);
            }
        }
        running.set(false);
        stopSelf();
    }

    private void ensureChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return;
        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        NotificationChannel c = new NotificationChannel(
                CHANNEL_ID,
                "BCP Telegram observability",
                NotificationManager.IMPORTANCE_LOW);
        c.setDescription("Read-only Telegram status bridge for BCP Edge");
        nm.createNotificationChannel(c);
    }

    private Notification notification() {
        Intent launch = new Intent(this, MainActivity.class);
        PendingIntent pi = PendingIntent.getActivity(
                this, 0, launch,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Notification.Builder b = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                ? new Notification.Builder(this, CHANNEL_ID)
                : new Notification.Builder(this);
        return b.setContentTitle("BCP Telegram · lecture seule")
                .setContentText("Observabilité active · aucun contrôle distant")
                .setSmallIcon(android.R.drawable.stat_notify_sync_noanim)
                .setOngoing(true)
                .setContentIntent(pi)
                .build();
    }

    @Override public void onDestroy() {
        running.set(false);
        if (executor != null) executor.shutdownNow();
        super.onDestroy();
    }

    @Override public IBinder onBind(Intent intent) {
        return null;
    }
}
