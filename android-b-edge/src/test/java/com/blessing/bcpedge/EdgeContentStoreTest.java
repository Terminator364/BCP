package com.blessing.bcpedge;

import org.junit.Test;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

public class EdgeContentStoreTest {
    private static final long GIB = 1024L * 1024L * 1024L;

    @Test
    public void dedicated64GiBPhoneUsesFarMoreThanLegacy8GiBCapWhenSpaceExists() {
        long q = EdgeContentStore.dedicatedQuotaBytes(64L * GIB, 50L * GIB);
        assertEquals(32L * GIB, q);
    }

    @Test
    public void dedicatedPhoneKeepsEightGiBOrTwentyPercentReserve() {
        long q = EdgeContentStore.dedicatedQuotaBytes(64L * GIB, 30L * GIB);
        assertTrue(q <= 18L * GIB);
        assertTrue(30L * GIB - q >= 12L * GIB);
    }

    @Test
    public void pressureShrinksCacheInsteadOfConsumingLastFreeSpace() {
        long q = EdgeContentStore.dedicatedQuotaBytes(64L * GIB, 4L * GIB);
        assertEquals(1L * GIB, q);
    }
}
