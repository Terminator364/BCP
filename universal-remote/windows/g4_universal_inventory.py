"""BCP G4 unrestricted Windows inventory: OS ACLs govern paths.

No predefined folder scope or total file-size cap. Chunk/page size limits only
bound per-response memory use, especially on 4 GB RAM hardware.
This is a library; no network listener or privilege elevation.
"""
from __future__ import annotations
import base64
import hashlib
import itertools
import os
from pathlib import Path
import shutil
import subprocess

CHUNK_BYTES=64*1024
PAGE_ITEMS=128

def _path(s):
    if not isinstance(s,str) or not s or len(s)>32767 or "\x00" in s:
        raise ValueError("INVALID_PATH")
    p=Path(s)
    if not p.is_absolute():
        raise ValueError("ABSOLUTE_PATH_REQUIRED")
    return p

def volumes():
    if os.name!="nt":
        return [{"path":"/"}]
    import ctypes
    mask=ctypes.windll.kernel32.GetLogicalDrives()
    results=[]
    for i in range(26):
        if mask&(1<<i):
            p=chr(65+i)+":\\"
            try:
                info=shutil.disk_usage(p)
                results.append({"path":p,"capacity_bytes":info.total,
                                "free_bytes":info.free})
            except (OSError,PermissionError):
                results.append({"path":p,"present":True,"space_unavailable":True})
    return results

def stat(raw):
    p=_path(raw)
    st=p.stat()
    return {"path":str(p),"file":p.is_file(),"directory":p.is_dir(),
            "bytes":st.st_size,"modified_ns":st.st_mtime_ns}

def list_page(raw,cursor=0,size=100):
    p=_path(raw)
    if not p.is_dir():raise ValueError("NOT_A_DIRECTORY")
    if type(cursor)!=int or cursor<0 or type(size)!=int or not 1<=size<=PAGE_ITEMS:
        raise ValueError("PAGE_INPUT_INVALID")
    results=[]
    with os.scandir(p) as iterator:
        window=itertools.islice(iterator,cursor,cursor+size+1)
        for entry in window:
            if len(results)==size:
                return {"path":str(p),"items":results,
                        "next_cursor":cursor+len(results)}
            try:
                st=entry.stat(follow_symlinks=False)
                results.append({"name":entry.name,"folder":entry.is_dir(follow_symlinks=False),
                                "bytes":st.st_size,"symlink":entry.is_symlink()})
            except OSError:
                results.append({"name":entry.name,"error":"STAT_UNAVAILABLE"})
    return {"path":str(p),"items":results,"next_cursor":None}

def read_chunk(raw,offset=0,size=CHUNK_BYTES):
    p=_path(raw)
    if type(offset)!=int or offset<0 or type(size)!=int or not 1<=size<=CHUNK_BYTES:
        raise ValueError("CHUNK_INPUT_INVALID")
    with p.open("rb") as stream:
        stream.seek(offset)
        data=stream.read(size)
        length=stream.seek(0,os.SEEK_END)
    return {"path":str(p),"total_bytes":length,"offset":offset,
            "bytes":len(data),"next_offset":offset+len(data) if offset+len(data)<length else None,
            "sha256_chunk":hashlib.sha256(data).hexdigest(),
            "data_base64":base64.b64encode(data).decode("ascii")}

def file_digest(raw):
    p=_path(raw)
    h=hashlib.sha256()
    total=0
    with p.open("rb") as stream:
        for part in iter(lambda:stream.read(CHUNK_BYTES),b""):
            h.update(part);total+=len(part)
    return {"path":str(p),"bytes":total,"sha256":h.hexdigest()}

def running_processes(cursor=0,size=100):
    if os.name!="nt":raise ValueError("WINDOWS_ONLY")
    if type(cursor)!=int or cursor<0 or type(size)!=int or not 1<=size<=PAGE_ITEMS:
        raise ValueError("PAGE_INPUT_INVALID")
    import csv
    import io
    run=subprocess.run(["tasklist.exe","/FO","CSV","/NH"],capture_output=True,
                       timeout=15,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    if run.returncode:raise ValueError("PROCESS_QUERY_FAILED")
    rows=list(csv.reader(io.StringIO(run.stdout.decode("mbcs","replace"))))
    items=[{"name":x[0],"pid":x[1]} for x in rows[cursor:cursor+size] if len(x)>1]
    next_cursor=cursor+len(items) if len(rows)>cursor+len(items) else None
    return {"items":items,"next_cursor":next_cursor}

def windows():
    if os.name!="nt":raise ValueError("WINDOWS_ONLY")
    import ctypes
    from ctypes import wintypes
    user32=ctypes.windll.user32
    callback_type=ctypes.WINFUNCTYPE(ctypes.c_bool,wintypes.HWND,wintypes.LPARAM)
    output=[]
    def callback(hwnd,_):
        if user32.IsWindowVisible(hwnd):
            n=user32.GetWindowTextLengthW(hwnd)
            if n>0:
                buf=ctypes.create_unicode_buffer(min(n+1,4096))
                user32.GetWindowTextW(hwnd,buf,len(buf))
                if buf.value:output.append({"hwnd":int(hwnd),"title":buf.value})
        return len(output)<1024
    fn=callback_type(callback)
    user32.EnumWindows(fn,0)
    return {"windows":output,"more_possible":len(output)>=1024}
