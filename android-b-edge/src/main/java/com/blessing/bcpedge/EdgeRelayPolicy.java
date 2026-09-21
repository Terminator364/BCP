package com.blessing.bcpedge;

public final class EdgeRelayPolicy {
    public static final int RELAY_PORT = 8876;
    public static final int MAX_CONNECTIONS = 4;
    public static final int CONNECT_TIMEOUT_MS = 8000;
    public static final int TUNNEL_IDLE_TIMEOUT_MS = 80000;
    public static final int REGISTRATION_TTL_SECONDS = 300;
    public static final int HEADER_MAX_BYTES = 16_384;
    public static final int API_BODY_MAX_BYTES = 64 * 1024;

    private EdgeRelayPolicy() {}

    public static boolean isAllowedConnectTarget(String host, int port) {
        if (host == null || port != 443) return false;
        return "api.telegram.org".equalsIgnoreCase(host.trim());
    }

    public static boolean isValidProxyAuthorization(String header, String expectedToken) {
        return isValidBearerAuthorization(header, expectedToken);
    }

    public static boolean isValidBearerAuthorization(String header, String expectedToken) {
        if (header == null || expectedToken == null || expectedToken.isEmpty()) return false;
        String prefix = "Bearer ";
        if (!header.startsWith(prefix)) return false;
        byte[] a = header.substring(prefix.length()).trim().getBytes(java.nio.charset.StandardCharsets.UTF_8);
        byte[] b = expectedToken.getBytes(java.nio.charset.StandardCharsets.UTF_8);
        return java.security.MessageDigest.isEqual(a, b);
    }

    public static boolean isPublicApiPath(String method, String path) {
        return "GET".equalsIgnoreCase(method)
                && ("/health".equals(path) || "/v1/node/capabilities".equals(path));
    }

    public static boolean isAllowedApiPath(String method, String path) {
        if (isPublicApiPath(method, path)) return true;
        if ("GET".equalsIgnoreCase(method) && "/v1/node/status".equals(path)) return true;
        if ("GET".equalsIgnoreCase(method) && "/v1/node/context".equals(path)) return true;
        if ("GET".equalsIgnoreCase(method) && "/v1/node/routes".equals(path)) return true;
        if ("GET".equalsIgnoreCase(method) && "/v1/node/communications".equals(path)) return true;
        if ("POST".equalsIgnoreCase(method) && "/v1/node/sync".equals(path)) return true;
        if ("POST".equalsIgnoreCase(method) && "/v1/node/jobs".equals(path)) return true;
        return false;
    }

    public static boolean isFreshRegistration(long nowMs, long expiresAtMs) {
        return expiresAtMs > nowMs && expiresAtMs - nowMs <= 10L * 60L * 1000L;
    }
}
