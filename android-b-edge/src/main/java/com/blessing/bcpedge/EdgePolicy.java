package com.blessing.bcpedge;

public final class EdgePolicy {
    private EdgePolicy() {}

    public static String mode(boolean pcReachable, boolean pcMemoryPressure) {
        if (!pcReachable) return "EDGE_ONLY";
        return pcMemoryPressure ? "PC_MEMORY_PRESSURE" : "PC_AVAILABLE";
    }

    public static String nextState(boolean requiresPc, String mode) {
        if (requiresPc && !"PC_AVAILABLE".equals(mode)) return "WAITING_FOR_PC";
        return "READY";
    }

    public static String temperature(long ageMs, boolean active) {
        if (active) return "HOT";
        if (ageMs <= 6L * 60L * 60L * 1000L) return "WARM";
        return "COLD";
    }

    public static boolean shouldRunSync(long nowMs, long lastAttemptMs, long minIntervalMs) {
        long bounded = Math.max(30_000L, minIntervalMs);
        if (lastAttemptMs <= 0L || nowMs < lastAttemptMs) return true;
        return (nowMs - lastAttemptMs) >= bounded;
    }

    public static long defaultReconcileIntervalMs() { return 5L * 60L * 1000L; }

    public static String resourceClass(boolean requiresPc, boolean semantic, boolean bulk) {
        if (semantic) return "REMOTE_AI";
        if (requiresPc) return "PC_R3";
        if (bulk) return "EDGE_R2";
        return "EDGE_R1";
    }

    public static boolean canRunNow(String resourceClass, boolean lowMemory,
                                    boolean powerSave, boolean severeThermal,
                                    boolean networkConnected) {
        if ("PC_R3".equals(resourceClass)) return true;
        if ("REMOTE_AI".equals(resourceClass)) return networkConnected && !powerSave && !severeThermal;
        if ("EDGE_R2".equals(resourceClass)) return !lowMemory && !powerSave && !severeThermal;
        return !lowMemory && !severeThermal;
    }

    public static int boundedQueueLimit() { return 256; }
    public static int boundedMemoryEntries() { return 256; }
}
