from pathlib import Path

PS1=Path("windows/NEXUS_AUTH_RETRY_CURRENT.ps1")
CMD=Path("windows/NEXUS_AUTH_RETRY_CURRENT.cmd")
POLICY=Path(".project-memory/DELIVERY_REDUNDANCY_POLICY.json")

def ck(name, cond):
    print(("PASS" if cond else "FAIL"), name)
    if not cond:
        raise AssertionError(name)

def main():
    p=PS1.read_text(encoding="utf-8")
    c=CMD.read_text(encoding="utf-8")
    policy=POLICY.read_text(encoding="utf-8")
    ck("local-endpoint-only", 'http://127.0.0.1:8765/v1/system/nexus/retry-auth' in p)
    ck("no-cloudflare-direct-url", "cloudflare.com" not in p.lower())
    ck("no-classic-localhost-oauth", "8976" not in p)
    ck("local-token-read", 'bcp_token.txt' in p)
    ck("token-not-printed", 'Write-Host $token' not in p and 'echo %TOKEN%' not in c)
    ck("explicit-confirm", 'confirm = $true' in p)
    ck("bounded-timeout", '-TimeoutSec 12' in p)
    ck("single-rest-call", p.count("Invoke-RestMethod")==1)
    ck("launched-pass", 'NEXUS_FRESH_DEVICE_FLOW_STARTED' in p)
    ck("unexpected-hold", 'HOLD NEXUS_UNEXPECTED_RESULT' in p)
    ck("cmd-one-shot", 'NEXUS_AUTH_RETRY_CURRENT.ps1' in c and 'pause' in c.lower())
    ck("mail-primary-detailed", '"role": "SOLE_PRIMARY_DETAILED_HUMAN_CHECKPOINT_DELIVERY"' in policy)
    ck("chat-pointer-only", '"role": "POINTER_ONLY_AFTER_SUCCESSFUL_EMAIL_CHECKPOINT"' in policy)
    ck("chat-no-full-body", '"detailed_checkpoint_body_forbidden_after_successful_email": true' in policy)
    ck("mail-before-chat-pointer", '"send_before_chat_pointer": true' in policy)
    ck("checkpoint-subject-policy", 'subject_must_include_checkpoint_id' in policy)
    ck("nested-zip-forbidden", 'nested_zip_for_user_action_forbidden' in policy)
    print("R55_DELIVERY_POLICY_AND_NEXUS_HELPER=PASS")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
