from __future__ import annotations
import hashlib, json, os, subprocess, sys, tempfile, zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
INSTALLER=ROOT/"windows"/"offline_recovery_6034"/"offline_install_6034.py"
TARGET_VERSION="6.0.34";TARGET_SEQUENCE=6034
MEMBER="payload/tools/recovery_update_runner.py"

GOOD_RUNNER=r'''from __future__ import annotations
import argparse,json,time
from pathlib import Path
def publish_result(root,result,rec): return {"cloud":"PASS"}
def main():
 p=argparse.ArgumentParser();p.add_argument("--install",required=True);p.add_argument("--control",required=True);a=p.parse_args()
 root=Path(a.install);s=root/"state";s.mkdir(parents=True,exist_ok=True)
 (s/"active_release.json").write_text(json.dumps({"version":"6.0.34","sequence":6034}),encoding="utf-8")
 return 0
if __name__=="__main__": raise SystemExit(main())
'''
BAD_DRIVEFS_RUNNER=GOOD_RUNNER.replace('return {"cloud":"PASS"}','atomic(result,rec); return {"cloud":"PASS"}')

def pack(path:Path,runner:str,duplicates:int=1,version="6.0.34",sequence=6034,from_versions=None):
 if from_versions is None: from_versions=["6.0.32"]
 manifest={"schema":1,"package_type":"agent_update","version":version,"sequence":sequence,
           "from_version":from_versions[0] if from_versions else None,"from_versions":from_versions,
           "files":[{"path":"app/marker.txt","sha256":hashlib.sha256(b"fixture").hexdigest(),"size":7}]}
 with zipfile.ZipFile(path,"w",zipfile.ZIP_DEFLATED) as z:
  z.writestr("manifest.json",json.dumps(manifest))
  for _ in range(duplicates): z.writestr(MEMBER,runner)
  z.writestr("payload/app/marker.txt","fixture")
 return hashlib.sha256(path.read_bytes()).hexdigest()

def invoke(td:Path,pkg:Path,sha:str,mem:int=512,preflight=False):
 root=td/"install";root.mkdir(parents=True,exist_ok=True);(root/"state").mkdir(exist_ok=True)
 work=td/"work"
 cmd=[sys.executable,str(INSTALLER),"--test-mode","--package",str(pkg),"--install-root",str(root),
      "--python",sys.executable,"--work-root",str(work),"--expected-sha",sha,
      "--target-version",TARGET_VERSION,"--target-sequence",str(TARGET_SEQUENCE),
      "--free-memory-override-mb",str(mem)]
 if preflight: cmd.append("--preflight-only")
 cp=subprocess.run(cmd,capture_output=True,text=True,errors="replace",timeout=60)
 return cp,root,work

def check(name,ok):
 print(("PASS" if ok else "FAIL"),name)
 if not ok: raise AssertionError(name)

def main():
 source=INSTALLER.read_text(encoding="utf-8")
 check("installer-no-network-imports", all(x not in source for x in ("urllib","requests","http://","https://","drive.google")))
 check("installer-no-drivefs-hardcode", "Mon Drive" not in source and "Google Drive" not in source)
 check("installer-streaming-sha", "for chunk in iter" in source)
 check("installer-owned-subprocess-shell-false", "shell=False" in source)
 check("installer-runner-size-bound", "524288" in source)

 with tempfile.TemporaryDirectory(prefix="r48_") as raw:
  td=Path(raw);pkg=td/"good.zip";sha=pack(pkg,GOOD_RUNNER)
  cp,root,work=invoke(td,pkg,sha,mem=192)
  check("low-memory-valid-path-192mb",cp.returncode==0 and "OFFLINE_RECOVERY_INSTALL_PASS" in cp.stdout)
  active=json.loads((root/"state"/"active_release.json").read_text())
  check("active-readback-6034",active=={"version":"6.0.34","sequence":6034})
  cp2,_,_=invoke(td,pkg,sha,mem=192)
  check("idempotent-reentry",cp2.returncode==0 and "ALREADY_ACTIVE" in cp2.stdout)

 with tempfile.TemporaryDirectory(prefix="r48_") as raw:
  td=Path(raw);pkg=td/"good.zip";sha=pack(pkg,GOOD_RUNNER)
  cp,root,work=invoke(td,pkg,sha,mem=159)
  check("critical-memory-hold-premutation",cp.returncode==20 and "LOW_MEMORY_PREMUTATION" in cp.stdout and not (root/"state"/"active_release.json").exists())

 with tempfile.TemporaryDirectory(prefix="r48_") as raw:
  td=Path(raw);pkg=td/"good.zip";sha=pack(pkg,GOOD_RUNNER)
  cp,root,work=invoke(td,pkg,"0"*64,mem=512)
  check("bad-sha-hold",cp.returncode==20 and "PACKAGE_SHA256_MISMATCH" in cp.stdout and not work.exists())

 with tempfile.TemporaryDirectory(prefix="r48_") as raw:
  td=Path(raw);pkg=td/"dup.zip";sha=pack(pkg,GOOD_RUNNER,duplicates=2)
  cp,root,work=invoke(td,pkg,sha)
  check("duplicate-runner-hold",cp.returncode==20 and "RUNNER_MEMBER_COUNT" in cp.stdout)

 with tempfile.TemporaryDirectory(prefix="r48_") as raw:
  td=Path(raw);pkg=td/"badcontract.zip";sha=pack(pkg,BAD_DRIVEFS_RUNNER)
  cp,root,work=invoke(td,pkg,sha)
  check("drivefs-regression-hold",cp.returncode==20 and "RUNNER_DRIVEFS_FAILOPEN_CONTRACT" in cp.stdout)

 with tempfile.TemporaryDirectory(prefix="r48_") as raw:
  td=Path(raw);pkg=td/"good.zip";sha=pack(pkg,GOOD_RUNNER)
  work=td/"work";work.mkdir();(work/"install.lock").write_text(str(os.getpid()),encoding="ascii")
  cp,root,_=invoke(td,pkg,sha)
  check("concurrent-launch-hold",cp.returncode==20 and "INSTALL_ALREADY_RUNNING" in cp.stdout)

 with tempfile.TemporaryDirectory(prefix="r48_") as raw:
  td=Path(raw);pkg=td/"good.zip";sha=pack(pkg,GOOD_RUNNER)
  root=td/"install";(root/"state").mkdir(parents=True)
  (root/"state"/"active_release.json").write_text(json.dumps({"version":"6.0.35","sequence":6035}),encoding="utf-8")
  work=td/"work"
  cmd=[sys.executable,str(INSTALLER),"--test-mode","--package",str(pkg),"--install-root",str(root),"--python",sys.executable,
       "--work-root",str(work),"--expected-sha",sha,"--target-version",TARGET_VERSION,"--target-sequence",str(TARGET_SEQUENCE),
       "--free-memory-override-mb","512"]
  cp=subprocess.run(cmd,capture_output=True,text=True,timeout=60)
  check("no-downgrade-superseded",cp.returncode==20 and "TARGET_SUPERSEDED" in cp.stdout)

 with tempfile.TemporaryDirectory(prefix="r49_") as raw:
  td=Path(raw);pkg=td/"wrongver.zip";sha=pack(pkg,GOOD_RUNNER,version="6.0.33")
  cp,root,work=invoke(td,pkg,sha)
  check("manifest-version-mismatch-hold",cp.returncode==20 and "PACKAGE_MANIFEST_VERSION_MISMATCH" in cp.stdout)

 with tempfile.TemporaryDirectory(prefix="r49_") as raw:
  td=Path(raw);pkg=td/"wrongseq.zip";sha=pack(pkg,GOOD_RUNNER,sequence=6033)
  cp,root,work=invoke(td,pkg,sha)
  check("manifest-sequence-mismatch-hold",cp.returncode==20 and "PACKAGE_MANIFEST_SEQUENCE_MISMATCH" in cp.stdout)

 with tempfile.TemporaryDirectory(prefix="r49_") as raw:
  td=Path(raw);pkg=td/"wrongsource.zip";sha=pack(pkg,GOOD_RUNNER,from_versions=["6.0.31"])
  root=td/"install";(root/"state").mkdir(parents=True)
  (root/"state"/"active_release.json").write_text(json.dumps({"version":"6.0.32","sequence":6032}),encoding="utf-8")
  work=td/"work"
  cmd=[sys.executable,str(INSTALLER),"--test-mode","--package",str(pkg),"--install-root",str(root),"--python",sys.executable,
       "--work-root",str(work),"--expected-sha",sha,"--target-version",TARGET_VERSION,"--target-sequence",str(TARGET_SEQUENCE),
       "--free-memory-override-mb","512"]
  cp=subprocess.run(cmd,capture_output=True,text=True,timeout=60)
  check("manifest-source-mismatch-hold",cp.returncode==20 and "PACKAGE_MANIFEST_SOURCE_MISMATCH" in cp.stdout)

 print("R49_OFFLINE_RECOVERY_6034_TESTS=PASS")
 return 0
if __name__=="__main__": raise SystemExit(main())
