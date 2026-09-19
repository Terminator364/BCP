package com.blessing.bcpedge;

import java.util.Locale;

public final class TelegramObservabilityPolicy {
    public enum Kind {
        START, STATUS, PROJECT, JOB, LAST, CI, HOLDS, HELP, UNKNOWN
    }

    public static final class Command {
        public final Kind kind;
        public final String argument;
        Command(Kind kind, String argument) {
            this.kind = kind;
            this.argument = argument == null ? "" : argument;
        }
    }

    private TelegramObservabilityPolicy() {}

    public static Command parse(String raw) {
        if (raw == null) return new Command(Kind.UNKNOWN, "");
        String s = raw.trim();
        if (s.isEmpty()) return new Command(Kind.UNKNOWN, "");
        int space = s.indexOf(' ');
        String command = space < 0 ? s : s.substring(0, space);
        String argument = space < 0 ? "" : s.substring(space + 1).trim();
        int mention = command.indexOf('@');
        if (mention > 0) command = command.substring(0, mention);
        command = command.toLowerCase(Locale.ROOT);
        switch (command) {
            case "/start": return new Command(Kind.START, argument);
            case "/status": return new Command(Kind.STATUS, argument);
            case "/project": return new Command(Kind.PROJECT, argument);
            case "/job": return new Command(Kind.JOB, argument);
            case "/last": return new Command(Kind.LAST, argument);
            case "/ci": return new Command(Kind.CI, argument);
            case "/holds": return new Command(Kind.HOLDS, argument);
            case "/help": return new Command(Kind.HELP, argument);
            default: return new Command(Kind.UNKNOWN, argument);
        }
    }

    public static boolean isReadOnly(Kind kind) {
        return kind == Kind.START || kind == Kind.STATUS || kind == Kind.PROJECT ||
                kind == Kind.JOB || kind == Kind.LAST || kind == Kind.CI ||
                kind == Kind.HOLDS || kind == Kind.HELP;
    }

    public static String chatVisibilityState(boolean dispatchObserved,
                                             boolean completionReceipt,
                                             boolean platformHoldReported,
                                             boolean supportedInternalTelemetry) {
        if (completionReceipt) return "OBSERVED_CHAT_ACTION";
        if (platformHoldReported) return "CHAT_PLATFORM_HOLD_REPORTED";
        if (dispatchObserved) return "CHAT_WAITING";
        if (!supportedInternalTelemetry) return "UNKNOWN_INTERNAL_CHAT_STATE";
        return "UNKNOWN_INTERNAL_CHAT_STATE";
    }

    public static String clipForTelegram(String text) {
        String s = text == null ? "" : text;
        if (s.length() <= 3800) return s;
        return s.substring(0, 3740) + "\n… sortie tronquée; détails disponibles dans BCP.";
    }
}
