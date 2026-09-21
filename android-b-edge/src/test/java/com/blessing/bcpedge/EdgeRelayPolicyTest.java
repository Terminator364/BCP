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

    @Test public void pairedBearerMustMatchExactly() {
        assertTrue(EdgeRelayPolicy.isValidProxyAuthorization("Bearer abc123", "abc123"));
        assertTrue(EdgeRelayPolicy.isValidBearerAuthorization("Bearer abc123", "abc123"));
        assertFalse(EdgeRelayPolicy.isValidProxyAuthorization("Bearer abc124", "abc123"));
        assertFalse(EdgeRelayPolicy.isValidBearerAuthorization("Bearer abc124", "abc123"));
        assertFalse(EdgeRelayPolicy.isValidProxyAuthorization("Basic abc123", "abc123"));
        assertFalse(EdgeRelayPolicy.isValidProxyAuthorization(null, "abc123"));
        assertFalse(EdgeRelayPolicy.isValidProxyAuthorization("Bearer abc123", ""));
    }

    @Test public void localApiSurfaceIsBounded() {
        assertTrue(EdgeRelayPolicy.isPublicApiPath("GET", "/health"));
        assertTrue(EdgeRelayPolicy.isPublicApiPath("GET", "/v1/node/capabilities"));
        assertFalse(EdgeRelayPolicy.isPublicApiPath("GET", "/v1/node/status"));

        assertTrue(EdgeRelayPolicy.isAllowedApiPath("GET", "/v1/node/status"));
        assertTrue(EdgeRelayPolicy.isAllowedApiPath("POST", "/v1/node/sync"));
        assertTrue(EdgeRelayPolicy.isAllowedApiPath("POST", "/v1/node/jobs"));
        assertTrue(EdgeRelayPolicy.isAllowedApiPath("GET", "/v1/node/communications"));
        assertTrue(EdgeRelayPolicy.isAllowedApiPath("POST", "/v1/node/communications"));
        assertFalse(EdgeRelayPolicy.isPublicApiPath("GET", "/v1/node/communications"));
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
