"""BCP owner policy laboratory: device trust is durable but consent cannot be forged."""
from pathlib import Path
import hashlib,json,secrets,tempfile,time
import g4_owner_trust as m

result={}
def check(label,condition):
    result[label]=bool(condition)
    if not condition:raise AssertionError(label)
def deny(label,fn):
    try:fn()
    except (m.TrustError,ValueError):check(label,True)
    else:check(label,False)

with tempfile.TemporaryDirectory(prefix="bcp-owner-policy-") as tmp:
    root=Path(tmp)
    key=secrets.token_bytes(32)
    dev=hashlib.sha256(secrets.token_bytes(32)).hexdigest()
    policy=m.OwnerTrust(root,key)
    check("deny_before_enrollment",not policy.public_status(dev)["trusted"])
    deny("no_enroll_without_local_consent",
         lambda:policy.enroll_local(dev,confirm_local=False))
    deny("no_authorization_before_enroll",
         lambda:policy.authorize(dev,"files.read"))
    check("still_no_profile_created",not list(root.glob("*.json")))
    p=policy.enroll_local(dev,confirm_local=True,profile="operator",
                          high_risk_confirmation=True)
    check("owner_durable",p["expiry"] is None and p["operation_limit"] is None)
    check("owner_no_folder_scope",p["path_scope"] is None)
    check("owner_full_categories",len(p["categories"])==8)
    for _ in range(101):
        policy.authorize(dev,"files.read")
    check("over_100_calls_no_quota",True)
    policy.authorize(dev,"files.write")
    check("write_category_authorized",True)
    deny("command_requires_high_risk_consent",
        lambda:policy.authorize(dev,"commands"))
    check("approved_command_category",
        policy.authorize(dev,"commands",approval_for_sensitive=True))
    deny("deny_unknown_category",lambda:policy.authorize(dev,"telepathy"))
    deny("remote_cannot_revoke",
         lambda:policy.revoke_local(dev,confirm_local=False))
    check("still_trusted",policy.public_status(dev)["trusted"])
    file=root/(dev+".json")
    original=file.read_text("utf8")
    obj=json.loads(original);obj["high_risk_confirmation"]=False
    file.write_text(json.dumps(obj),encoding="utf8")
    deny("tampered_policy_fails_closed",lambda:policy.authorize(dev,"commands"))
    file.write_text(original,encoding="utf8")
    check("restored_valid_policy",policy.authorize(dev,"files.read"))
    owner=policy.enroll_local(dev,confirm_local=True,profile="operator",
                             high_risk_confirmation=False)
    check("local_choice_no_repeated_command_prompt",
          policy.authorize(dev,"commands"))
    check("user_selected_high_risk_mode_off",
          owner["high_risk_confirmation"] is False)
    check("local_revoke",policy.revoke_local(dev,confirm_local=True)["revoked"])
    deny("revoke_blocks_all",lambda:policy.authorize(dev,"files.read"))
    check("revoked_status",not policy.public_status(dev)["trusted"])
    # Unpaired second device is not implicitly trusted.
    other=hashlib.sha256(secrets.token_bytes(32)).hexdigest()
    deny("second_device_untrusted",lambda:policy.authorize(other,"files.read"))
print(json.dumps({"schema":"BCP_G4_OWNER_TRUST_BENCH","checks":result,
                  "passed":sum(result.values()),"PASS":all(result.values()),
                  "production_owner_trust_created":False},indent=2))
