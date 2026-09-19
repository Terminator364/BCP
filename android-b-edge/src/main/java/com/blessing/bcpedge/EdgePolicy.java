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

    public static String nextState(boolean requiresPc, String mode, String resourceClass,
                                   boolean localResourceAllowed) {
        if (requiresPc && !"PC_AVAILABLE".equals(mode)) return "WAITING_FOR_PC";
        if (!requiresPc && !localResourceAllowed) return "HOLD_RESOURCE";
        return "READY";
    }

    public static boolean resourceAllowed(String resourceClass, boolean lowMemory,
                                          boolean powerSave, int thermalStatus,
                                          int batteryPct, boolean charging,
                                          boolean metered) {
        String rc = resourceClass == null ? "EDGE_R1" : resourceClass;
        if ("EDGE_R0".equals(rc)) return true;
        if (lowMemory || thermalStatus >= 4) return false; // SEVERE+
        if ("EDGE_R1".equals(rc)) return true;
        if ("EDGE_R2".equals(rc)) {
            if (powerSave || thermalStatus >= 3) return false; // MODERATE+
            if (!charging && batteryPct >= 0 && batteryPct < 40) return false;
            return !metered;
        }
        return false;
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

    public static boolean canAdmitJob(int currentDepth) {
        return currentDepth >= 0 && currentDepth < boundedQueueLimit();
    }

    public static int boundedQueueLimit() { return 128; }
    public static int boundedMemoryEntries() { return 96; }
}
