"""BCP G2 TLS accept-loop stall regression, temporary loopback server only.

One fake client holds a TCP socket open without TLS. A second fully verified
TLS client must still receive an HTTP response promptly. The active BCP
production listener on 8898 is never touched.
"""
from __future__ import annotations
import os
from pathlib import Path
import socket
import ssl
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler

sys.path.insert(0,str(Path(__file__).resolve().parent.parent/"windows"))
from g2_tls_bridge import BoundedTLSHTTPServer
ROOT=Path(os.environ["LOCALAPPDATA"])/"BCP-Universal-Remote"

class Simple(BaseHTTPRequestHandler):
    def do_GET(self):
        data=b"BCP_TLS_ACCEPT_LOOP_OK"
        self.send_response(200)
        self.send_header("Content-Length",str(len(data)))
        self.end_headers()
        self.wfile.write(data)
    def log_message(self,*args):pass

ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ctx.load_cert_chain(str(ROOT/"private-state"/"g2-server.crt"),
                    str(ROOT/"private-state"/"g2-server.key"))
srv=BoundedTLSHTTPServer(("127.0.0.1",0),Simple,ctx)
port=srv.server_address[1]
thread=threading.Thread(target=srv.serve_forever,daemon=True)
thread.start()
raw=None
try:
    raw=socket.create_connection(("127.0.0.1",port),2)
    raw.sendall(b"NOT_A_TLS_HANDSHAKE")  # intentionally stalls handshake
    start=time.monotonic()
    tls=ssl.create_default_context(cafile=str(ROOT/"private-state"/"g2-server.crt"))
    with socket.create_connection(("127.0.0.1",port),3) as remote:
        remote.settimeout(6)
        with tls.wrap_socket(remote,server_hostname="127.0.0.1") as conn:
            conn.sendall(b"GET /health HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n")
            received=b""
            while True:
                part=conn.recv(8192)
                if not part:break
                received+=part
    elapsed=time.monotonic()-start
    assert b"BCP_TLS_ACCEPT_LOOP_OK" in received,"GOOD_CLIENT_NOT_SERVED"
    assert elapsed<5.0,("TLS_HANDSHAKE_BLOCKED_ACCEPT_LOOP",elapsed)
    print({"schema":"BCP_TLS_HANDSHAKE_CONCURRENCY_V1",
           "PASS":True,"good_client_latency_seconds":round(elapsed,3),
           "malformed_client_did_not_stall_accept":True,
           "production_port_touched":False})
finally:
    if raw:raw.close()
    srv.shutdown()
    srv.server_close()
    thread.join(5)
