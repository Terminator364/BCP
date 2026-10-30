"""BCP G4 staging TLS+HMAC network bench. No host-level mutation."""
import hashlib,hmac,json,os,secrets,ssl,time,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(os.environ["LOCALAPPDATA"])/"BCP-Universal-Remote"
key=(Path(os.environ["LOCALAPPDATA"])/"BCP-USB-Rescue/private-state/pairing-key.txt").read_text("utf8").strip().encode()
ctx=ssl.create_default_context(cafile=str(ROOT/"private-state/g2-server.crt"))
base="https://127.0.0.1:8910"
results={}
def signed(path,body=None,valid=True):
    raw=json.dumps(body if body is not None else {},separators=(",",":")).encode("utf8")
    nonce=secrets.token_hex(16)
    stamp=str(int(time.time()))
    material=f"POST\n{path}\n{stamp}\n{nonce}\n{hashlib.sha256(raw).hexdigest()}".encode()
    signature=hmac.new(key,material,hashlib.sha256).hexdigest() if valid else "0"*64
    request=urllib.request.Request(base+path,data=raw,method="POST",headers={
        "Content-Type":"application/json",
        "X-Bridge-Nonce":nonce,"X-Bridge-Time":stamp,"X-Bridge-Signature":signature})
    try:
        with urllib.request.urlopen(request,context=ctx,timeout=8) as res:
            code=res.status;reply=res.read();header=res.headers
    except urllib.error.HTTPError as err:
        code=err.code;reply=err.read();header=err.headers
    expected=hmac.new(key,f"{nonce}\n{code}\n{hashlib.sha256(reply).hexdigest()}".encode(),hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected,header.get("X-Bridge-Signature","")):
        raise AssertionError("BAD_G4_RESPONSE_HMAC")
    return code,json.loads(reply.decode("utf8"))
with urllib.request.urlopen(base+"/health",context=ctx,timeout=8) as r:
    results["tls_health"]=r.status==200 and json.load(r).get("stage")=="G4_STAGING_LOCALHOST_ONLY"
status,cap=signed("/v1/g4/capabilities")
results["authenticated_capabilities"]=status==200 and cap["result"]["authenticated"] is True
status,sysinfo=signed("/v1/g4/system")
results["authenticated_windows_inventory"]=status==200 and "host" in sysinfo["result"]
status,proc=signed("/v1/g4/processes")
results["authenticated_processes"]=status==200 and "items" in proc["result"]
status,directory=signed("/v1/g4/files/list",{"path":str(Path.home())})
results["authorized_home_listing"]=status==200 and "entries" in directory["result"]
status,no=signed("/v1/g4/changes/commit",{"ticket":"0"*32})
results["unapproved_change_denied"]=status==400 and no.get("ok") is False
status,no=signed("/v1/g4/capabilities",valid=False)
results["bad_hmac_denied"]=status==401 and no.get("ok") is False
status,no=signed("/v1/g4/files/read",{"path":str(ROOT/"private-state/g2-server.key")})
results["private_key_read_denied"]=status==400 and no.get("ok") is False
print(json.dumps({"schema":"G4_STAGING_HMAC_TLS_SECURITY_TEST","checks":results,
"PASS":all(results.values()),"public_binding":False,"windows_mutation":False},indent=2))
if not all(results.values()):raise SystemExit(1)
