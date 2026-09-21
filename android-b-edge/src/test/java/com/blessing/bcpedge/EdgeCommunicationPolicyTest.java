package com.blessing.bcpedge;

import org.junit.Test;
import static org.junit.Assert.*;

public class EdgeCommunicationPolicyTest {
    @Test public void noInternetMeansNoNotice() {
        assertEquals("", EdgeCommunicationPolicy.chooseNotice(
                10_000L, true, true, "REACHABLE", "OFFLINE", "ONLINE_WIFI",
                false, 1L, 1L));
    }

    @Test public void startupNoticeWinsWhenDue() {
        assertEquals("PHONE_NODE_ONLINE", EdgeCommunicationPolicy.chooseNotice(
                100_000L, true, false, "UNKNOWN", "ONLINE_WIFI", "UNKNOWN",
                true, 0L, 0L));
    }

    @Test public void detectsPcLossWithoutWaitingForPcWorker() {
        long now = 30_000_000L;
        assertEquals("PC_UNREACHABLE", EdgeCommunicationPolicy.chooseNotice(
                now, true, false, "REACHABLE", "ONLINE_WIFI", "ONLINE_WIFI",
                true, now - 1_000L, now - 1_000L));
    }

    @Test public void detectsPcRecovery() {
        long now = 30_000_000L;
        assertEquals("PC_RECONNECTED", EdgeCommunicationPolicy.chooseNotice(
                now, true, true, "UNREACHABLE", "ONLINE_WIFI", "ONLINE_WIFI",
                true, now - 1_000L, now - 1_000L));
    }

    @Test public void sparseAliveDoesNotSpam() {
        long now = 30_000_000L;
        assertEquals("", EdgeCommunicationPolicy.chooseNotice(
                now, true, true, "REACHABLE", "ONLINE_WIFI", "ONLINE_WIFI",
                true, now - 1_000L, now - 1_000L));
        assertEquals("PHONE_NODE_ALIVE", EdgeCommunicationPolicy.chooseNotice(
                now, true, true, "REACHABLE", "ONLINE_WIFI", "ONLINE_WIFI",
                true, now - 1_000L, now - EdgeCommunicationPolicy.ALIVE_NOTICE_MS - 1L));
    }
}
