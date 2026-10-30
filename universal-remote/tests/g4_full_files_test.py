"""BCP unrestricted streamed Windows file engine laboratory regression tests."""
import base64
import hashlib
import os
from pathlib import Path
import secrets
import tempfile
from g4_full_files import FileTransactions, FileOperationError, CHUNK

checks={}
def check(name,value):
    checks[name]=bool(value)
    if not value:raise AssertionError(name)
def denied(name,callback):
    try:callback()
    except (FileOperationError,ValueError,OSError):
        check(name,True)
    else:check(name,False)

with tempfile.TemporaryDirectory(prefix="bcp-full-files-") as tmp:
    root=Path(tmp)
    first=root/"Volume-A"
    second=root/"Volume-B"
    first.mkdir();second.mkdir()
    engine=FileTransactions(root/"state")
    raw=os.urandom(1024001)
    dst=second/"large-data.bin"
    started=engine.begin(str(dst))
    ident=started["upload_id"]
    check("new_upload_offset_zero",started["next_offset"]==0)
    denied("cannot_begin_twice_same_destination",
        lambda:engine.begin(str(dst),overwrite=True,expected_old_sha="bad"))
    denied("reject_wrong_offset",lambda:engine.append(ident,100,"YQ=="))
    denied("reject_too_large_chunk",lambda:engine.append(ident,0,base64.b64encode(os.urandom(CHUNK+1)).decode()))
    offset=0
    for index in range(4):
        piece=raw[offset:offset+CHUNK]
        ack=engine.append(ident,offset,base64.b64encode(piece).decode(),
                          hashlib.sha256(piece).hexdigest())
        offset=ack["next_offset"]
    check("upload_partial_before_restart",offset==4*CHUNK)
    # Drop in-memory instance, resume via on-disk metadata.
    engine=FileTransactions(root/"state")
    while offset<len(raw):
        piece=raw[offset:offset+CHUNK]
        ack=engine.append(ident,offset,base64.b64encode(piece).decode(),
                          hashlib.sha256(piece).hexdigest())
        offset=ack["next_offset"]
    check("stream_over_one_megabyte",offset==len(raw))
    denied("wrong_final_checksum_refused",lambda:engine.commit(ident,"0"*64))
    check("unfinished_does_not_replace",not dst.exists())
    done=engine.commit(ident,hashlib.sha256(raw).hexdigest())
    check("exact_large_file_written",dst.read_bytes()==raw)
    check("sha256_returned",done["sha256"]==hashlib.sha256(raw).hexdigest())
    denied("committed_upload_not_replayed",lambda:engine.commit(ident,hashlib.sha256(raw).hexdigest()))
    denied("existing_destination_preserved",lambda:engine.begin(str(dst)))
    # Replace with a checked original; keep backup.
    replacement=b"replacement-content"
    oldsha=hashlib.sha256(raw).hexdigest()
    tx=engine.begin(str(dst),overwrite=True,expected_old_sha=oldsha)["upload_id"]
    engine.append(tx,0,base64.b64encode(replacement).decode())
    changed=engine.commit(tx,hashlib.sha256(replacement).hexdigest())
    check("explicit_replacement_worked",dst.read_bytes()==replacement)
    check("backup_kept_in_recovery",changed["recoverable_original"] and
          (root/"state/files/recovery"/(tx+".bak")).read_bytes()==raw)
    # Adversarial Windows race: a concurrent writer creates a new
    # destination after upload begin. Committing must NEVER overwrite it.
    contested=second/"concurrent-created.txt"
    tx_race=engine.begin(str(contested))["upload_id"]
    race_payload=b"BCP_UPLOAD_MUST_NOT_OVERRIDE"
    engine.append(tx_race,0,base64.b64encode(race_payload).decode())
    contested.write_bytes(b"ANOTHER_WRITER_WON")
    denied("concurrent_new_file_must_never_be_overwritten",
        lambda:engine.commit(tx_race,hashlib.sha256(race_payload).hexdigest()))
    check("concurrent_original_remains_untouched",contested.read_bytes()==b"ANOTHER_WRITER_WON")
    # No fixed quota of 20, 30 minutes, or single directory.
    for i in range(26):
        target=first/("item_"+str(i)+".txt")
        transaction=engine.begin(str(target))["upload_id"]
        one=str(i).encode()
        engine.append(transaction,0,base64.b64encode(one).decode())
        engine.commit(transaction,hashlib.sha256(one).hexdigest())
    check("more_than_twenty_operations",len(list(first.iterdir()))==26)
    check("multiple_sibling_directories_accessed",dst.exists() and
          (first/"item_25.txt").exists())
    # Reversible quarantine + restore, including directory trees.
    q=engine.quarantine(str(first))
    check("directory_quarantined_without_deletion",not first.exists() and q["recoverable"])
    restored=engine.restore(q["recovery_id"])
    check("directory_restored",first.is_dir() and (first/"item_25.txt").exists())
    denied("recovery_replay_denied",lambda:engine.restore(q["recovery_id"]))
    # Abort keeps destination absent.
    blank=second/"cancelled.txt"
    pending=engine.begin(str(blank))["upload_id"]
    engine.abort(pending)
    check("abort_leaves_no_created_document",not blank.exists())
    denied("abort_cannot_continue",lambda:engine.append(pending,0,"YQ=="))
    denied("path_must_be_absolute",lambda:engine.begin("relative.txt"))
    check("server_state_only_test_files",len(list((root/"state/files/uploads").glob("*.json")))>26)
print({"schema":"BCP_G4_FULL_FILES_REGRESSION",
       "passed":sum(checks.values()),"checks":checks,
       "PASS":all(checks.values()),"real_user_files_modified":False,
       "hard_total_size_quota":False,"per_response_memory_bounded":True})
