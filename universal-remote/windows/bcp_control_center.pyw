"""BCP Control Center — permanent, single-window, single-shortcut Windows UI.

No admin elevation, no public networking, no credential export, no automatic
owner approval. Starting or refreshing the UI never closes the window.
"""
from __future__ import annotations
import json,os,socket,subprocess,sys,threading,time
from pathlib import Path
import tkinter as tk
from tkinter import ttk
from datetime import datetime

ROOT=Path(os.environ["LOCALAPPDATA"])/"BCP-Universal-Remote"
REGISTRY_PATH=ROOT/"private-state"/"g4"/"device-registry"
WINDOW_TITLE="BCP — Centre de contrôle"
_registry_instance=None
_registry_init_lock=threading.Lock()

def registry_instance():
    """Initialise Windows ACL-backed store only once per UI process."""
    global _registry_instance
    if _registry_instance is None:
        with _registry_init_lock:
            if _registry_instance is None:
                from g4_device_identity import DeviceRegistry
                _registry_instance=DeviceRegistry(REGISTRY_PATH)
    return _registry_instance
BG="#F3F6FA";INK="#132439";MUTED="#5C6B7A";BLUE="#1461AB";CARD="#FFFFFF"

def read_json(path):
    try:return json.loads(Path(path).read_text("utf-8-sig"))
    except (OSError,UnicodeError,ValueError):return {}

def service_alive():
    try:
        with socket.create_connection(("127.0.0.1",8898),.65):return True
    except OSError:return False

def latest_heartbeat():
    return read_json(ROOT/"state"/"g2-phone-status.json")

def status_snapshot():
    connected=service_alive()
    heartbeat=latest_heartbeat()
    try:
        registry=registry_instance()
        pending=registry.pending_public()
        enrolled=registry.enrolled_public()
        registry_problem=None
    except Exception as ex:
        pending=[];enrolled=[];registry_problem=type(ex).__name__
    try:
        from g4_owner_gateway import load_policy
        from g4_owner_transactions import owner_hash
        policy=load_policy()
        for device in enrolled:
            device["owner"]=policy.public_status(
                owner_hash(device["device_id"])).get("trusted",False)
    except Exception:
        for device in enrolled:device["owner"]=False
    return {"connected":connected,"phone":heartbeat,"pending":pending,
            "enrolled":enrolled,"registry_problem":registry_problem}

def _start_existing_service():
    """Prefer bounded socket-based starter, no slow WMI/NetTCPConnection."""
    flags=getattr(subprocess,"CREATE_NO_WINDOW",0)
    fast=ROOT/"g2_autostart_fast.py"
    if fast.is_file():
        subprocess.Popen([sys.executable,str(fast)],cwd=str(ROOT),
            stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,creationflags=flags)
        return True
    script=ROOT/"g2_autostart.ps1"
    if not script.is_file():return False
    subprocess.Popen(["powershell.exe","-NoProfile","-NonInteractive",
      "-ExecutionPolicy","Bypass","-File",str(script)],cwd=str(ROOT),
      stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
      stderr=subprocess.DEVNULL,creationflags=flags)
    return True

def show_existing_window():
    if os.name!="nt":return False
    try:
        import ctypes
        hwnd=ctypes.windll.user32.FindWindowW(None,WINDOW_TITLE)
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd,9)
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            return True
    except Exception:pass
    return False

class Center:
    def __init__(self):
        self.root=tk.Tk()
        self.root.title(WINDOW_TITLE)
        self.root.geometry("940x650")
        self.root.minsize(730,560)
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW",self.hide)
        self.done=False
        self.busy=False
        self.last_auto_start=0
        self.snapshot={}
        self.selected_pending=None
        self.status=tk.StringVar(value="Démarrage et vérification locale…")
        self.phone=tk.StringVar(value="Téléphone : vérification…")
        self.challenge=tk.StringVar(value="Aucune demande en attente.")
        self.log=tk.StringVar(value="BCP reste actif dans cette fenêtre.")
        self.note=tk.StringVar(value="Une confirmation locale unique est requise pour un nouveau téléphone.")
        style=ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("BCP.TNotebook",background=BG,borderwidth=0)
        style.configure("BCP.TNotebook.Tab",font=("Segoe UI",11),padding=(18,12))
        style.configure("BCP.TButton",font=("Segoe UI",11),padding=(12,9))
        style.configure("BCP.TLabel",font=("Segoe UI",11),background=BG,foreground=INK)
        style.configure("Sub.TLabel",font=("Segoe UI",10),background=BG,foreground=MUTED)
        style.configure("Hero.TLabel",font=("Segoe UI",22,"bold"),background=BG,foreground=INK)
        header=ttk.Frame(self.root,padding=(24,20))
        header.pack(fill="x")
        ttk.Label(header,text="BCP · CENTRE DE CONTRÔLE",style="Hero.TLabel").pack(anchor="w")
        ttk.Label(header,text="Une fenêtre. Une connexion. Les vérifications se font automatiquement.",
                  style="Sub.TLabel").pack(anchor="w",pady=(5,0))
        self.tabs=ttk.Notebook(self.root,style="BCP.TNotebook")
        self.tabs.pack(fill="both",expand=True,padx=20,pady=(0,15))
        self.overview=ttk.Frame(self.tabs,padding=22)
        self.devices=ttk.Frame(self.tabs,padding=22)
        self.tools=ttk.Frame(self.tabs,padding=22)
        self.diagnostics=ttk.Frame(self.tabs,padding=22)
        for panel,label in ((self.overview,"Accueil"),(self.devices,"Mes appareils"),
                            (self.tools,"Outils"),(self.diagnostics,"Diagnostic")):
            self.tabs.add(panel,text=label)
        self._overview()
        self._devices()
        self._tools()
        self._diagnostics()
        foot=ttk.Frame(self.root,padding=(24,5,24,18))
        foot.pack(fill="x")
        ttk.Label(foot,textvariable=self.note,style="Sub.TLabel",wraplength=850).pack(anchor="w")
        self.root.after(100,self.refresh)
        self.root.after(1300,self.auto_service)

    def _overview(self):
        p=self.overview
        ttk.Label(p,text="État actuel",font=("Segoe UI",17,"bold")).pack(anchor="w",pady=(0,12))
        ttk.Label(p,textvariable=self.status,font=("Segoe UI",14,"bold"),
                  wraplength=760).pack(anchor="w",pady=(0,14))
        ttk.Label(p,textvariable=self.phone,wraplength=770).pack(anchor="w",pady=(0,20))
        ttk.Label(p,text="Le service G2 démarre ou se rétablit automatiquement quand il est indisponible.",
                  style="Sub.TLabel",wraplength=770).pack(anchor="w")
        ttk.Label(p,text="Les transferts et le contrôle propriétaire restent protégés par les droits Windows.",
                  style="Sub.TLabel",wraplength=770).pack(anchor="w",pady=(10,10))

    def _devices(self):
        p=self.devices
        ttk.Label(p,text="Appairage propriétaire",font=("Segoe UI",17,"bold")).pack(anchor="w")
        ttk.Label(p,text="Une seule approbation sur ce PC ; plus de saisie de code.",
                  style="Sub.TLabel").pack(anchor="w",pady=(5,14))
        ttk.Label(p,textvariable=self.challenge,font=("Segoe UI",15,"bold"),
                  wraplength=760).pack(anchor="w",pady=(0,13))
        ttk.Label(p,text="Compare le code affiché ici à celui de ton téléphone. Si les deux "
                        "codes sont identiques, autorise cet appareil.",wraplength=780).pack(anchor="w",pady=(0,15))
        self.approve=ttk.Button(p,text="Oui, c'est mon téléphone — autoriser",
                                command=self.approve_one,style="BCP.TButton")
        self.approve.pack(anchor="w")
        self.approve.state(["disabled"])
        ttk.Separator(p).pack(fill="x",pady=20)
        ttk.Label(p,text="Appareils déjà reconnus",font=("Segoe UI",12,"bold")).pack(anchor="w")
        self.device_list=tk.Listbox(p,height=6,relief="flat",font=("Segoe UI",10),
                                    selectmode="browse",activestyle="none")
        self.device_list.pack(fill="x",pady=(9,8))
        ttk.Button(p,text="Révoquer l'appareil sélectionné",
                   command=self.revoke_selected).pack(anchor="w")

    def _tools(self):
        p=self.tools
        ttk.Label(p,text="Tes outils",font=("Segoe UI",17,"bold")).pack(anchor="w",pady=(0,10))
        ttk.Label(p,text="Les autres lanceurs BCP sont rangés dans un dossier d'archives "
                        "réversible, pas supprimés. Toutes les fonctions BCP restent ici.",
                        wraplength=760).pack(anchor="w")
        ttk.Button(p,text="Ouvrir les fichiers BCP",command=lambda:self.open_path(ROOT)).pack(anchor="w",pady=(15,6))
        ttk.Button(p,text="Ouvrir les anciens raccourcis",
                   command=lambda:self.open_path(Path.home()/"Desktop"/"_Projets et outils"/"BCP - anciens raccourcis")).pack(anchor="w",pady=6)

    def _diagnostics(self):
        p=self.diagnostics
        ttk.Label(p,text="Diagnostic automatique",font=("Segoe UI",17,"bold")).pack(anchor="w")
        ttk.Label(p,textvariable=self.log,wraplength=770).pack(anchor="w",pady=(18,12))
        ttk.Label(p,text="Les vérifications et la reconnexion sont automatiques. "
                        "Aucune installation système, commande administrateur "
                        "ou autorisation sensible n'est lancée silencieusement.",
                  style="Sub.TLabel",wraplength=770).pack(anchor="w")
        ttk.Button(p,text="Actualiser maintenant",command=self.refresh).pack(anchor="w",pady=16)
        ttk.Button(p,text="Quitter complètement BCP",command=self.quit).pack(anchor="w",pady=7)

    def hide(self):
        # X minimizes instead of killing the only control center.
        # Reopening the desktop icon restores the same window.
        self.root.iconify()

    def quit(self):
        self.done=True
        self.root.destroy()

    def _async(self,fn,callback):
        def worker():
            try:result=fn()
            except Exception as ex:result={"error":type(ex).__name__}
            if not self.done:
                try:self.root.after(0,lambda:callback(result))
                except RuntimeError:pass
        threading.Thread(target=worker,daemon=True,name="BCP-UI-Worker").start()

    def refresh(self):
        if self.done:return
        if not self.busy:
            self.busy=True
            self._async(status_snapshot,self._update)
        self.root.after(5000,self.refresh)

    def _update(self,value):
        self.busy=False
        if self.done:return
        if "error" in value:
            self.status.set("Diagnostic temporairement indisponible.")
            self.log.set("Le centre reste ouvert. Prochain contrôle automatique.")
            return
        self.snapshot=value
        connected=value["connected"]
        self.status.set("● PC connecté — service BCP disponible" if connected else
                        "● Service BCP indisponible — reconnexion automatique")
        phone=value["phone"]
        code=phone.get("version_code")
        self.phone.set("Samsung : version "+str(code)+" · "+str(phone.get("network","inconnu"))+
              (" · connecté" if phone.get("app_visible") else " · dernière activité connue")
              if code else "Samsung : aucun rapport récent")
        registry_problem=value["registry_problem"]
        self.log.set("BCP local : "+("actif" if connected else "vérification")+
                     " ; registre : "+("opérationnel" if not registry_problem else registry_problem)+
                     " ; demandes : "+str(len(value["pending"]))+
                     " ; appareils : "+str(len(value["enrolled"])))
        self.device_list.delete(0,tk.END)
        for item in value["enrolled"]:
            label=item["label"]+" · "+item["device_id"][:8]+(
                " · RÉVOQUÉ" if item["revoked"] else
                " · AUTORISÉ" if item.get("owner") else " · identité vérifiée")
            self.device_list.insert(tk.END,label)
        pending=value["pending"]
        if pending:
            item=pending[0]
            self.selected_pending=item["device_id"]
            try:
                code=registry_instance().pending_code_local(self.selected_pending)
                self.challenge.set("Demande : "+item["label"]+"\nCode sur ce PC : "+code)
                self.approve.state(["!disabled"])
            except Exception:
                self.challenge.set("Demande en cours de préparation.")
                self.approve.state(["disabled"])
        else:
            self.selected_pending=None
            self.challenge.set("Aucune nouvelle autorisation nécessaire.")
            self.approve.state(["disabled"])
        if not connected:self.auto_service()

    def auto_service(self):
        if self.done or service_alive():return
        now=time.monotonic()
        if now-self.last_auto_start<60:return
        self.last_auto_start=now
        self._async(_start_existing_service,lambda result:
                    self.note.set("Reconnexion BCP lancée automatiquement." if result is True
                      else "Le démarrage local requiert une réparation manuelle."))

    def approve_one(self):
        device=self.selected_pending
        if not device:return
        self.approve.state(["disabled"])
        def work():
            from g4_owner_gateway import local_enroll_verified_device
            registry=registry_instance()
            challenge=registry.pending_code_local(device)
            registry.approve_local(device,challenge,local_user_confirmed=True)
            return local_enroll_verified_device(device,"operator",
                    high_risk_confirmation=True)
        def completed(result):
            if "error" in result:self.note.set("Autorisation non terminée : "+result["error"]+". Aucune élévation Windows.")
            else:self.note.set("Appareil confirmé une fois. Les prochaines connexions sont automatiques.")
            self.refresh()
        self._async(work,completed)

    def revoke_selected(self):
        selection=self.device_list.curselection()
        devices=self.snapshot.get("enrolled",[])
        if not selection or selection[0]>=len(devices):return
        device=devices[selection[0]]
        # Revoke is deliberately a two-stage confirmation: destructive trust
        # removal must not be triggered by accidental click.
        from tkinter import messagebox
        if not messagebox.askyesno("BCP", "Révoquer uniquement "+device["label"]+" ?",
                                   parent=self.root):return
        def work():
            from g4_owner_gateway import local_revoke
            registry=registry_instance()
            registry.revoke_local(device["device_id"],local_user_confirmed=True)
            try:local_revoke(device["device_id"])
            except Exception:pass
            return {"revoked":True}
        self._async(work,lambda res:self.refresh())

    def open_path(self,path):
        p=Path(path)
        if p.is_dir():os.startfile(str(p))
        else:self.note.set("Dossier indisponible ; aucune action nécessaire.")

    def run(self):
        self.root.mainloop()

def main():
    if show_existing_window():return
    app=Center()
    if "--minimized" in sys.argv[1:]:
        app.root.after(120,app.root.iconify)
    app.run()

if __name__=="__main__":main()
