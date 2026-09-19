package com.blessing.bcpedge;

import org.junit.Test;
import static org.junit.Assert.*;

public class EdgePolicyTest {
    @Test public void modesAreDeterministic() {
        assertEquals("EDGE_ONLY", EdgePolicy.mode(false, false));
        assertEquals("PC_MEMORY_PRESSURE", EdgePolicy.mode(true, true));
        assertEquals("PC_AVAILABLE", EdgePolicy.mode(true, false));
    }

    @Test public void heavyJobsWaitOutsideHealthyPcMode() {
        assertEquals("WAITING_FOR_PC", EdgePolicy.nextState(true, "EDGE_ONLY"));
        assertEquals("WAITING_FOR_PC", EdgePolicy.nextState(true, "PC_MEMORY_PRESSURE"));
        assertEquals("READY", EdgePolicy.nextState(true, "PC_AVAILABLE"));
        assertEquals("READY", EdgePolicy.nextState(false, "EDGE_ONLY"));
    }

    @Test public void resourceGovernorFailsClosedForHeavyEdgeWork() {
        assertTrue(EdgePolicy.resourceAllowed("EDGE_R0", true, true, 6, 5, false, true));
        assertFalse(EdgePolicy.resourceAllowed("EDGE_R1", true, false, 0, 90, true, false));
        assertFalse(EdgePolicy.resourceAllowed("EDGE_R2", false, true, 0, 90, true, false));
        assertFalse(EdgePolicy.resourceAllowed("EDGE_R2", false, false, 3, 90, true, false));
        assertFalse(EdgePolicy.resourceAllowed("EDGE_R2", false, false, 0, 20, false, false));
        assertFalse(EdgePolicy.resourceAllowed("EDGE_R2", false, false, 0, 90, true, true));
        assertTrue(EdgePolicy.resourceAllowed("EDGE_R2", false, false, 0, 90, true, false));
        assertEquals("HOLD_RESOURCE",
                EdgePolicy.nextState(false, "EDGE_ONLY", "EDGE_R2", false));
        assertEquals("READY",
                EdgePolicy.nextState(false, "EDGE_ONLY", "EDGE_R1", true));
    }

    @Test public void reconciliationCadenceIsBounded() {
        assertTrue(EdgePolicy.shouldRunSync(1_000_000L, 0L, 300_000L));
        assertFalse(EdgePolicy.shouldRunSync(1_100_000L, 1_000_000L, 300_000L));
        assertTrue(EdgePolicy.shouldRunSync(1_300_000L, 1_000_000L, 300_000L));
        assertTrue(EdgePolicy.shouldRunSync(900_000L, 1_000_000L, 300_000L));
        assertFalse(EdgePolicy.shouldRunSync(1_010_000L, 1_000_000L, 1_000L));
    }

    @Test public void memoryTemperatureIsBounded() {
        assertEquals("HOT", EdgePolicy.temperature(Long.MAX_VALUE, true));
        assertEquals("WARM", EdgePolicy.temperature(1000, false));
        assertEquals("COLD", EdgePolicy.temperature(7L * 60L * 60L * 1000L, false));
        assertTrue(EdgePolicy.boundedQueueLimit() <= 256);
        assertTrue(EdgePolicy.canAdmitJob(0));
        assertTrue(EdgePolicy.canAdmitJob(EdgePolicy.boundedQueueLimit() - 1));
        assertFalse(EdgePolicy.canAdmitJob(EdgePolicy.boundedQueueLimit()));
        assertFalse(EdgePolicy.canAdmitJob(-1));
        assertTrue(EdgePolicy.boundedMemoryEntries() <= 128);
    }
}
