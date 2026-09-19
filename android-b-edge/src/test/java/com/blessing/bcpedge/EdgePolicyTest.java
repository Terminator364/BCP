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
        assertTrue(EdgePolicy.boundedMemoryEntries() <= 128);
    }
}
