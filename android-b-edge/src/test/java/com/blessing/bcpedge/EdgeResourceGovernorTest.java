package com.blessing.bcpedge;

import org.json.JSONObject;
import org.junit.Test;

import static org.junit.Assert.*;

public class EdgeResourceGovernorTest {
    private JSONObject base() throws Exception {
        return new JSONObject()
                .put("low_memory", false)
                .put("memory_load_percent", 50)
                .put("storage_pressure", false)
                .put("power_save", false)
                .put("battery_pct", 80)
                .put("charging", true)
                .put("thermal_status", 0)
                .put("internet_validated", true);
    }

    @Test public void durableTinyWorkSurvivesPressure() throws Exception {
        JSONObject s = base()
                .put("low_memory", true)
                .put("memory_load_percent", 97)
                .put("storage_pressure", true)
                .put("power_save", true);
        assertFalse(EdgeResourceGovernor.shouldDefer("EDGE_R0", s));
    }

    @Test public void heavierPhoneWorkDefersOnStoragePressure() throws Exception {
        JSONObject s = base().put("storage_pressure", true);
        assertTrue(EdgeResourceGovernor.shouldDefer("EDGE_R1", s));
        assertTrue(EdgeResourceGovernor.shouldDefer("EDGE_R2", s));
        assertTrue(EdgeResourceGovernor.shouldDefer("REMOTE_AI", s));
    }

    @Test public void memoryPressureUsesMeasuredLoadNotOnlyAndroidFlag() throws Exception {
        JSONObject s = base().put("memory_load_percent", 94);
        assertTrue(EdgeResourceGovernor.shouldDefer("EDGE_R1", s));
        assertFalse(EdgeResourceGovernor.shouldDefer("PC_R3", s));
    }

    @Test public void healthyStateAllowsPhoneAndRemoteWork() throws Exception {
        JSONObject s = base();
        assertFalse(EdgeResourceGovernor.shouldDefer("EDGE_R1", s));
        assertFalse(EdgeResourceGovernor.shouldDefer("EDGE_R2", s));
        assertFalse(EdgeResourceGovernor.shouldDefer("REMOTE_AI", s));
    }

    @Test public void remoteAiNeedsValidatedInternet() throws Exception {
        JSONObject s = base().put("internet_validated", false);
        assertTrue(EdgeResourceGovernor.shouldDefer("REMOTE_AI", s));
        assertFalse(EdgeResourceGovernor.shouldDefer("EDGE_R1", s));
    }
}
