package com.blessing.bcpedge;

import android.app.Application;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;

import com.blessing.bcpedge.work.EdgeWorkScheduler;

import java.util.concurrent.atomic.AtomicLong;

public final class BcpEdgeApplication extends Application {
    private static final long MIN_REENTRY_TRIGGER_MS = 15_000L;
    private final AtomicLong lastReentryTriggerAt = new AtomicLong(0L);

    @Override
    public void onCreate() {
        super.onCreate();
        EdgeWorkScheduler.schedulePeriodic(this);
        registerNetworkReturnMonitor();
    }

    private void registerNetworkReturnMonitor() {
        ConnectivityManager cm = getSystemService(ConnectivityManager.class);
        if (cm == null) return;
        cm.registerDefaultNetworkCallback(new ConnectivityManager.NetworkCallback() {
            @Override
            public void onAvailable(Network network) {
                EdgeWorkScheduler.requestImmediate(BcpEdgeApplication.this, "NETWORK_AVAILABLE");
            }

            @Override
            public void onCapabilitiesChanged(Network network, NetworkCapabilities caps) {
                if (caps == null) return;
                boolean internet = caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET);
                boolean validated = caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED);
                boolean localReachable = caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)
                        || caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET)
                        || caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR);
                if (!localReachable && !internet) return;

                long now = System.currentTimeMillis();
                long previous = lastReentryTriggerAt.get();
                if (previous > 0L && now - previous < MIN_REENTRY_TRIGGER_MS) return;
                if (!lastReentryTriggerAt.compareAndSet(previous, now)) return;
                String reason = validated ? "NETWORK_VALIDATED_RETURN" : "LOCAL_NETWORK_CHANGE";
                EdgeWorkScheduler.requestImmediate(BcpEdgeApplication.this, reason);
            }
        });
    }
}
