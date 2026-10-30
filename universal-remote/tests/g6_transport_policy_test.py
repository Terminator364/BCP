"""BCP G6 deterministic transport state-machine tests; no actual network used."""
from pathlib import Path
import json
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/"windows"))
from g6_transport_policy import LinkSignals,TransportPlanner,NetworkPolicyError

checks={}
def ok(name,condition):
    checks[name]=bool(condition)
    if not condition:raise AssertionError(name)
def denied(name,fn):
    try:fn()
    except NetworkPolicyError:ok(name,True)
    else:raise AssertionError(name)

clock=[10000.]
with tempfile.TemporaryDirectory(prefix="bcp-g6-network-") as temp:
    file=Path(temp)/"state.json"
    p=TransportPlanner(file,now=lambda:clock[0])
    on=LinkSignals(True,True,True,True,True)
    ok("all_four_prioritized",p.plan(on)["attempts"]==["WIFI_LAN","TAILSCALE","USB","BLUETOOTH"])
    ok("never_enables_cellular_tether",p.plan(on)["mobile_tethering"] is False)
    ok("wifi_untrusted_must_not_lan",p.plan(LinkSignals(False,True,True,False,False))["attempts"]==["TAILSCALE"])
    ok("lan_server_not_seen_must_not_attempt",p.plan(LinkSignals(True,False,True,False,False))["attempts"]==["TAILSCALE"])
    ok("offline_empty_plan",p.plan(LinkSignals())["attempts"]==[])
    p.report("WIFI_LAN",False)
    ok("lan_failure_fails_over_tailnet",p.plan(on)["attempts"][0]=="TAILSCALE")
    p.report("TAILSCALE",False)
    ok("tailnet_failure_fails_over_usb",p.plan(on)["attempts"][0]=="USB")
    p.report("USB",False)
    ok("usb_failure_fails_over_bluetooth",p.plan(on)["attempts"]==["BLUETOOTH"])
    p.report("BLUETOOTH",False)
    q=p.plan(on)
    ok("all_cooldown_no_retry_storm",q["attempts"]==[] and q["wait_until"]>clock[0])
    ok("cooldown_wait_is_bounded",0<q["wait_until"]-clock[0]<=60)
    t=TransportPlanner(file,now=lambda:clock[0])
    ok("persists_failure_backoff",t.plan(on)["attempts"]==[])
    clock[0]+=3
    ok("retry_after_cooldown",t.plan(on)["attempts"]==list(("WIFI_LAN","TAILSCALE","USB","BLUETOOTH")))
    t.report("WIFI_LAN",False)
    ok("exponential_backoff",t.failures["WIFI_LAN"]["retry_after"]-clock[0]==4)
    t.report("WIFI_LAN",True)
    ok("success_resets_backoff",t.failures["WIFI_LAN"]["count"]==0 and t.plan(on)["attempts"][0]=="WIFI_LAN")
    ok("signals_do_not_store_private_IP_or_SSID",not any(k in file.read_text() for k in ("192.168.","ssid","pairing")))
    denied("bad_channel_rejected",lambda:t.report("PUBLIC_INTERNET",False))
    denied("fake_signals_rejected",lambda:t.plan({"trusted_wifi":True}))
    denied("bad_result_type_rejected",lambda:t.report("USB","success"))
    file.write_text("invalid")
    denied("corrupt_journal_fails_closed",lambda:TransportPlanner(file))
print(json.dumps({"schema":"BCP_G6_NETWORK_PLANNER_LAB","passed":len(checks),
                  "checks":checks,"PASS":all(checks.values()),
                  "network_connections_attempted":0,"cellular_tether_enabled":False}))
