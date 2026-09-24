package com.blessing.bcpedge;

public final class EdgeRelayPolicy {
    public static final int RELAY_PORT = 8876;
    public static final int API_TLS_PORT = 8877;
    public static final long PROXY_AUTH_MAX_SKEW_SECONDS = 120;
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

    public static boolean isValidProxyAuthorization(String header, String expectedToken,
                                                    String target, long nowEpochSeconds) {
        if (header == null || expectedToken == null || expectedToken.isEmpty()
                || target == null || target.isEmpty()) return false;
        String prefix = "BCP-HMAC-SHA256 ";
        if (!header.startsWith(prefix)) return false;
        String[] parts = header.substring(prefix.length()).trim().split(":", 3);
        if (parts.length != 3) return false;
        long ts;
        try { ts = Long.parseLong(parts[0]); } catch (Exception e) { return false; }
        if (Math.abs(nowEpochSeconds - ts) > PROXY_AUTH_MAX_SKEW_SECONDS) return false;
        String nonce = parts[1];
        String supplied = parts[2].toLowerCase(java.util.Locale.ROOT);
        if (!nonce.matches("[A-Za-z0-9_-]{16,64}") || !supplied.matches("[0-9a-f]{64}")) return false;
        try {
            String canonical = "CONNECT\\n" + target + "\\n" + ts + "\\n" + nonce;
            javax.crypto.Mac mac = javax.crypto.Mac.getInstance("HmacSHA256");
            mac.init(new javax.crypto.spec.SecretKeySpec(
                    expectedToken.getBytes(java.nio.charset.StandardCharsets.UTF_8),
                    "HmacSHA256"));
            byte[] digest = mac.doFinal(canonical.getBytes(java.nio.charset.StandardCharsets.UTF_8));
            StringBuilder expected = new StringBuilder(64);
            for (byte b : digest) expected.append(String.format(java.util.Locale.ROOT, "%02x", b & 0xff));
            return java.security.MessageDigest.isEqual(
                    supplied.getBytes(java.nio.charset.StandardCharsets.US_ASCII),
                    expected.toString().getBytes(java.nio.charset.StandardCharsets.US_ASCII));
        } catch (Exception e) {
            return false;
        }
    }

    public static String proxyAuthNonce(String header) {
        if (header == null || !header.startsWith("BCP-HMAC-SHA256 ")) return "";
        String[] parts = header.substring("BCP-HMAC-SHA256 ".length()).trim().split(":", 3);
        return parts.length == 3 && parts[1].matches("[A-Za-z0-9_-]{16,64}") ? parts[1] : "";
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
        if ("GET".equalsIgnoreCase(method) && "/v1/node/cd9/status".equals(path)) return true;
        if ("GET".equalsIgnoreCase(method) && "/v1/node/context".equals(path)) return true;
        if ("GET".equalsIgnoreCase(method) && "/v1/node/events".equals(path)) return true;
        if ("GET".equalsIgnoreCase(method) && "/v1/node/mission-steps".equals(path)) return true;
        if ("GET".equalsIgnoreCase(method) && "/v1/node/capability-registry".equals(path)) return true;
        if ("GET".equalsIgnoreCase(method) && "/v1/node/memory-claims".equals(path)) return true;
        if ("POST".equalsIgnoreCase(method) && "/v1/node/events".equals(path)) return true;
        if ("POST".equalsIgnoreCase(method) && "/v1/node/mission-steps".equals(path)) return true;
        if ("POST".equalsIgnoreCase(method) && "/v1/node/mission-steps/state".equals(path)) return true;
        if ("POST".equalsIgnoreCase(method) && "/v1/node/capability-registry".equals(path)) return true;
        if ("POST".equalsIgnoreCase(method) && "/v1/node/memory-claims".equals(path)) return true;
        if ("POST".equalsIgnoreCase(method) && "/v1/node/sync".equals(path)) return true;
        if ("POST".equalsIgnoreCase(method) && "/v1/node/jobs".equals(path)) return true;
        return false;
    }

    public static boolean isFreshRegistration(long nowMs, long expiresAtMs) {
        return expiresAtMs > nowMs && expiresAtMs - nowMs <= 10L * 60L * 1000L;
    }
}
