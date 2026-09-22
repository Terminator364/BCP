package com.blessing.bcpedge;

import org.junit.Test;

import static org.junit.Assert.*;

public class EdgeRelayPolicyTest {
    @Test public void targetAllowlistIsStrict() {
        assertTrue(EdgeRelayPolicy.isAllowedConnectTarget("api.telegram.org", 443));
        assertTrue(EdgeRelayPolicy.isAllowedConnectTarget("API.TELEGRAM.ORG", 443));
        assertFalse(EdgeRelayPolicy.isAllowedConnectTarget("api.telegram.org", 80));
        assertFalse(EdgeRelayPolicy.isAllowedConnectTarget("github.com", 443));
        assertFalse(EdgeRelayPolicy.isAllowedConnectTarget("evil.example", 443));
        assertFalse(EdgeRelayPolicy.isAllowedConnectTarget(null, 443));
    }

    @Test public void privateApiBearerMustMatchExactly() {
        assertTrue(EdgeRelayPolicy.isValidBearerAuthorization("Bearer abc123", "abc123"));
        assertFalse(EdgeRelayPolicy.isValidBearerAuthorization("Bearer abc124", "abc123"));
        assertFalse(EdgeRelayPolicy.isValidBearerAuthorization("Basic abc123", "abc123"));
    }

    @Test public void proxyAuthUsesFreshHmacAndRejectsBearer() throws Exception {
        long now = 2_000_000L;
        String token = "paired-secret";
        String target = "api.telegram.org:443";
        String nonce = "abcdefghijklmnop";
        String canonical = "CONNECT\\n" + target + "\\n" + now + "\\n" + nonce;
        javax.crypto.Mac mac = javax.crypto.Mac.getInstance("HmacSHA256");
        mac.init(new javax.crypto.spec.SecretKeySpec(
                token.getBytes(java.nio.charset.StandardCharsets.UTF_8), "HmacSHA256"));
        byte[] digest = mac.doFinal(canonical.getBytes(java.nio.charset.StandardCharsets.UTF_8));
        StringBuilder sig = new StringBuilder();
        for (byte b : digest) sig.append(String.format(java.util.Locale.ROOT, "%02x", b & 0xff));
        String header = "BCP-HMAC-SHA256 " + now + ":" + nonce + ":" + sig;

        assertTrue(EdgeRelayPolicy.isValidProxyAuthorization(header, token, target, now));
        assertEquals(nonce, EdgeRelayPolicy.proxyAuthNonce(header));
        assertFalse(EdgeRelayPolicy.isValidProxyAuthorization(header, token, target, now + 121));
        assertFalse(EdgeRelayPolicy.isValidProxyAuthorization(header, "wrong", target, now));
        assertFalse(EdgeRelayPolicy.isValidProxyAuthorization("Bearer " + token, token, target, now));
    }

    @Test public void localApiSurfaceIsBounded() {
        assertTrue(EdgeRelayPolicy.isPublicApiPath("GET", "/health"));
        assertTrue(EdgeRelayPolicy.isPublicApiPath("GET", "/v1/node/capabilities"));
        assertFalse(EdgeRelayPolicy.isPublicApiPath("GET", "/v1/node/status"));

        assertTrue(EdgeRelayPolicy.isAllowedApiPath("GET", "/v1/node/status"));
        assertTrue(EdgeRelayPolicy.isAllowedApiPath("POST", "/v1/node/sync"));
        assertTrue(EdgeRelayPolicy.isAllowedApiPath("POST", "/v1/node/jobs"));
        assertFalse(EdgeRelayPolicy.isAllowedApiPath("POST", "/v1/node/shell"));
        assertFalse(EdgeRelayPolicy.isAllowedApiPath("GET", "/etc/passwd"));
    }

    @Test public void registrationFreshnessIsBounded() {
        long now = 1_000_000L;
        assertTrue(EdgeRelayPolicy.isFreshRegistration(now, now + 300_000L));
        assertFalse(EdgeRelayPolicy.isFreshRegistration(now, now - 1L));
        assertFalse(EdgeRelayPolicy.isFreshRegistration(now, now + 700_000L));
    }
}
