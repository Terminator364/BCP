"""BCP G2 fast safe starter: no WMI, Get-NetTCPConnection or PnP scans.

Works under the signed-in Windows user without elevation; retains local TLS,
existing keys, original G2 service source and native Tailscale Serve.
"""
from __future__ import annotations
import ipaddress,json,os,re,socket,subprocess,sys,time
from pathlib import Path

ROOT=Path(os.environ["LOCALAPPDATA"])/"BCP-Universal-Remote"
STATE=ROOT/"state"
BRIDGE=ROOT/"g2_tls_bridge.py"
JOURNAL=STATE/"g2-fast-start.json"
LEGACY=STATE/"g2-launch.json"

def log(status,details):
    STATE.mkdir(parents=True,exist_ok=True)
    obj={"schema":"BCP_G2_FAST_START_V1","status":status,
         "utc":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),
         "details":details}
    tmp=JOURNAL.with_name(JOURNAL.name+".new")
    tmp.write_text(json.dumps(obj,sort_keys=True),encoding="utf8")
    os.replace(tmp,JOURNAL)
    print("BCP_G2_FAST="+status+" "+details,flush=True)

def listener():
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as s:
        s.settimeout(.6)
        return s.connect_ex(("127.0.0.1",8898))==0

def local_ip(ip):
    try:
        value=ipaddress.ip_address(ip)
        permitted=(
            ipaddress.ip_network("127.0.0.0/8"),
            ipaddress.ip_network("10.0.0.0/8"),
            ipaddress.ip_network("172.16.0.0/12"),
            ipaddress.ip_network("192.168.0.0/16"),
            ipaddress.ip_network("100.64.0.0/10"))
        if value.version!=4 or not any(value in net for net in permitted):
            return False
        with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as s:
            s.bind((str(value),0))
        return True
    except (OSError,ValueError):return False

def previous_addresses():
    try:
        info=json.loads(LEGACY.read_text("utf-8-sig"))
        return re.findall(r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?!\d)",
               str(info.get("detail","")))
    except (OSError,ValueError):return []

def wifi_addresses():
    # ipconfig is bounded; no network configuration is modified.
    try:
        result=subprocess.run(["ipconfig"],capture_output=True,text=True,
                              errors="replace",timeout=4,
                              creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        if result.returncode!=0:return []
    except (OSError,subprocess.TimeoutExpired):return []
    # IPv4 only; binding verifies that an address really belongs to MBMPC.
    return re.findall(r"(?:IPv4[^:\n]*:|IPv4[^:\n]*\.\s*:)[^\d]*(\d{1,3}(?:\.\d{1,3}){3})",
                      result.stdout,re.IGNORECASE)

def main():
    if not BRIDGE.is_file():
        log("FAIL","bridge source absent");return 2
    if listener():
        log("ALREADY_RUNNING","127.0.0.1:8898 reachable");return 0
    exe=Path(sys.executable)
    pythonw=exe.with_name("pythonw.exe")
    if not pythonw.is_file():
        log("FAIL","pythonw executable absent");return 3
    addresses=["127.0.0.1"]
    for ip in previous_addresses()+wifi_addresses():
        if ip not in addresses and local_ip(ip):addresses.append(ip)
    argv=[str(pythonw),str(BRIDGE)]
    for ip in addresses:argv.extend(["--bind",ip])
    flags=getattr(subprocess,"CREATE_NO_WINDOW",0)
    try:
        process=subprocess.Popen(argv,cwd=str(ROOT),stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                                creationflags=flags)
    except OSError as exc:
        log("FAIL",type(exc).__name__);return 4
    for i in range(16):
        if listener():
            log("STARTED","pid="+str(process.pid)+";bindings="+",".join(addresses))
            return 0
        if process.poll() is not None:
            log("FAILED_EXIT","code="+str(process.returncode));return 5
        time.sleep(.45)
    log("PENDING","pid="+str(process.pid)+";bindings="+",".join(addresses))
    return 0

if __name__=="__main__":raise SystemExit(main())
