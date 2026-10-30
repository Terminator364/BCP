"""Create a harmless G4 approval ticket on the user's Windows PC.
No approval, privilege change, or execution is performed here.
"""
from pathlib import Path
import json
import os
from g4_agent import G4Bridge, ROOT

def main():
    base=ROOT/"G4-Staging-Workspace"
    base.mkdir(parents=True,exist_ok=True)
    target=base/"G4_FIELD_APPROVAL_PROOF_20261030.txt"
    if target.exists():
        print("ALREADY_EXISTS: preserve prior file")
        return
    bridge=G4Bridge()
    ticket=bridge.operate("prepare",{
        "kind":"write_text",
        "path":str(target),
        "text":"BCP G4 - field approval proof.\nOnly written after confirmation in the Windows approval center.\n"
    })
    # Prove that the request alone never creates or modifies the file.
    denied=False
    try:
        bridge.operate("commit",{"ticket":ticket["ticket"]})
    except ValueError as ex:
        denied=str(ex)=="LOCAL_APPROVAL_REQUIRED"
    if not denied or target.exists():
        raise AssertionError("G4_NOT_SAFE_BEFORE_LOCAL_APPROVAL")
    result={"operation":"write_text","target":str(target),
            "ticket":ticket["ticket"],"status":ticket["status"],
            "expires":ticket["expires"],"requires_local_approval":True}
    (ROOT/"state"/"g4_field_approval_ticket.json").write_text(
        json.dumps(result,indent=2),encoding="utf8")
    print(json.dumps(result,indent=2))
if __name__=="__main__":main()
