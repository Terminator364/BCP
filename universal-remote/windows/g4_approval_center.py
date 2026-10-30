"""BCP G4 Approval Center — local, explicit Windows user confirmation.
Never auto-approves. This UI is intentionally NOT an internet endpoint.
"""
from __future__ import annotations
import json
import time
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox
from g4_agent import PENDING, APPROVAL_KEY, approval_seal, json_atomic, spec_fingerprint

def pending():
    result=[]
    if not PENDING.is_dir():return result
    for path in sorted(PENDING.glob("*.json"),key=lambda p:p.stat().st_mtime,reverse=True)[:200]:
        try:
            item=json.loads(path.read_text("utf8"))
            if (item.get("status")=="PENDING" and
                item.get("expires",0)>=int(time.time()) and
                path.stem==item.get("id")):
                result.append(item)
        except (ValueError,OSError,TypeError):pass
    return result[:25]

def summary(item):
    spec=item["spec"]
    lines=[
        "TYPE : "+str(item["kind"]),
        "TICKET : "+str(item["id"]),
        "EXPIRATION : "+time.strftime("%H:%M:%S",time.localtime(item["expires"])),
        "ACTION : "+str(spec.get("path") or spec.get("exe") or "(unknown)")]
    if item["kind"]=="run":
        lines+=["ARGUMENTS : "+json.dumps(spec.get("args",[]),ensure_ascii=False)]
    if item["kind"]=="write_text":
        content=spec.get("text","")
        lines+=["CONTENU A ECRIRE (aperçu) : "+content[:4000],
                "TAILLE : "+str(len(content.encode("utf8")))+" octets"]
    return "\n".join(lines)

def main():
    root=tk.Tk()
    root.title("BCP G4 — Approbation des opérations Windows")
    root.geometry("810x510")
    root.minsize(630,370)
    root.configure(bg="#f5f6fa")
    ttk.Label(root,text="Autorisations locales Windows — G4",
              font=("Segoe UI",16,"bold")).pack(pady=(12,4))
    ttk.Label(root,text="Aucune action sensible n'est lancée sans ton accord sur ce PC. Aucun privilège administrateur ajouté.").pack()
    frame=ttk.Frame(root)
    frame.pack(fill="both",expand=True,padx=16,pady=10)
    tickets=tk.Listbox(frame,height=7,exportselection=False)
    tickets.pack(fill="x",pady=(0,8))
    details=tk.Text(frame,wrap="word",height=11,font=("Consolas",10))
    details.pack(fill="both",expand=True)
    details.config(state="disabled")
    state={"items":[]}
    def select(event=None):
        pos=tickets.curselection()
        details.config(state="normal")
        details.delete("1.0","end")
        if pos and pos[0]<len(state["items"]):
            details.insert("end",summary(state["items"][pos[0]]))
        details.config(state="disabled")
    tickets.bind("<<ListboxSelect>>",select)
    def refresh():
        state["items"]=pending()
        tickets.delete(0,"end")
        for item in state["items"]:
            spec=item["spec"]
            label=f'{item["kind"]}  |  {str(spec.get("path") or spec.get("exe") or item["id"])[:105]}'
            tickets.insert("end",label)
        select()
    def decide(approve):
        selected=tickets.curselection()
        if not selected or selected[0]>=len(state["items"]):
            messagebox.showinfo("BCP","Sélectionne une demande avant de continuer.",parent=root)
            return
        original=state["items"][selected[0]]
        ticket=original["id"]
        file=PENDING/(ticket+".json")
        try:
            current=json.loads(file.read_text("utf8"))
            if (current.get("status")!="PENDING" or
                current.get("expires",0)<int(time.time()) or
                spec_fingerprint(current)!=spec_fingerprint(original)):
                raise ValueError("La demande a changé ou a expiré")
            verb="APPROUVER" if approve else "REFUSER"
            if not messagebox.askyesno("Confirmer "+verb,
                   summary(current)[:7000]+"\n\nConfirmer "+verb+" ?",
                   parent=root,icon="warning",default="no"):
                return
            if approve:
                current["approved_at"]=int(time.time())
                current["status"]="APPROVED"
                current["approval_seal"]=approval_seal(current,APPROVAL_KEY.read_bytes())
            else:
                current["status"]="DENIED"
                current["approved_at"]=None
                current.pop("approval_seal",None)
            json_atomic(file,current)
            messagebox.showinfo("BCP","Demande "+("approuvée" if approve else "refusée")+
                         ". L'agent G4 peut maintenant la traiter selon ses règles.",
                         parent=root)
        except (OSError,ValueError,KeyError,TypeError) as e:
            messagebox.showerror("BCP",str(e),parent=root)
        refresh()
    buttons=ttk.Frame(root)
    buttons.pack(fill="x",padx=16,pady=(0,15))
    ttk.Button(buttons,text="Actualiser",command=refresh).pack(side="left")
    ttk.Button(buttons,text="Refuser",command=lambda:decide(False)).pack(side="right",padx=(6,0))
    ttk.Button(buttons,text="Approuver l'action sélectionnée",command=lambda:decide(True)).pack(side="right")
    refresh()
    root.mainloop()

if __name__=="__main__":
    main()
