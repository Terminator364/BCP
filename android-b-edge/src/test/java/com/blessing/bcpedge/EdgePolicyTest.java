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
        assertTrue(EdgePolicy.canAdmitJob(0));
        assertTrue(EdgePolicy.canAdmitJob(EdgePolicy.boundedQueueLimit() - 1));
        assertFalse(EdgePolicy.canAdmitJob(EdgePolicy.boundedQueueLimit()));
        assertFalse(EdgePolicy.canAdmitJob(-1));
        assertTrue(EdgePolicy.boundedMemoryEntries() <= 256);
    }

    @Test public void resourceAdmissionIsDeterministic() {
        assertEquals("PC_R3", EdgePolicy.resourceClass(true,false,false));
        assertEquals("REMOTE_AI", EdgePolicy.resourceClass(false,true,false));
        assertEquals("EDGE_R2", EdgePolicy.resourceClass(false,false,true));
        assertEquals("EDGE_R1", EdgePolicy.resourceClass(false,false,false));
        assertFalse(EdgePolicy.canRunNow("EDGE_R2",true,false,false,true));
        assertFalse(EdgePolicy.canRunNow("REMOTE_AI",false,false,false,false));
        assertTrue(EdgePolicy.canRunNow("EDGE_R1",false,false,false,false));
        assertEquals(5L * 60L * 1000L, EdgePolicy.defaultReconcileIntervalMs());
    }
    @Test public void memoryEvidenceCannotDowngradePinnedFacts() {
        assertTrue(EdgePolicy.canReplaceMemory("PROJECT_MEMORY", null, false, "MODEL_PROPOSED"));
        assertFalse(EdgePolicy.canReplaceMemory("PROJECT_MEMORY", "VALIDATED", true, "MODEL_PROPOSED"));
        assertFalse(EdgePolicy.canReplaceMemory("PROJECT_MEMORY", "MACHINE_READBACK", false, "MODEL_PROPOSED"));
        assertTrue(EdgePolicy.canReplaceMemory("PROJECT_MEMORY", "MACHINE_READBACK", true, "VALIDATED"));
        assertFalse(EdgePolicy.canReplaceMemory("POLICY", null, false, "MODEL_PROPOSED"));
        assertTrue(EdgePolicy.canReplaceMemory("POLICY", null, false, "SYSTEM_POLICY"));
        assertTrue(EdgePolicy.canReplaceMemory("USER_MEMORY", "USER_DECLARED", true, "USER_DECLARED"));
    }

    @Test public void queueAcceptanceIsNotCompletionProof() {
        assertTrue(EdgePolicy.isRemoteQueueAccepted("QUEUED"));
        assertTrue(EdgePolicy.isRemoteQueueAccepted("ALREADY_QUEUED"));
        assertFalse(EdgePolicy.isCompletionResult("QUEUED"));
        assertFalse(EdgePolicy.isCompletionResult("ACCEPTED"));
        assertTrue(EdgePolicy.isCompletionResult("COMMITTED"));
        assertTrue(EdgePolicy.isCompletionResult("ALREADY_COMMITTED"));
        assertTrue(EdgePolicy.isCompletionResult("SUCCESS"));
    }

}
