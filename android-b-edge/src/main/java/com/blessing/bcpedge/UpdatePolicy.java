package com.blessing.bcpedge;

import java.util.Locale;

public final class UpdatePolicy {
    private UpdatePolicy() {}

    public static boolean shouldInstall(int currentCode, int latestCode) {
        return currentCode > 0 && latestCode > currentCode;
    }

    public static boolean trustedManifest(String packageId, String expectedPackage,
                                          String certSha256, String expectedCertSha256,
                                          String apkSha256, int versionCode) {
        if (packageId == null || !packageId.equals(expectedPackage)) return false;
        if (certSha256 == null || expectedCertSha256 == null) return false;
        if (!certSha256.toLowerCase(Locale.ROOT)
                .equals(expectedCertSha256.toLowerCase(Locale.ROOT))) return false;
        if (!isSha256(apkSha256)) return false;
        return versionCode > 0;
    }

    public static boolean isSha256(String value) {
        if (value == null || value.length() != 64) return false;
        for (int i = 0; i < value.length(); i++) {
            char c = Character.toLowerCase(value.charAt(i));
            if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) return false;
        }
        return true;
    }
}
