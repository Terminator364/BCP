"""BCP local owner enrollment center. No enrollment via HTTP or legacy G2 token."""
from __future__ import annotations
import os
from pathlib import Path
import tkinter as tk
from tkinter import ttk,messagebox
from g4_device_identity import DeviceRegistry
import g4_owner_gateway as owner

ROOT=Path(os.environ["LOCALAPPDATA"])/"BCP-Universal-Remote"
REGISTRY=ROOT/"private-state"/"g4"/"device-registry"

def main():
    registry=DeviceRegistry(REGISTRY)
    root=tk.Tk()
    root.title("BCP - Identité unique et confiance propriétaire")
    root.geometry("750x620")
    root.minsize(690,555)
    body=ttk.Frame(root,padding=20)
    body.pack(fill="both",expand=True)
    ttk.Label(body,text="BCP · IDENTITÉS ET DROITS WINDOWS",
              font=("Segoe UI",16,"bold")).pack(anchor="w")
    ttk.Label(body,text=("Chaque Samsung doit prouver une clé indépendante, "
        "puis recevoir une approbation sur ce PC. L'ancien code partagé G2 "
        "ne donne aucun droit de contrôle général."),
        wraplength=670).pack(anchor="w",pady=(9,12))
    ttk.Label(body,text=("Après cette validation unique, le profil propriétaire "
        "est durable jusqu'à révocation : pas de quota arbitraire de 30 minutes, "
        "20 opérations ou dossier unique. Les ACL Windows et UAC restent applicables."),
        wraplength=670).pack(anchor="w")
    ttk.Separator(body).pack(fill="x",pady=13)
    ttk.Label(body,text="Demandes reçues depuis Android",font=("Segoe UI",12,"bold")).pack(anchor="w")
    pending=ttk.Combobox(body,state="readonly",width=75)
    pending.pack(fill="x",pady=(7,7))
    pending_map={}
    code=ttk.Entry(body,width=16)
    ttk.Label(body,text="Code à 6 chiffres affiché sur le téléphone").pack(anchor="w")
    code.pack(anchor="w",pady=(5,8))
    high_risk=tk.BooleanVar(value=True)
    ttk.Checkbutton(body,variable=high_risk,
      text="Confirmer les actions Windows sensibles (commandes, installations, bureau)"
    ).pack(anchor="w",pady=6)
    owner_status=tk.StringVar(value="Aucune activation non vérifiée.")
    ttk.Label(body,textvariable=owner_status,wraplength=650,
              font=("Segoe UI",10,"bold")).pack(anchor="w",pady=(8,6))
    enrolled=ttk.Combobox(body,state="readonly",width=75)
    ttk.Label(body,text="Appareils connus / révocation indépendante",
              font=("Segoe UI",12,"bold")).pack(anchor="w",pady=(15,3))
    enrolled.pack(fill="x",pady=(5,6))
    enrolled_map={}

    def refresh():
        pending_map.clear()
        requests=registry.pending_public()
        choices=[]
        for item in requests:
            label=item["label"]+" · "+item["device_id"][:12]+" · attend approbation"
            pending_map[label]=item["device_id"]
            choices.append(label)
        pending["values"]=choices
        if choices:pending.current(0)
        else:pending.set("")
        enrolled_map.clear()
        devices=registry.enrolled_public()
        entries=[]
        for item in devices:
            status=owner.public_status(item["device_id"])
            label=(item["label"]+" · "+item["device_id"][:12]+
                  (" · RÉVOQUÉ" if item["revoked"] else
                   " · PROPRIÉTAIRE" if status["trusted"] else " · identité validée"))
            entries.append(label);enrolled_map[label]=item["device_id"]
        enrolled["values"]=entries
        if entries:enrolled.current(0)
        else:enrolled.set("")
        owner_status.set(str(len(requests))+" demande(s) en attente · "+
                         str(sum(not x["revoked"] for x in devices))+
                         " appareil(s) avec identité individuelle validée.")

    def approve():
        selected=pending_map.get(pending.get())
        typed=code.get().strip()
        if not selected:
            messagebox.showwarning("BCP","Aucune demande Android en attente.",parent=root)
            return
        if len(typed)!=6 or not typed.isdecimal():
            messagebox.showwarning("BCP","Saisir les six chiffres du Samsung.",parent=root)
            return
        if not messagebox.askyesno("BCP : confirmation locale",
            "Vous confirmez que le code provient de VOTRE téléphone ?\n\n"
            "BCP enregistrera cette identité et activera le profil propriétaire "
            "révocable pour cet appareil uniquement.\n\n"
            "Cela n'ouvre aucun accès public et ne contourne pas Windows/UAC.",
            default="no",parent=root):
            return
        try:
            identity=registry.approve_local(selected,typed,local_user_confirmed=True)
            status=owner.local_enroll_verified_device(selected,"operator",
                 high_risk_confirmation=high_risk.get())
            code.delete(0,tk.END)
            messagebox.showinfo("BCP",
                "Téléphone reconnu individuellement. Profil propriétaire activé.\n"
                "Le contrôle sensible reste soumis aux droits Windows.",parent=root)
        except Exception as exc:
            messagebox.showerror("BCP",
                "Activation incomplète : "+type(exc).__name__+
                "\nLe système refuse les opérations sans les deux preuves.",parent=root)
        refresh()

    def enable_existing_identity():
        selected=enrolled_map.get(enrolled.get())
        if not selected:
            messagebox.showwarning("BCP","Sélectionne un appareil déjà identifié.",parent=root)
            return
        if not messagebox.askyesno("BCP : confirmation propriétaire",
            "Activer ou réparer le profil propriétaire de ce téléphone "
            "déjà identifié, sans lui donner de droits supplémentaires "
            "au-delà des droits du compte Windows ?",
            default="no",parent=root):
            return
        try:
            owner.local_enroll_verified_device(selected,"operator",
                high_risk_confirmation=high_risk.get())
            messagebox.showinfo("BCP","Profil propriétaire confirmé et activé.",parent=root)
        except Exception as exc:
            messagebox.showerror("BCP","Profil non activé : "+
                type(exc).__name__,parent=root)
        refresh()

    def revoke():
        selected=enrolled_map.get(enrolled.get())
        if not selected:
            messagebox.showwarning("BCP","Sélectionnez un appareil.",parent=root);return
        if not messagebox.askyesno("Révoquer cet appareil",
            "Supprimer le droit de ce téléphone sans toucher aux autres appareils ?",
            default="no",parent=root):return
        try:
            registry.revoke_local(selected,local_user_confirmed=True)
            try:owner.local_revoke(selected)
            except Exception:pass
            messagebox.showinfo("BCP","Appareil révoqué. Son HMAC individuel est refusé.",parent=root)
        except Exception as exc:
            messagebox.showerror("BCP","Révocation échouée : "+type(exc).__name__,parent=root)
        refresh()

    buttons=ttk.Frame(body);buttons.pack(fill="x",pady=12)
    ttk.Button(buttons,text="Approuver ce téléphone une seule fois",command=approve).pack(side="left")
    ttk.Button(buttons,text="Actualiser",command=refresh).pack(side="right")
    ttk.Button(body,text="Activer un appareil déjà identifié",command=enable_existing_identity).pack(anchor="w",pady=5)
    ttk.Button(body,text="Révoquer l'appareil sélectionné",command=revoke).pack(anchor="w",pady=10)
    ttk.Label(body,text=("Aucune action ne s'active à l'ouverture de cette fenêtre. "
        "Les secrets individuels restent hors des conversations et du dépôt GitHub."),
        wraplength=670).pack(anchor="w",pady=10)
    refresh()
    root.mainloop()

if __name__=="__main__":main()
