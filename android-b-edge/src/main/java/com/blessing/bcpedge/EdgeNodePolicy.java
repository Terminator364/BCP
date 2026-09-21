package com.blessing.bcpedge;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

public final class EdgeNodePolicy {
    public static final int NODE_PORT = 8877;
    public static final int MAX_CONNECTIONS = 4;
    public static final int MAX_HEADER_BYTES = 16 * 1024;
    public static final int MAX_BODY_BYTES = 32 * 1024;
    public static final int SOCKET_TIMEOUT_MS = 8000;

    private EdgeNodePolicy() {}

    public static boolean isValidAuthorization(String header, String expectedToken) {
        if (header == null || expectedToken == null || expectedToken.isEmpty()) return false;
        if (!header.startsWith("Bearer ")) return false;
        byte[] a = header.substring(7).trim().getBytes(StandardCharsets.UTF_8);
        byte[] b = expectedToken.getBytes(StandardCharsets.UTF_8);
        return MessageDigest.isEqual(a, b);
    }

    public static boolean isSafeJobKind(String kind) {
        if (kind == null) return false;
        String k = kind.trim();
        return k.matches("[A-Za-z0-9_.:-]{1,80}");
    }

    public static boolean isSafeIdempotencyKey(String key) {
        if (key == null) return false;
        String k = key.trim();
        return k.length() >= 8 && k.length() <= 160 && k.matches("[A-Za-z0-9_.:@/+-]+");
    }

    public static int boundedPriority(int value) {
        return Math.max(0, Math.min(100, value));
    }
}
