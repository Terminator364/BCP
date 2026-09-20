from __future__ import annotations
import argparse, ctypes, hashlib, json, os, shutil, subprocess, sys, time, zipfile
from pathlib import Path

VERSION="6.0.34"; SEQUENCE=6034
PACKAGE="Tunnel_PC_G6_6.0.34_2003_RECOVERY_DRIVEFS_RESULT_HOTFIX.zip"
SHA256="53dbc2e38bf7d1759b95195954189e974cb0489215def0c6d85411a285880e26"
RUNNER_MEMBER="payload/tools/recovery_update_runner.py"

def sha256(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()

def read_json(path:Path):
    try:return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:return {}

def write_json(path:Path,obj:dict):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+".tmp")
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding="utf-8")
    os.replace(tmp,path)

def free_memory_mb()->int:
    if os.name=="nt":
        class M(ctypes.Structure):
            _fields_=[("dwLength",ctypes.c_ulong),("dwMemoryLoad",ctypes.c_ulong),
            ("ullTotalPhys",ctypes.c_ulonglong),("ullAvailPhys",ctypes.c_ulonglong),
            ("ullTotalPageFile",ctypes.c_ulonglong),("ullAvailPageFile",ctypes.c_ulonglong),
            ("ullTotalVirtual",ctypes.c_ulonglong),("ullAvailVirtual",ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual",ctypes.c_ulonglong)]
        m=M();m.dwLength=ctypes.sizeof(M)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)): return int(m.ullAvailPhys//(1024*1024))
    try:return int(os.sysconf("SC_AVPHYS_PAGES")*os.sysconf("SC_PAGE_SIZE")//(1024*1024))
    except Exception:return 512

def pid_alive(pid:int)->bool:
    if pid<=0:return False
    if os.name=="nt":
        h=ctypes.windll.kernel32.OpenProcess(0x1000,False,int(pid))
        if not h:return False
        ctypes.windll.kernel32.CloseHandle(h);return True
    try:os.kill(pid,0);return True
    except Exception:return False

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--package",default="")
    ap.add_argument("--install-root",default="")
    ap.add_argument("--python",dest="python_path",default="")
    ap.add_argument("--work-root",default="")
    ap.add_argument("--expected-sha",default="")
    ap.add_argument("--target-version",default="")
    ap.add_argument("--target-sequence",type=int,default=0)
    ap.add_argument("--test-mode",action="store_true")
    ap.add_argument("--preflight-only",action="store_true")
    ap.add_argument("--free-memory-override-mb",type=int,default=-1)
    ap.add_argument("--min-free-memory-mb",type=int,default=160)
    ap.add_argument("--min-free-disk-mb",type=int,default=80)
    a=ap.parse_args()

    local=Path(os.environ.get("LOCALAPPDATA",str(Path.home())))
    if not a.test_mode:
        a.package=a.package or str(Path(__file__).with_name(PACKAGE))
        a.install_root=str(local/"Tunnel_PC_G4")
        a.python_path=str(Path(a.install_root)/"runtime"/"python.exe")
        a.work_root=str(local/"ChatGPT_ManagedApps"/"offline_recovery"/"6034")
        a.expected_sha=SHA256;a.target_version=VERSION;a.target_sequence=SEQUENCE
    if not all([a.package,a.install_root,a.python_path,a.work_root,a.expected_sha,a.target_version]) or a.target_sequence<1:
        print("HOLD PARAMETERS_INCOMPLETE");return 20

    package=Path(a.package).resolve();root=Path(a.install_root).resolve()
    py=Path(a.python_path).resolve();work=Path(a.work_root).resolve()
    if not package.is_file(): print("HOLD PACKAGE_MISSING");return 20
    if not root.is_dir(): print("HOLD INSTALL_ROOT_MISSING");return 20
    if not py.is_file(): print("HOLD PYTHON_RUNTIME_MISSING");return 20

    actual=sha256(package).lower()
    if actual!=a.expected_sha.lower():
        print("HOLD PACKAGE_SHA256_MISMATCH",actual);return 20

    active=read_json(root/"state"/"active_release.json")
    active_seq=int(active.get("sequence") or 0)
    if active_seq>a.target_sequence:
        print("HOLD TARGET_SUPERSEDED",active_seq);return 20
    if active_seq==a.target_sequence and str(active.get("version") or "")==a.target_version:
        print("OFFLINE_RECOVERY_ALREADY_ACTIVE",a.target_version,a.target_sequence);return 0

    free=a.free_memory_override_mb if a.free_memory_override_mb>=0 else free_memory_mb()
    if free<a.min_free_memory_mb:
        print("HOLD LOW_MEMORY_PREMUTATION",free);return 20
    try:
        disk=shutil.disk_usage(work.parent if work.parent.exists() else local)
        if disk.free<a.min_free_disk_mb*1024*1024:
            print("HOLD LOW_DISK_PREMUTATION",disk.free//(1024*1024));return 20
    except Exception:
        if not a.test_mode:
            print("HOLD DISK_PREFLIGHT_FAILED");return 20

    work.mkdir(parents=True,exist_ok=True)
    lock=work/"install.lock"
    if lock.exists():
        try: prior=int(lock.read_text(encoding="ascii").strip() or 0)
        except Exception: prior=0
        if pid_alive(prior):
            print("HOLD INSTALL_ALREADY_RUNNING",prior);return 20
        lock.unlink(missing_ok=True)
    try:
        fd=os.open(str(lock),os.O_CREAT|os.O_EXCL|os.O_WRONLY)
        os.write(fd,str(os.getpid()).encode("ascii"));os.close(fd)
    except FileExistsError:
        print("HOLD INSTALL_ALREADY_RUNNING");return 20

    try:
        stage=work/"stage";control=work/"control"
        shutil.rmtree(stage,ignore_errors=True);shutil.rmtree(control,ignore_errors=True)
        stage.mkdir(parents=True);(control/"00_CONTEXT").mkdir(parents=True)
        (control/"02_UPDATES"/"AGENT").mkdir(parents=True);(control/"RECOVERY").mkdir(parents=True)
        staged=stage/package.name;shutil.copyfile(package,staged)
        if sha256(staged).lower()!=a.expected_sha.lower():
            print("HOLD STAGED_PACKAGE_READBACK_MISMATCH");return 20

        try:
            with zipfile.ZipFile(staged,"r") as z:
                matches=[i for i in z.infolist() if i.filename==RUNNER_MEMBER]
                if len(matches)!=1:
                    print("HOLD RUNNER_MEMBER_COUNT",len(matches));return 20
                info=matches[0]
                if not (64<=info.file_size<=524288):
                    print("HOLD RUNNER_SIZE_INVALID",info.file_size);return 20
                raw=z.read(info)
        except zipfile.BadZipFile:
            print("HOLD PACKAGE_BAD_ZIP");return 20
        try: src=raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            print("HOLD RUNNER_ENCODING_INVALID");return 20
        try: compile(src,RUNNER_MEMBER,"exec")
        except Exception as e:
            print("HOLD RUNNER_COMPILE_FAILED",repr(e));return 20
        if "def main(" not in src or "__main__" not in src:
            print("HOLD RUNNER_CONTRACT_INVALID");return 20
        if a.target_sequence>=6034 and ("publish_result(root,result,rec)" not in src or "atomic(result,rec)" in src):
            print("HOLD RUNNER_DRIVEFS_FAILOPEN_CONTRACT");return 20

        runner=stage/"recovery_update_runner.py";runner.write_bytes(src.encode("utf-8"))
        control_pkg=control/"02_UPDATES"/"AGENT"/package.name;shutil.copyfile(staged,control_pkg)
        if sha256(control_pkg).lower()!=a.expected_sha.lower():
            print("HOLD CONTROL_PACKAGE_READBACK_MISMATCH");return 20
        write_json(control/"00_CONTEXT"/"RECOVERY_BOOTSTRAP_TARGET.json",{
            "schema":"g6.recovery_bootstrap_target/1","status":"ACTIVE","truth":"LOCAL_OFFLINE_TARGET_NOT_INSTALL_PROOF",
            "version":a.target_version,"sequence":a.target_sequence,"package_file":package.name,
            "package_sha256":a.expected_sha.lower(),"authorization_token":"2003",
            "rollback_version":"6.0.32","rollback_sequence":6032})
        if a.preflight_only:
            print("OFFLINE_RECOVERY_PREFLIGHT_PASS",a.target_version,a.target_sequence,"free_memory_mb",free);return 0

        flags=getattr(subprocess,"CREATE_NO_WINDOW",0)
        cp=subprocess.run([str(py),str(runner),"--install",str(root),"--control",str(control)],
            cwd=str(root),capture_output=True,text=True,errors="replace",timeout=420,shell=False,creationflags=flags)
        (work/"runner.stdout.log").write_text(cp.stdout or "",encoding="utf-8")
        (work/"runner.stderr.log").write_text(cp.stderr or "",encoding="utf-8")
        if cp.returncode!=0:
            print("HOLD RUNNER_FAILED",cp.returncode,(cp.stderr or "")[-1000:]);return 20

        final=read_json(root/"state"/"active_release.json")
        if int(final.get("sequence") or 0)!=a.target_sequence or str(final.get("version") or "")!=a.target_version:
            print("HOLD ACTIVE_RELEASE_READBACK_MISMATCH",final);return 20
        write_json(work/"OFFLINE_INSTALL_RESULT.json",{
            "schema":"bcp.offline_recovery_install/1","status":"INSTALL_ACTIVE_READBACK_PASS",
            "version":a.target_version,"sequence":a.target_sequence,"package_sha256":a.expected_sha.lower(),
            "internet_required":False,"drivefs_required":False,"field_command_plane_two_cycles_verified":False,
            "completed_at":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())})
        print("OFFLINE_RECOVERY_INSTALL_PASS",a.target_version,a.target_sequence);return 0
    except subprocess.TimeoutExpired:
        print("HOLD RUNNER_TIMEOUT_420S");return 20
    finally:
        lock.unlink(missing_ok=True)

if __name__=="__main__": raise SystemExit(main())
