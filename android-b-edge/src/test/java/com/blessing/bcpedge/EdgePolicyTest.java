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

    @Test public void memoryTemperatureIsBounded() {
        assertEquals("HOT", EdgePolicy.temperature(Long.MAX_VALUE, true));
        assertEquals("WARM", EdgePolicy.temperature(1000, false));
        assertEquals("COLD", EdgePolicy.temperature(7L * 60L * 60L * 1000L, false));
        assertTrue(EdgePolicy.boundedQueueLimit() <= 256);
        assertTrue(EdgePolicy.boundedMemoryEntries() <= 256);
    }

    @Test public void reconcileCadenceIsBounded() {
        long now=1_000_000L;
        assertTrue(EdgePolicy.shouldRunSync(now,0,EdgePolicy.defaultReconcileIntervalMs()));
        assertFalse(EdgePolicy.shouldRunSync(now,now-60_000L,EdgePolicy.defaultReconcileIntervalMs()));
        assertTrue(EdgePolicy.shouldRunSync(now,now-EdgePolicy.defaultReconcileIntervalMs(),EdgePolicy.defaultReconcileIntervalMs()));
    }

    @Test public void resourceClassesAreDeterministic() {
        assertEquals("PC_R3",EdgePolicy.resourceClass(true,false,false));
        assertEquals("REMOTE_AI",EdgePolicy.resourceClass(false,true,false));
        assertEquals("EDGE_R2",EdgePolicy.resourceClass(false,false,true));
        assertEquals("EDGE_R1",EdgePolicy.resourceClass(false,false,false));
        assertFalse(EdgePolicy.canRunNow("EDGE_R2",true,false,false,true));
        assertFalse(EdgePolicy.canRunNow("REMOTE_AI",false,false,false,false));
        assertTrue(EdgePolicy.canRunNow("EDGE_R1",false,false,false,false));
    }
}
