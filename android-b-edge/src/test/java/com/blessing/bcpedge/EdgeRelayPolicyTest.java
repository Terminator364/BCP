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
        assertFalse(EdgeRelayPolicy.isValidProxyAuthorization("Bearer abc124", "abc123"));
        assertFalse(EdgeRelayPolicy.isValidProxyAuthorization("Basic abc123", "abc123"));
        assertFalse(EdgeRelayPolicy.isValidProxyAuthorization(null, "abc123"));
        assertFalse(EdgeRelayPolicy.isValidProxyAuthorization("Bearer abc123", ""));
    }

    @Test public void registrationFreshnessIsBounded() {
        long now = 1_000_000L;
        assertTrue(EdgeRelayPolicy.isFreshRegistration(now, now + 300_000L));
        assertFalse(EdgeRelayPolicy.isFreshRegistration(now, now - 1L));
        assertFalse(EdgeRelayPolicy.isFreshRegistration(now, now + 700_000L));
    }
}
