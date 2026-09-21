package com.blessing.bcpedge;

public final class EdgeCommunicationPolicy {
    public static final long STARTUP_NOTICE_MIN_MS = 6L * 60L * 60L * 1000L;
    public static final long ALIVE_NOTICE_MS = 90L * 60L * 1000L;

    private EdgeCommunicationPolicy() {}

    public static String chooseNotice(
            long now,
            boolean telegramReady,
            boolean pcReachable,
            String previousPcState,
            String currentNetworkState,
            String previousNetworkState,
            boolean validatedInternet,
            long lastStartupNoticeAt,
            long lastAliveNoticeAt) {
        if (!telegramReady || !validatedInternet) return "";
        if (lastStartupNoticeAt <= 0L || now - lastStartupNoticeAt >= STARTUP_NOTICE_MIN_MS) {
            return "PHONE_NODE_ONLINE";
        }
        String pc = pcReachable ? "REACHABLE" : "UNREACHABLE";
        if (previousPcState != null && !"UNKNOWN".equals(previousPcState) && !previousPcState.equals(pc)) {
            return pcReachable ? "PC_RECONNECTED" : "PC_UNREACHABLE";
        }
        if (previousNetworkState != null && !"UNKNOWN".equals(previousNetworkState)
                && currentNetworkState != null && !previousNetworkState.equals(currentNetworkState)) {
            return "PHONE_UPLINK_RECOVERED";
        }
        if (lastAliveNoticeAt <= 0L || now - lastAliveNoticeAt >= ALIVE_NOTICE_MS) {
            return "PHONE_NODE_ALIVE";
        }
        return "";
    }
}
