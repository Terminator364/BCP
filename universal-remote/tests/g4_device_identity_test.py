"""BCP device isolation, enrollment and replay tests. No real PC files changed."""
import hashlib
import hmac
import json
from pathlib import Path
import secrets
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parent.parent/"windows"))
from g4_device_identity import DeviceRegistry,IdentityError,signing_message

passed=[]
def ok(name,test):
    assert test,name
    passed.append(name)
def denied(name,call):
    try:call()
    except (IdentityError,ValueError):
        passed.append(name)
    else:raise AssertionError(name)

with tempfile.TemporaryDirectory(prefix="bcp-device-identity-") as p:
    reg=DeviceRegistry(Path(p)/"private")
    a=secrets.token_hex(16);b=secrets.token_hex(16)
    ka=secrets.token_hex(32);kb=secrets.token_hex(32)
    now=1761858600
    path="/v1/g4/universal/inventory"
    body=b'{"action":"system.volumes","args":{}}'
    ok("starts_empty",reg.enrolled_public()==[])
    denied("cannot_approve_without_pending",lambda:reg.approve_local(a,"123456",True,now))
    x=reg.request_enrollment(a,ka,"Samsung A",now)
    y=reg.request_enrollment(b,kb,"Samsung B",now)
    ok("two_pending_unique",len(reg.pending_public(now))==2 and x["verification_code"]!=y["verification_code"])
    ok("no_authority_on_request",reg.enrolled_public()==[])
    denied("missing_user_confirmation",lambda:reg.approve_local(a,x["verification_code"],False,now))
    denied("wrong_code",lambda:reg.approve_local(a,"not-six",True,now))
    denied("wrong_6_digit_code",lambda:reg.approve_local(a,("%06d"%((int(x["verification_code"])+1)%1000000)),True,now))
    ok("approved_device_a",reg.approve_local(a,x["verification_code"],True,now)["owner_trust"]=="NOT_GRANTED")
    ok("device_b_still_pending",len(reg.enrolled_public())==1 and len(reg.pending_public(now))==1)
    denied("cannot_approve_twice",lambda:reg.approve_local(a,x["verification_code"],True,now))
    denied("cannot_duplicate_registration",lambda:reg.request_enrollment(a,ka,"Duplicate",now))
    ok("second_device_approved",reg.approve_local(b,y["verification_code"],True,now)["status"]=="ENROLLED")
    t=str(now);n=secrets.token_hex(16)
    sign=lambda key,dev,ts,nonce,contents,pt=path:hmac.new(bytes.fromhex(key),
        signing_message(dev,"POST",pt,ts,nonce,contents),hashlib.sha256).hexdigest()
    good=sign(ka,a,t,n,body)
    ok("device_a_signature",reg.verify_request(a,"POST",path,t,n,body,good,now)==a)
    denied("device_nonce_replay",lambda:reg.verify_request(a,"POST",path,t,n,body,good,now))
    denied("wrong_body",lambda:reg.verify_request(a,"POST",path,t,secrets.token_hex(16),b'evil',good,now))
    denied("wrong_device_key",lambda:reg.verify_request(a,"POST",path,t,secrets.token_hex(16),body,sign(kb,a,t,secrets.token_hex(16),body),now))
    denied("wrong_device_identity",lambda:reg.verify_request(b,"POST",path,t,secrets.token_hex(16),body,good,now))
    denied("expired_timestamp",lambda:reg.verify_request(a,"POST",path,str(now-300),secrets.token_hex(16),body,good,now))
    denied("invalid_path",lambda:reg.verify_request(a,"POST","/v1/status",t,secrets.token_hex(16),body,good,now))
    denied("invalid_nonce",lambda:reg.verify_request(a,"POST",path,t,"notnonce",body,good,now))
    denied("cannot_revoke_without_local",lambda:reg.revoke_local(a,False))
    ok("revoke_a",reg.revoke_local(a,True)["status"]=="REVOKED")
    nna=secrets.token_hex(16)
    denied("revoked_device_refused",lambda:reg.verify_request(a,"POST",path,t,nna,body,sign(ka,a,t,nna,body),now))
    nnb=secrets.token_hex(16)
    ok("device_b_unaffected",reg.verify_request(b,"POST",path,t,nnb,body,sign(kb,b,t,nnb,body),now)==b)
    denied("shared_g2_key_not_valid_device",lambda:reg.verify_request(b,"POST",path,t,secrets.token_hex(16),body,"0"*64,now))
    c=secrets.token_hex(16)
    kc=secrets.token_hex(32)
    reg.request_enrollment(c,kc,"Android C",now)
    d=secrets.token_hex(16)
    kd=secrets.token_hex(32)
    reg.request_enrollment(d,kd,"Android D",now)
    e=secrets.token_hex(16)
    reg.request_enrollment(e,secrets.token_hex(32),"Android E",now)
    f=secrets.token_hex(16)
    denied("pending_count_cap",lambda:reg.request_enrollment(f,secrets.token_hex(32),"Android F",now))
    ok("prune_expired",len(reg.pending_public(now+601))==0)
    denied("expired_approval_rejected",lambda:reg.approve_local(c,"000000",True,now+601))
    ok("no_global_owner_profile_created",all("owner" not in item for item in reg.enrolled_public()))
print(json.dumps({"schema":"BCP_DEVICE_IDENTITY_REGRESSION_V1","passed":len(passed),
                  "checks":passed,"PASS":True,"real_owner_granted":False,
                  "real_user_files_modified":False},indent=2))
