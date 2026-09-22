package com.blessing.bcpedge;

import android.content.Context;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;

import java.math.BigInteger;
import java.security.KeyPairGenerator;
import java.security.KeyStore;
import java.security.MessageDigest;
import java.security.cert.Certificate;
import java.util.Calendar;
import java.util.Locale;

import javax.net.ssl.KeyManagerFactory;
import javax.net.ssl.SSLContext;
import javax.net.ssl.SSLServerSocket;

/**
 * Persistent B-EDGE TLS identity.
 *
 * The private RSA key is generated inside AndroidKeyStore and is never exported.
 * The self-signed certificate is intentionally local: peers trust it only after
 * comparing its SHA-256 fingerprint with the fingerprint carried by the paired
 * BCP control-plane registration.
 */
public final class EdgeTlsIdentity {
    private static final String ALIAS = "bcp-edge-tls-v3";
    private static final String KEYSTORE = "AndroidKeyStore";

    private EdgeTlsIdentity() {}

    public static SSLServerSocket createServerSocket(Context context, int port) throws Exception {
        ensureKey();
        KeyStore ks = KeyStore.getInstance(KEYSTORE);
        ks.load(null);
        KeyManagerFactory kmf = KeyManagerFactory.getInstance(
                KeyManagerFactory.getDefaultAlgorithm());
        kmf.init(ks, null);

        SSLContext ssl = SSLContext.getInstance("TLS");
        ssl.init(kmf.getKeyManagers(), null, null);
        SSLServerSocket server = (SSLServerSocket) ssl.getServerSocketFactory()
                .createServerSocket(port);
        server.setReuseAddress(true);
        server.setEnabledProtocols(preferredProtocols(server.getSupportedProtocols()));
        return server;
    }

    public static String certificateSha256(Context context) throws Exception {
        ensureKey();
        KeyStore ks = KeyStore.getInstance(KEYSTORE);
        ks.load(null);
        Certificate cert = ks.getCertificate(ALIAS);
        if (cert == null) throw new IllegalStateException("EDGE_TLS_CERTIFICATE_MISSING");
        byte[] digest = MessageDigest.getInstance("SHA-256").digest(cert.getEncoded());
        StringBuilder out = new StringBuilder(digest.length * 2);
        for (byte b : digest) out.append(String.format(Locale.ROOT, "%02x", b & 0xff));
        return out.toString();
    }

    private static synchronized void ensureKey() throws Exception {
        KeyStore ks = KeyStore.getInstance(KEYSTORE);
        ks.load(null);
        if (ks.containsAlias(ALIAS) && ks.getCertificate(ALIAS) != null) return;

        Calendar start = Calendar.getInstance();
        start.add(Calendar.DAY_OF_YEAR, -1);
        Calendar end = Calendar.getInstance();
        end.add(Calendar.YEAR, 15);

        KeyPairGenerator gen = KeyPairGenerator.getInstance(
                KeyProperties.KEY_ALGORITHM_RSA, KEYSTORE);
        gen.initialize(new KeyGenParameterSpec.Builder(
                ALIAS, KeyProperties.PURPOSE_SIGN
                        | KeyProperties.PURPOSE_VERIFY
                        | KeyProperties.PURPOSE_DECRYPT)
                .setKeySize(2048)
                .setDigests(
                        KeyProperties.DIGEST_NONE,
                        KeyProperties.DIGEST_SHA256,
                        KeyProperties.DIGEST_SHA384,
                        KeyProperties.DIGEST_SHA512)
                .setSignaturePaddings(
                        KeyProperties.SIGNATURE_PADDING_RSA_PKCS1,
                        KeyProperties.SIGNATURE_PADDING_RSA_PSS)
                .setEncryptionPaddings(
                        KeyProperties.ENCRYPTION_PADDING_NONE,
                        KeyProperties.ENCRYPTION_PADDING_RSA_PKCS1)
                .setCertificateSubject(new javax.security.auth.x500.X500Principal("CN=BCP-EDGE"))
                .setCertificateSerialNumber(new BigInteger(128, new java.security.SecureRandom()).abs())
                .setCertificateNotBefore(start.getTime())
                .setCertificateNotAfter(end.getTime())
                .build());
        gen.generateKeyPair();
    }

    private static String[] preferredProtocols(String[] supported) {
        java.util.List<String> out = new java.util.ArrayList<>();
        for (String p : supported) {
            if ("TLSv1.3".equals(p) || "TLSv1.2".equals(p)) out.add(p);
        }
        if (out.isEmpty()) throw new IllegalStateException("NO_MODERN_TLS_PROTOCOL");
        return out.toArray(new String[0]);
    }
}
