package com.blessing.bcpedge;

import org.junit.Test;

import static org.junit.Assert.*;

public class AdaptiveNetworkRouterTest {
    @Test
    public void wifiTelegramWinsWhenHealthy() {
        AdaptiveNetworkRouter.Snapshot s =
                new AdaptiveNetworkRouter.Snapshot(true, true, false, true);
        assertEquals(
                AdaptiveNetworkRouter.WIFI_TELEGRAM,
                AdaptiveNetworkRouter.chooseControlRoute(s, true, true, true, 500));
    }

    @Test
    public void cellularTelegramUsedOnlyForTinyControlTraffic() {
        AdaptiveNetworkRouter.Snapshot s =
                new AdaptiveNetworkRouter.Snapshot(false, true, true, true);
        assertEquals(
                AdaptiveNetworkRouter.CELLULAR_TELEGRAM,
                AdaptiveNetworkRouter.chooseControlRoute(s, true, false, true, 900));
        assertEquals(
                AdaptiveNetworkRouter.LOCAL_OUTBOX,
                AdaptiveNetworkRouter.chooseControlRoute(
                        s, true, false, true,
                        AdaptiveNetworkRouter.MAX_CELLULAR_CONTROL_BYTES + 1));
    }

    @Test
    public void cellularRequiresExplicitPolicyPermission() {
        AdaptiveNetworkRouter.Snapshot s =
                new AdaptiveNetworkRouter.Snapshot(false, true, true, true);
        assertEquals(
                AdaptiveNetworkRouter.LOCAL_OUTBOX,
                AdaptiveNetworkRouter.chooseControlRoute(s, true, true, false, 500));
    }

    @Test
    public void nexusCanCarryControlWhenTelegramDirectIsDown() {
        AdaptiveNetworkRouter.Snapshot wifi =
                new AdaptiveNetworkRouter.Snapshot(true, false, false, true);
        assertEquals(
                AdaptiveNetworkRouter.WIFI_NEXUS,
                AdaptiveNetworkRouter.chooseControlRoute(wifi, false, true, false, 500));
        AdaptiveNetworkRouter.Snapshot cellular =
                new AdaptiveNetworkRouter.Snapshot(false, true, true, true);
        assertEquals(
                AdaptiveNetworkRouter.CELLULAR_NEXUS,
                AdaptiveNetworkRouter.chooseControlRoute(cellular, false, true, true, 500));
    }

    @Test
    public void bulkClassesNeverQualifyForCellular() {
        assertTrue(AdaptiveNetworkRouter.isCellularEligiblePayload("ALERT", 1024));
        assertTrue(AdaptiveNetworkRouter.isCellularEligiblePayload("ACK", 20));
        assertFalse(AdaptiveNetworkRouter.isCellularEligiblePayload("APK", 1024));
        assertFalse(AdaptiveNetworkRouter.isCellularEligiblePayload("PDF", 1024));
        assertFalse(AdaptiveNetworkRouter.isCellularEligiblePayload(
                "ALERT", AdaptiveNetworkRouter.MAX_CELLULAR_CONTROL_BYTES + 1));
    }
}
