package com.blessing.bcpedge;

import org.junit.Test;

import static org.junit.Assert.assertEquals;

public class ExcellentiaEdgeBridgeTest {
    @Test public void supportedPassDurationsAreExact() {
        int[] values = new int[]{30, 60, 90, 120, 180, 240, 360, 480};
        for (int value : values) {
            assertEquals(value, ExcellentiaEdgeBridge.normalizeMinutes(value));
        }
    }

    @Test public void unsupportedPassDurationFallsBackToThirtyMinutes() {
        assertEquals(30, ExcellentiaEdgeBridge.normalizeMinutes(0));
        assertEquals(30, ExcellentiaEdgeBridge.normalizeMinutes(45));
        assertEquals(30, ExcellentiaEdgeBridge.normalizeMinutes(481));
    }
}
