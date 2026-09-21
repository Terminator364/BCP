package com.blessing.bcpedge;

import org.junit.Test;
import static org.junit.Assert.*;

public class EdgeResourceGovernorTest {
    private boolean defer(String cls, boolean low, int mem, boolean storage,
                          boolean power, int battery, boolean charging,
                          int thermal, boolean internet) {
        return EdgeResourceGovernor.shouldDeferSignals(
                cls, low, mem, storage, power, battery, charging, thermal, internet);
    }

    @Test public void durableTinyWorkSurvivesPressure() {
        assertFalse(defer("EDGE_R0", true, 97, true, true, 5, false, 6, false));
    }

    @Test public void heavierPhoneWorkDefersOnStoragePressure() {
        assertTrue(defer("EDGE_R1", false, 50, true, false, 80, true, 0, true));
        assertTrue(defer("EDGE_R2", false, 50, true, false, 80, true, 0, true));
        assertTrue(defer("REMOTE_AI", false, 50, true, false, 80, true, 0, true));
    }

    @Test public void memoryPressureUsesMeasuredLoadNotOnlyAndroidFlag() {
        assertTrue(defer("EDGE_R1", false, 94, false, false, 80, true, 0, true));
        assertFalse(defer("PC_R3", false, 94, false, false, 80, true, 0, true));
    }

    @Test public void healthyStateAllowsPhoneAndRemoteWork() {
        assertFalse(defer("EDGE_R1", false, 50, false, false, 80, true, 0, true));
        assertFalse(defer("EDGE_R2", false, 50, false, false, 80, true, 0, true));
        assertFalse(defer("REMOTE_AI", false, 50, false, false, 80, true, 0, true));
    }

    @Test public void remoteAiNeedsValidatedInternet() {
        assertTrue(defer("REMOTE_AI", false, 50, false, false, 80, true, 0, false));
        assertFalse(defer("EDGE_R1", false, 50, false, false, 80, true, 0, false));
    }
}
