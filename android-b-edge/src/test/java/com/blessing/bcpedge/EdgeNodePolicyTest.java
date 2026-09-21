package com.blessing.bcpedge;

import org.junit.Test;

import static org.junit.Assert.*;

public class EdgeNodePolicyTest {
    @Test public void authorizationIsStrict() {
        assertTrue(EdgeNodePolicy.isValidAuthorization("Bearer secret-token-123", "secret-token-123"));
        assertFalse(EdgeNodePolicy.isValidAuthorization("Bearer wrong", "secret-token-123"));
        assertFalse(EdgeNodePolicy.isValidAuthorization(null, "secret-token-123"));
        assertFalse(EdgeNodePolicy.isValidAuthorization("Basic abc", "secret-token-123"));
    }

    @Test public void jobKindAndIdempotencyAreBounded() {
        assertTrue(EdgeNodePolicy.isSafeJobKind("TELEGRAM_SEND"));
        assertTrue(EdgeNodePolicy.isSafeJobKind("COMMUNICATION_EVENT"));
        assertFalse(EdgeNodePolicy.isSafeJobKind("../shell"));
        assertFalse(EdgeNodePolicy.isSafeJobKind(""));
        assertTrue(EdgeNodePolicy.isSafeIdempotencyKey("edge-msg-abcdef123456"));
        assertFalse(EdgeNodePolicy.isSafeIdempotencyKey("short"));
        assertFalse(EdgeNodePolicy.isSafeIdempotencyKey("bad key with spaces"));
    }

    @Test public void prioritiesAreBounded() {
        assertEquals(0, EdgeNodePolicy.boundedPriority(-5));
        assertEquals(55, EdgeNodePolicy.boundedPriority(55));
        assertEquals(100, EdgeNodePolicy.boundedPriority(500));
    }
    @Test public void projectIdsAreBounded() {
        assertTrue(EdgeNodePolicy.isSafeProjectId("API_BCP"));
        assertTrue(EdgeNodePolicy.isSafeProjectId("buildhub/main"));
        assertFalse(EdgeNodePolicy.isSafeProjectId(""));
        assertFalse(EdgeNodePolicy.isSafeProjectId("../../bad project"));
    }
}
