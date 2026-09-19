package com.blessing.bcpedge;

import org.junit.Test;
import static org.junit.Assert.*;

public class UpdatePolicyTest {
    private static final String PKG = "com.blessing.bcpedge.evergreen";
    private static final String CERT =
            "0baad4749918f1b2430bbbf3f5ddbdb1de4908b017910d67aef2cb987ddeb617";
    private static final String SHA =
            "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";

    @Test public void newerVersionOnly() {
        assertTrue(UpdatePolicy.shouldInstall(100, 101));
        assertFalse(UpdatePolicy.shouldInstall(100, 100));
        assertFalse(UpdatePolicy.shouldInstall(100, 99));
    }

    @Test public void trustedManifestRequiresPinnedIdentity() {
        assertTrue(UpdatePolicy.trustedManifest(PKG, PKG, CERT, CERT, SHA, 100));
        assertFalse(UpdatePolicy.trustedManifest("bad.package", PKG, CERT, CERT, SHA, 100));
        assertFalse(UpdatePolicy.trustedManifest(PKG, PKG, "00", CERT, SHA, 100));
        assertFalse(UpdatePolicy.trustedManifest(PKG, PKG, CERT, CERT, "bad", 100));
        assertFalse(UpdatePolicy.trustedManifest(PKG, PKG, CERT, CERT, SHA, 0));
    }

    @Test public void sha256ShapeIsStrict() {
        assertTrue(UpdatePolicy.isSha256(SHA));
        assertFalse(UpdatePolicy.isSha256(SHA.substring(1)));
        assertFalse(UpdatePolicy.isSha256(SHA.substring(0,63) + "g"));
    }
}
