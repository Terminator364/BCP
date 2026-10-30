"""BCP Android v1.5.0 signed stable promotion, atomic and rollback-safe.

Runs ONLY on MBMPC with an existing valid local signing report. Never copies
private signing material or publishes any unauthenticated remote endpoint.
"""
from pathlib import Path
import hashlib
import json
import os
import shutil

root=Path(os.environ["LOCALAPPDATA"])/"BCP-Universal-Remote"
build=root/"G2-v150-build"
signed=build/"BCP-Universal-v1.5.0-SIGNED.apk"
report=json.loads((build/"G2_SIGNED_RELEASE_REPORT.json").read_text("utf-8-sig"))
source=signed.read_bytes()
sha=hashlib.sha256(source).hexdigest()
if not (report.get("certificate_matches_R33") is True and
        report.get("package")=="com.blessing.rescuebridge" and
        report.get("version_code")==19 and
        report.get("version_name")=="1.5.0-g4-file-upload-candidate" and
        report.get("bytes")==len(source) and
        report.get("sha256","").lower()==sha and
        30000<len(source)<30000000 and source.startswith(b"PK")):
    raise RuntimeError("V150_SIGNED_ARTIFACT_INVALID")

updates=root/"updates"
current_meta=updates/"stable.json"
current_apk=updates/"stable.apk"
previous=json.loads(current_meta.read_text("utf8"))
old_sha=previous.get("sha256","").lower()
if previous.get("package")!="com.blessing.rescuebridge":
    raise RuntimeError("STABLE_PACKAGE_CHANGED")
if hashlib.sha256(current_apk.read_bytes()).hexdigest()!=old_sha:
    raise RuntimeError("OLD_STABLE_APK_SHA_INVALID")
old_version=previous["versionCode"]
if type(old_version)!=int or old_version>19:
    raise RuntimeError("VERSION_DOWNGRADE_REFUSED")
if old_version==19:
    if old_sha==sha:
        print(json.dumps({"status":"ALREADY_PUBLISHED_SAME_SHA",
                          "versionCode":19,"sha256":sha}))
        raise SystemExit(0)
    raise RuntimeError("SAME_VERSION_DIFFERENT_BINARY")
if old_version!=18:
    raise RuntimeError("UNEXPECTED_MIGRATION_BASE")
url=previous.get("url","")
if not isinstance(url,str) or not url.startswith("https://") or not url.endswith("/updates/stable.apk"):
    raise RuntimeError("UNTRUSTED_STABLE_URL")

backup=root/"backups"/"G4_V150_STABLE_PREVIOUS"
if backup.exists():
    raise RuntimeError("PREEXISTING_V150_BACKUP_REQUIRES_AUDIT")
backup.mkdir(parents=True,exist_ok=False)
backmeta=backup/"stable.json"
backapk=backup/"stable.apk"
shutil.copy2(current_meta,backmeta)
shutil.copy2(current_apk,backapk)
if (hashlib.sha256(backapk.read_bytes()).hexdigest()!=old_sha or
    json.loads(backmeta.read_text("utf8"))!=previous):
    raise RuntimeError("ROLLBACK_BACKUP_VERIFICATION_FAILED")

newmeta={"schema":"BCP_SELF_UPDATE_V1","channel":"stable",
         "package":"com.blessing.rescuebridge","versionCode":19,
         "versionName":"1.5.0-g4-file-upload-candidate",
         "size":len(source),"sha256":sha,"url":url}

def stage_bytes(path,data):
    with path.open("xb") as f:
        f.write(data)
        f.flush();os.fsync(f.fileno())

new_apk_tmp=updates/"stable.apk.v150.part"
new_meta_tmp=updates/"stable.json.v150.part"
def restore_previous():
    restore_apk=updates/"stable.apk.rollback.part"
    restore_meta=updates/"stable.json.rollback.part"
    if restore_apk.exists() or restore_meta.exists():
        raise RuntimeError("OLD_ROLLBACK_STAGING_CONFLICT")
    stage_bytes(restore_apk,backapk.read_bytes())
    stage_bytes(restore_meta,backmeta.read_bytes())
    os.replace(restore_apk,current_apk)
    os.replace(restore_meta,current_meta)
    if hashlib.sha256(current_apk.read_bytes()).hexdigest()!=old_sha:
        raise RuntimeError("ROLLBACK_APK_HASH_MISMATCH")
    if json.loads(current_meta.read_text("utf8"))!=previous:
        raise RuntimeError("ROLLBACK_MANIFEST_MISMATCH")

switched=False
try:
    if new_apk_tmp.exists() or new_meta_tmp.exists():
        raise RuntimeError("UNRESOLVED_PREVIOUS_STAGING")
    stage_bytes(new_apk_tmp,source)
    stage_bytes(new_meta_tmp,json.dumps(newmeta,separators=(",",":"),
                                         ensure_ascii=False).encode("utf8"))
    if hashlib.sha256(new_apk_tmp.read_bytes()).hexdigest()!=sha:
        raise RuntimeError("STAGED_APK_HASH_MISMATCH")
    os.replace(new_apk_tmp,current_apk)
    switched=True
    os.replace(new_meta_tmp,current_meta)
    if (hashlib.sha256(current_apk.read_bytes()).hexdigest()!=sha or
        json.loads(current_meta.read_text("utf8"))!=newmeta):
        raise RuntimeError("POST_PUBLICATION_VERIFY_FAILED")
except Exception:
    if switched:
        restore_previous()
    raise
finally:
    for partial in (new_apk_tmp,new_meta_tmp):
        if partial.exists():partial.unlink()

print(json.dumps({"schema":"BCP_V150_SIGNED_STABLE_PROMOTION",
     "status":"PASS","previous_code":old_version,"new_code":19,
     "sha256":sha,"bytes":len(source),
     "backup_verified":True,"keystore_uploaded":False,
     "local_owner_profile_activated":False},ensure_ascii=False))
