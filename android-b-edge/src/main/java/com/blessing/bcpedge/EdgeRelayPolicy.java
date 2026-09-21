package com.blessing.bcpedge;

public final class EdgeRelayPolicy {
    public static final int RELAY_PORT = 8876;
    public static final int MAX_CONNECTIONS = 4;
    public static final int CONNECT_TIMEOUT_MS = 8000;
    public static final int TUNNEL_IDLE_TIMEOUT_MS = 80000;
    public static final int REGISTRATION_TTL_SECONDS = 300;

    private EdgeRelayPolicy() {}

    public static boolean isAllowedConnectTarget(String host, int port) {
        if (host == null || port != 443) return false;
        return "api.telegram.org".equalsIgnoreCase(host.trim());
    }

    public static boolean isValidProxyAuthorization(String header, String expectedToken) {
        if (header == null || expectedToken == null || expectedToken.isEmpty()) return false;
        String prefix = "Bearer ";
        if (!header.startsWith(prefix)) return false;
        byte[] a = header.substring(prefix.length()).trim().getBytes(java.nio.charset.StandardCharsets.UTF_8);
        byte[] b = expectedToken.getBytes(java.nio.charset.StandardCharsets.UTF_8);
        return java.security.MessageDigest.isEqual(a, b);
    }

    public static boolean isFreshRegistration(long nowMs, long expiresAtMs) {
        return expiresAtMs > nowMs && expiresAtMs - nowMs <= 10L * 60L * 1000L;
    }
}
