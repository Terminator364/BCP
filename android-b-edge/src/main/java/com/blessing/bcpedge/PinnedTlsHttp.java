package com.blessing.bcpedge;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.EOFException;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.cert.CertificateException;
import java.security.cert.X509Certificate;
import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;

import javax.net.ssl.SSLContext;
import javax.net.ssl.SSLSocket;
import javax.net.ssl.TrustManager;
import javax.net.ssl.X509TrustManager;

/**
 * Minimal certificate-pinned HTTPS/1.1 client for the local BCP PC appliance.
 *
 * This intentionally does not install a trust-all manager. The custom trust
 * manager accepts exactly one SHA-256 leaf-certificate fingerprint that was
 * confirmed/persisted by B-EDGE before any credential-bearing request is sent.
 */
public final class PinnedTlsHttp {
    private static final int MAX_BODY_BYTES = 1_048_576;

    private PinnedTlsHttp() {}

    public static JSONObject requestJson(
            String method,
            String url,
            String body,
            String bearer,
            String idempotencyKey,
            String expectedCertSha256,
            String edgeVersion,
            int connectMs,
            int readMs) throws Exception {
        URL u = new URL(url);
        if (!"https".equalsIgnoreCase(u.getProtocol())) {
            throw new IOException("PINNED_TLS_REQUIRES_HTTPS");
        }
        String host = u.getHost();
        int port = u.getPort() > 0 ? u.getPort() : 443;
        if (host == null || host.isEmpty()) throw new IOException("TLS_HOST_MISSING");
        byte[] expected = decodeSha256(expectedCertSha256);

        SSLContext ssl = SSLContext.getInstance("TLS");
        ssl.init(null, new TrustManager[]{new ExactPinTrustManager(expected)}, null);

        try (SSLSocket socket = (SSLSocket) ssl.getSocketFactory().createSocket()) {
            socket.connect(new InetSocketAddress(host, port), connectMs);
            socket.setSoTimeout(readMs);
            socket.setEnabledProtocols(preferredProtocols(socket.getSupportedProtocols()));
            socket.startHandshake();

            String path = u.getFile();
            if (path == null || path.isEmpty()) path = "/";
            byte[] bodyBytes = body == null ? null : body.getBytes(StandardCharsets.UTF_8);

            LinkedHashMap<String,String> headers = new LinkedHashMap<>();
            headers.put("Host", host + (port == 443 ? "" : ":" + port));
            headers.put("Accept", "application/json");
            headers.put("Connection", "close");
            headers.put("User-Agent", "BCP-Edge/" + (edgeVersion == null ? "" : edgeVersion));
            headers.put("X-BCP-Edge-Version", edgeVersion == null ? "" : edgeVersion);
            if (bearer != null && !bearer.isEmpty()) {
                headers.put("Authorization", "Bearer " + bearer);
            }
            if (idempotencyKey != null && !idempotencyKey.isEmpty()) {
                headers.put("Idempotency-Key", idempotencyKey);
            }
            if (bodyBytes != null) {
                headers.put("Content-Type", "application/json; charset=utf-8");
                headers.put("Content-Length", Integer.toString(bodyBytes.length));
            }

            OutputStream out = socket.getOutputStream();
            StringBuilder head = new StringBuilder();
            head.append(method).append(' ').append(path).append(" HTTP/1.1\r\n");
            for (Map.Entry<String,String> e : headers.entrySet()) {
                head.append(e.getKey()).append(": ").append(e.getValue()).append("\r\n");
            }
            head.append("\r\n");
            out.write(head.toString().getBytes(StandardCharsets.US_ASCII));
            if (bodyBytes != null) out.write(bodyBytes);
            out.flush();

            InputStream in = socket.getInputStream();
            String statusLine = readLine(in, 4096);
            if (statusLine == null || !statusLine.startsWith("HTTP/")) {
                throw new IOException("TLS_HTTP_STATUS_INVALID");
            }
            String[] parts = statusLine.split(" ", 3);
            if (parts.length < 2) throw new IOException("TLS_HTTP_STATUS_INVALID");
            int status = Integer.parseInt(parts[1]);

            int contentLength = -1;
            while (true) {
                String line = readLine(in, 8192);
                if (line == null || line.isEmpty()) break;
                int colon = line.indexOf(':');
                if (colon <= 0) continue;
                String name = line.substring(0, colon).trim().toLowerCase(Locale.ROOT);
                String value = line.substring(colon + 1).trim();
                if ("content-length".equals(name)) {
                    contentLength = Integer.parseInt(value);
                    if (contentLength < 0 || contentLength > MAX_BODY_BYTES) {
                        throw new IOException("TLS_HTTP_BODY_TOO_LARGE");
                    }
                }
                if ("transfer-encoding".equals(name)
                        && value.toLowerCase(Locale.ROOT).contains("chunked")) {
                    throw new IOException("TLS_HTTP_CHUNKED_UNSUPPORTED");
                }
            }

            byte[] raw = contentLength >= 0
                    ? readExactly(in, contentLength)
                    : readToEof(in, MAX_BODY_BYTES);
            String text = new String(raw, StandardCharsets.UTF_8);
            if (status >= 400) throw new IOException("HTTP_" + status + ": " + text);
            return text.isEmpty() ? new JSONObject() : new JSONObject(text);
        }
    }

    static boolean matchesPin(X509Certificate cert, byte[] expected) throws CertificateException {
        try {
            byte[] actual = MessageDigest.getInstance("SHA-256").digest(cert.getEncoded());
            return MessageDigest.isEqual(actual, expected);
        } catch (CertificateException e) {
            throw e;
        } catch (Exception e) {
            throw new CertificateException("PIN_DIGEST_FAILED", e);
        }
    }

    private static final class ExactPinTrustManager implements X509TrustManager {
        private final byte[] expected;

        ExactPinTrustManager(byte[] expected) { this.expected = expected.clone(); }

        @Override public void checkClientTrusted(X509Certificate[] chain, String authType)
                throws CertificateException {
            throw new CertificateException("CLIENT_CERT_NOT_SUPPORTED");
        }

        @Override public void checkServerTrusted(X509Certificate[] chain, String authType)
                throws CertificateException {
            if (chain == null || chain.length == 0 || !matchesPin(chain[0], expected)) {
                throw new CertificateException("PC_TLS_PIN_MISMATCH");
            }
        }

        @Override public X509Certificate[] getAcceptedIssuers() {
            return new X509Certificate[0];
        }
    }

    private static byte[] decodeSha256(String hex) throws IOException {
        String s = hex == null ? "" : hex.trim().toLowerCase(Locale.ROOT);
        if (!s.matches("[0-9a-f]{64}")) throw new IOException("PC_TLS_PIN_MISSING_OR_INVALID");
        byte[] out = new byte[32];
        for (int i = 0; i < out.length; i++) {
            out[i] = (byte) Integer.parseInt(s.substring(i * 2, i * 2 + 2), 16);
        }
        return out;
    }

    private static String[] preferredProtocols(String[] supported) throws IOException {
        java.util.ArrayList<String> out = new java.util.ArrayList<>();
        for (String p : supported) {
            if ("TLSv1.3".equals(p) || "TLSv1.2".equals(p)) out.add(p);
        }
        if (out.isEmpty()) throw new IOException("NO_MODERN_TLS_PROTOCOL");
        return out.toArray(new String[0]);
    }

    private static String readLine(InputStream in, int max) throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        while (out.size() < max) {
            int b = in.read();
            if (b < 0) return out.size() == 0 ? null
                    : out.toString(StandardCharsets.US_ASCII.name());
            if (b == '\n') break;
            if (b != '\r') out.write(b);
        }
        if (out.size() >= max) throw new IOException("TLS_HTTP_LINE_TOO_LONG");
        return out.toString(StandardCharsets.US_ASCII.name());
    }

    private static byte[] readExactly(InputStream in, int length) throws IOException {
        byte[] out = new byte[length];
        int off = 0;
        while (off < length) {
            int n = in.read(out, off, length - off);
            if (n < 0) throw new EOFException("TLS_HTTP_EOF");
            off += n;
        }
        return out;
    }

    private static byte[] readToEof(InputStream in, int max) throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        byte[] buf = new byte[4096];
        int n;
        while ((n = in.read(buf)) >= 0) {
            if (out.size() + n > max) throw new IOException("TLS_HTTP_BODY_TOO_LARGE");
            out.write(buf, 0, n);
        }
        return out.toByteArray();
    }
}
