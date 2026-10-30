"""BCP G6 transport selection and low-resource reconnection policy.

No sockets, no network toggles, no cellular tethering and no credentials.
This deterministic planner only chooses the next existing secure transport.
"""
from __future__ import annotations
from dataclasses import dataclass
import json
from pathlib import Path
import os
import secrets
import time

ORDER=("WIFI_LAN","TAILSCALE","USB","BLUETOOTH")

@dataclass(frozen=True)
class LinkSignals:
    trusted_wifi:bool=False
    lan_server_visible:bool=False
    tailscale_connected:bool=False
    usb_session_ready:bool=False
    bluetooth_session_ready:bool=False

class NetworkPolicyError(ValueError):
    pass

class TransportPlanner:
    def __init__(self,state_file,now=None):
        self.path=Path(state_file)
        self.now=now if now is not None else time.time
        self.failures={name:{"count":0,"retry_after":0} for name in ORDER}
        if self.path.exists():
            try:
                saved=json.loads(self.path.read_text("utf-8"))
                if saved.get("schema")!="BCP_TRANSPORT_POLICY_V1":
                    raise ValueError("SCHEMA_MISMATCH")
                for name in ORDER:
                    item=saved["failures"].get(name,{})
                    n=item.get("count");t=item.get("retry_after")
                    if type(n)!=int or n<0 or n>10000 or not isinstance(t,(int,float)) or t<0:
                        raise ValueError("BAD_STATE")
                    self.failures[name]={"count":n,"retry_after":float(t)}
            except (OSError,KeyError,ValueError,TypeError) as err:
                # Preserve questionable journal for inspection; never overwrite.
                raise NetworkPolicyError("TRANSPORT_JOURNAL_INVALID") from err
    def _save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temp=self.path.with_name(self.path.name+"."+secrets.token_hex(6)+".tmp")
        item={"schema":"BCP_TRANSPORT_POLICY_V1","failures":self.failures}
        try:
            with temp.open("x",encoding="utf-8") as file:
                json.dump(item,file,separators=(",",":"),sort_keys=True)
                file.flush();os.fsync(file.fileno())
            os.replace(temp,self.path)
        finally:
            if temp.exists():temp.unlink()
    def report(self,channel,success):
        if channel not in ORDER or type(success)!=bool:
            raise NetworkPolicyError("INVALID_RESULT")
        entry=self.failures[channel]
        if success:
            entry.update({"count":0,"retry_after":0})
        else:
            entry["count"]=min(entry["count"]+1,10000)
            delay=min(60,2**min(entry["count"],6))
            entry["retry_after"]=float(self.now())+delay
        self._save()
        return {"channel":channel,"retry_after":entry["retry_after"],
                "failures":entry["count"]}
    def _available(self,links):
        if not isinstance(links,LinkSignals):
            raise NetworkPolicyError("LINK_SIGNAL_REQUIRED")
        return {
            "WIFI_LAN":links.trusted_wifi and links.lan_server_visible,
            "TAILSCALE":links.tailscale_connected,
            "USB":links.usb_session_ready,
            "BLUETOOTH":links.bluetooth_session_ready
        }
    def plan(self,links):
        ready=self._available(links)
        now=float(self.now())
        active=[name for name in ORDER if ready[name]]
        choices=[name for name in active if self.failures[name]["retry_after"]<=now]
        if not choices and active:
            # Never rapidly retry every failed channel while all cooling.
            earliest=min(active,key=lambda name:self.failures[name]["retry_after"])
            return {"attempts":[],"wait_until":self.failures[earliest]["retry_after"],
                    "best_after_wait":earliest,"mobile_tethering":False}
        return {"attempts":choices,"wait_until":None,"best_after_wait":None,
                "mobile_tethering":False}
    def reset(self,channel):
        return self.report(channel,True)
