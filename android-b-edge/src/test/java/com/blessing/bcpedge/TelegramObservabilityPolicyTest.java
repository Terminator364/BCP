package com.blessing.bcpedge;

import org.junit.Test;

import static org.junit.Assert.*;

public class TelegramObservabilityPolicyTest {
    @Test public void parsesReadOnlyCommandsAndArguments() {
        TelegramObservabilityPolicy.Command c =
                TelegramObservabilityPolicy.parse("  /project@BlessingBot   API/BCP ");
        assertEquals(TelegramObservabilityPolicy.Kind.PROJECT, c.kind);
        assertEquals("API/BCP", c.argument);
        assertTrue(TelegramObservabilityPolicy.isReadOnly(c.kind));
    }

    @Test public void rejectsUnknownMutationCommand() {
        TelegramObservabilityPolicy.Command c =
                TelegramObservabilityPolicy.parse("/run deploy");
        assertEquals(TelegramObservabilityPolicy.Kind.UNKNOWN, c.kind);
        assertFalse(TelegramObservabilityPolicy.isReadOnly(c.kind));
    }

    @Test public void chatVisibilityNeverInventsInternalState() {
        assertEquals("OBSERVED_CHAT_ACTION",
                TelegramObservabilityPolicy.chatVisibilityState(true, true, false, false));
        assertEquals("CHAT_PLATFORM_HOLD_REPORTED",
                TelegramObservabilityPolicy.chatVisibilityState(true, false, true, false));
        assertEquals("CHAT_WAITING",
                TelegramObservabilityPolicy.chatVisibilityState(true, false, false, false));
        assertEquals("UNKNOWN_INTERNAL_CHAT_STATE",
                TelegramObservabilityPolicy.chatVisibilityState(false, false, false, false));
    }

    @Test public void clipsTelegramOutput() {
        StringBuilder s = new StringBuilder();
        for (int i = 0; i < 5000; i++) s.append('x');
        assertTrue(TelegramObservabilityPolicy.clipForTelegram(s.toString()).length() <= 3800);
    }
}
