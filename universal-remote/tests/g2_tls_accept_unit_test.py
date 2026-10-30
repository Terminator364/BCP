"""Standalone test of actual TLS listener class extracted verbatim by Python AST.

Runs on ephemeral localhost, generates short-lived self-signed certificate,
never reaches BCP production or the user's local PC.
"""
import ast
import os
from pathlib import Path
import socket,ssl,subprocess,tempfile,threading,time
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler

source=Path(__file__).resolve().parent.parent/"windows"/"g2_tls_bridge.py"
tree=ast.parse(source.read_text("utf8"))
node=next(n for n in tree.body if isinstance(n,ast.ClassDef)
          and n.name=="BoundedTLSHTTPServer")
ns={"ThreadingHTTPServer":ThreadingHTTPServer,"threading":threading,
    "ssl":ssl,"OSError":OSError,"TimeoutError":TimeoutError}
exec(compile(ast.Module(body=[node],type_ignores=[]),str(source),"exec"),ns)
Server=ns["BoundedTLSHTTPServer"]

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        data=b"SECOND_TLS_CLIENT_SUCCEEDED"
        self.send_response(200)
        self.send_header("Content-Length",str(len(data)))
        self.end_headers()
        self.wfile.write(data)
    def log_message(self,*args):pass

with tempfile.TemporaryDirectory(prefix="bcp-tls-") as d:
    cert=Path(d)/"cert.pem"
    key=Path(d)/"key.pem"
    subprocess.run(["openssl","req","-x509","-newkey","rsa:2048",
        "-sha256","-nodes","-days","1","-subj","/CN=BCP Lab",
        "-addext","subjectAltName=IP:127.0.0.1",
        "-keyout",str(key),"-out",str(cert)],
        check=True,capture_output=True,timeout=30)
    ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(str(cert),str(key))
    server=Server(("127.0.0.1",0),Handler,ctx)
    address=server.server_address
    t=threading.Thread(target=server.serve_forever,daemon=True)
    t.start()
    attacker=None
    try:
        attacker=socket.create_connection(address,timeout=2)
        # Client sends incomplete TLS header and waits forever.
        attacker.sendall(b"\x16\x03\x03\x00\x70")
        time.sleep(.15)
        cctx=ssl.create_default_context(cafile=str(cert))
        start=time.monotonic()
        with socket.create_connection(address,timeout=3) as conn:
            conn.settimeout(3)
            with cctx.wrap_socket(conn,server_hostname="127.0.0.1") as secure:
                secure.sendall(b"GET / HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n")
                data=b""
                while 1:
                    block=secure.recv(4096)
                    if not block:break
                    data+=block
        latency=time.monotonic()-start
        assert b"SECOND_TLS_CLIENT_SUCCEEDED" in data
        assert latency<3.0,latency
        print({"schema":"BCP_TLS_ACCEPT_NONBLOCKING_V1","PASS":True,
               "slow_connection_cannot_block_other_client":True,
               "verified_second_client":True,"latency_seconds":round(latency,3)})
    finally:
        if attacker:attacker.close()
        server.shutdown()
        server.server_close()
        t.join(4)
