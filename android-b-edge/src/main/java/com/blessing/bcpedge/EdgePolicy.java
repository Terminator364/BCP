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
    public static long sentinelStaleMs() { return 10L * 60L * 1000L; }
    public static long sentinelAlertCooldownMs() { return 60L * 60L * 1000L; }

    public static String sentinelState(long nowMs, long lastPcSuccessAt, int consecutiveFailures) {
        if (consecutiveFailures <= 0) return "PC_AVAILABLE";
        if (lastPcSuccessAt <= 0L) return consecutiveFailures >= 2 ? "PC_UNAVAILABLE_RECOVERY" : "PC_TRANSIENT_LOSS";
        long age = Math.max(0L, nowMs - lastPcSuccessAt);
        if (consecutiveFailures >= 2 && age >= sentinelStaleMs()) return "PC_UNAVAILABLE_RECOVERY";
        return "PC_TRANSIENT_LOSS";
    }

    public static boolean sentinelAlertDue(String state, long nowMs, long lastAlertAt) {
        if (!"PC_UNAVAILABLE_RECOVERY".equals(state)) return false;
        return lastAlertAt <= 0L || nowMs < lastAlertAt
                || (nowMs - lastAlertAt) >= sentinelAlertCooldownMs();
    }

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

    public static boolean canAdmitJob(int currentDepth) {
        return currentDepth >= 0 && currentDepth < boundedQueueLimit();
    }

    public static int evidenceRank(String evidenceClass) {
        String e = evidenceClass == null ? "UNVERIFIED" : evidenceClass.trim().toUpperCase();
        switch (e) {
            case "SYSTEM_POLICY": return 7;
            case "USER_DECLARED": return 6;
            case "VALIDATED": return 5;
            case "MACHINE_READBACK":
            case "MACHINE_VERIFIED": return 4;
            case "SOURCE_VERIFIED": return 3;
            case "CACHE": return 2;
            case "MODEL_PROPOSED": return 1;
            case "UNTRUSTED_EXTERNAL":
            case "UNVERIFIED":
            default: return 0;
        }
    }

    public static boolean canReplaceMemory(String scope, String oldEvidence,
                                           boolean oldPinned, String newEvidence) {
        String s = scope == null ? "" : scope.trim().toUpperCase();
        String n = newEvidence == null ? "UNVERIFIED" : newEvidence.trim().toUpperCase();
        if (("USER_MEMORY".equals(s) || "POLICY".equals(s))
                && !("USER_DECLARED".equals(n) || "VALIDATED".equals(n) || "SYSTEM_POLICY".equals(n))) {
            return false;
        }
        if (oldEvidence == null || oldEvidence.trim().isEmpty()) return true;
        int oldRank = evidenceRank(oldEvidence);
        int newRank = evidenceRank(n);
        if (oldPinned && newRank < oldRank) return false;
        return newRank >= oldRank;
    }

    public static boolean isCompletionResult(String result) {
        String r = result == null ? "" : result.trim().toUpperCase();
        return "COMMITTED".equals(r) || "ALREADY_COMMITTED".equals(r)
                || "DONE".equals(r) || "PASS".equals(r) || "SUCCESS".equals(r);
    }

    public static boolean isRemoteQueueAccepted(String result) {
        String r = result == null ? "" : result.trim().toUpperCase();
        return "QUEUED".equals(r) || "ALREADY_QUEUED".equals(r) || "ACCEPTED".equals(r);
    }

    public static int boundedQueueLimit() { return 256; }
    public static int boundedMemoryEntries() { return 256; }
}
