import os
import sys
import tempfile
import pathlib
import base64
import hashlib
sys.path.insert(0,str(pathlib.Path(os.environ["LOCALAPPDATA"])/"BCP-Universal-Remote"))
import g4_universal_inventory as m
with tempfile.TemporaryDirectory() as directory:
    root=pathlib.Path(directory)
    for i in range(245):
        (root/("item_%03d.txt" % i)).write_text("x",encoding="utf8")
    first=m.list_page(str(root),0,128)
    second=m.list_page(str(root),first["next_cursor"],128)
    assert len(first["items"])+len(second["items"])==245
    assert second["next_cursor"] is None
    raw=os.urandom(410000)
    file=root/"large.bin"
    file.write_bytes(raw)
    offset=0
    restored=bytearray()
    n=0
    while True:
        part=m.read_chunk(str(file),offset)
        restored.extend(base64.b64decode(part["data_base64"]))
        n+=1
        if part["next_offset"] is None:
            break
        offset=part["next_offset"]
    assert restored==raw
    assert m.file_digest(str(file))["sha256"]==hashlib.sha256(raw).hexdigest()
    assert n>6
    print("WINDOWS_FULL_INVENTORY_LAB=PASS;entries=245;file_bytes=410000;chunks="+str(n))
