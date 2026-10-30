package com.blessing.rescuebridge;

/** Pure Java mission gate. Policy is deliberately independent of Android UI. */
public final class MissionPolicy {
    private MissionPolicy() {}
    public static final long MAX_FUTURE_SECONDS = 86400L;
    public static boolean actionAllowed(String action) {
        return "status".equals(action) || "diagnostics".equals(action) ||
               "files".equals(action) || "read".equals(action) ||
               "write".equals(action) || "audit".equals(action);
    }
    public static boolean validExpiry(long nowSeconds, long expiresSeconds) {
        // Signed jobs can have arbitrary clocks; fail closed on expired/far-future missions.
        return expiresSeconds > nowSeconds && expiresSeconds - nowSeconds <= MAX_FUTURE_SECONDS;
    }
    public static boolean safeRelativePath(String name) {
        if (name == null || name.isEmpty() || name.length() > 240 || name.startsWith("/") ||
            name.indexOf('\\') >= 0 || name.indexOf('\u0000') >= 0) return false;
        String[] components=name.split("/",-1);
        for (String c : components) if (c.equals("..") || c.equals(".") || c.isEmpty()) return false;
        return true;
    }
    public static boolean validWriteContent(String content) {
        return content != null && content.getBytes(java.nio.charset.StandardCharsets.UTF_8).length <= 65536;
    }
}
