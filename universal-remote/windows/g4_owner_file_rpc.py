"""G4 owner file RPC dispatcher, staging only.

Mount only behind BOTH valid legacy transport HMAC and a verified individual
device signature; the legacy shared pairing key is insufficient for any method.
No network server, no enrollment or approval is created by this module.
"""
from __future__ import annotations
from pathlib import Path
import re
from g4_owner_transactions import OwnerFileService

class RpcError(ValueError):
    pass

ACTIONS={
    "begin":frozenset(("destination","overwrite","expected_old_sha")),
    "append":frozenset(("upload_id","offset","data_base64","chunk_sha256")),
    "commit":frozenset(("upload_id","sha256")),
    "abort":frozenset(("upload_id",)),
    "status":frozenset(("upload_id",))
}
REQUIRED={
    "begin":frozenset(("destination",)),
    "append":frozenset(("upload_id","offset","data_base64")),
    "commit":frozenset(("upload_id","sha256")),
    "abort":frozenset(("upload_id",)),
    "status":frozenset(("upload_id",))
}

class OwnerFileRpc:
    def __init__(self,state_dir:Path,policy,registry):
        self.service=OwnerFileService(state_dir,policy,registry)
    def dispatch(self,verified_device_id,action,args):
        if action not in ACTIONS or not isinstance(args,dict):
            raise RpcError("UNKNOWN_OWNER_FILE_ACTION")
        names=set(args)
        if not REQUIRED[action]<=names or not names<=ACTIONS[action]:
            raise RpcError("FILE_ACTION_INVALID_ARGUMENTS")
        if len(str(args))>150000:
            raise RpcError("REQUEST_TOO_LARGE")
        # Individual device identity is verified at the TLS boundary;
        # OwnerFileService also checks durable device registration,
        # revocation, owner trust, transaction ownership on every call.
        if action=="begin":
            return self.service.begin(verified_device_id,args["destination"],
                args.get("overwrite",False),args.get("expected_old_sha"))
        if action=="append":
            return self.service.append(verified_device_id,args["upload_id"],
                args["offset"],args["data_base64"],args.get("chunk_sha256"))
        if action=="commit":
            return self.service.commit(verified_device_id,args["upload_id"],
                                       args["sha256"])
        if action=="abort":
            return self.service.abort(verified_device_id,args["upload_id"])
        return self.service.status(verified_device_id,args["upload_id"])
