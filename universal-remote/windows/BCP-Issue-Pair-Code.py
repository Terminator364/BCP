"""BCP one-time pair invite: code only displayed locally on Windows, never written in plaintext."""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import time

ROOT=Path(os.environ["LOCALAPPDATA"])/"BCP-Universal-Remote"
STORE=ROOT/"private-state"/"pair-code.json"
def issue():
    STORE.parent.mkdir(parents=True,exist_ok=True)
    code=f"{secrets.randbelow(100_000_000):08d}"
    salt=secrets.token_bytes(16)
    digest=hashlib.pbkdf2_hmac("sha256",code.encode(),salt,120000)
    state={"schema":"BCP_PAIR_INVITE_V1","salt":salt.hex(),"digest":digest.hex(),
        "expires":int(time.time())+600,"attempts":0,"used":False}
    tmp=STORE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state,separators=(",",":")),encoding="utf-8")
    os.replace(tmp,STORE)
    username=os.environ.get("USERNAME","")
    if username:
        subprocess.run(["icacls",str(STORE),"/inheritance:r","/grant:r",username+":F"],
            capture_output=True,timeout=12,check=True)
    return code
def show():
    code=issue()
    ctypes.windll.user32.MessageBoxW(
        None,
        "Code d'appairage BCP : "+code+
        "\n\nSur ton téléphone : BCP Universal Remote > Réglages > Appairage en 8 chiffres."+
        "\n\nCode utilisable une seule fois pendant 10 minutes.",
        "BCP — Associer mon téléphone",0x40)
if __name__=="__main__":show()
