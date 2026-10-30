"""BCP - local Windows owner profile manager. No API can self-enroll."""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk,messagebox
import getpass
import g4_owner_gateway as owner

def main():
    root=tk.Tk()
    root.title("BCP - Confiance propriétaire durable")
    root.geometry("700x480")
    root.minsize(660,420)
    body=ttk.Frame(root,padding=22)
    body.pack(fill="both",expand=True)
    ttk.Label(body,text="BCP · PROFIL PROPRIÉTAIRE",
              font=("Segoe UI",16,"bold")).pack(anchor="w")
    ttk.Label(body,text=("Contrôlez les lecteurs et ressources de MBMPC selon "
      "vos droits Windows, sans limite de dossier, de minutes ou de nombre d'opérations."),
      wraplength=640).pack(anchor="w",pady=(12,8))
    ttk.Label(body,text=("La première activation exige votre décision sur ce PC. "
      "Elle n'autorise ni élévation UAC silencieuse ni accès Internet public."),
      wraplength=640).pack(anchor="w")
    status=tk.StringVar()
    ttk.Label(body,textvariable=status,wraplength=640,
              font=("Segoe UI",11,"bold")).pack(anchor="w",pady=(16,6))
    ttk.Separator(body).pack(fill="x",pady=(8,12))
    ttk.Label(body,text=("Important : l'appairage actuel utilise encore une clé "
      "partagée historique. Le futur protocole donnera une identité unique à chaque "
      "téléphone. Révoquer ce profil coupe l'autorisation de ce canal."),
      wraplength=640).pack(anchor="w")
    sensitive=tk.BooleanVar(value=True)
    ttk.Checkbutton(body,
      text="Conserver une confirmation contextuelle pour les actions sensibles",
      variable=sensitive).pack(anchor="w",pady=(16,6))
    ttk.Label(body,text=("La lecture générale des fichiers n'a pas de confirmation "
       "répétée. Les commandes et changements sensibles restent gouvernés par "
       "la préférence choisie ci-dessus et les droits Windows."),
       wraplength=640).pack(anchor="w")
    buttons=ttk.Frame(body);buttons.pack(fill="x",pady=(22,6))
    def refresh():
        s=owner.public_status()
        status.set(("Actif : "+str(s["profile"])+" | catégories "+
                  str(len(s["categories"]))+" | pas de quota ni expiration")
                   if s["trusted"] else "Aucun profil propriétaire actif.")
    def activate():
        if not messagebox.askyesno("BCP : approbation locale",
            "Autoriser durablement ce canal appairé à utiliser les capacités "
            "BCP au niveau de votre compte Windows ?\n\n"
            "Aucune durée de 30 minutes, aucun quota de 20 actions, "
            "aucune limite à un seul dossier.\n\n"
            "Pour les fonctions sensibles, Windows/UAC et votre préférence de "
            "confirmation resteront applicables.",
            parent=root,default="no"):
            return
        try:
            profile=owner.local_enroll(profile="operator",
                        high_risk_confirmation=sensitive.get())
            messagebox.showinfo("BCP","Profil propriétaire activé sur MBMPC."
                 "\nVous pouvez le révoquer dans cette même fenêtre.",parent=root)
        except Exception as e:
            messagebox.showerror("BCP","Activation impossible : "+
                type(e).__name__+". Aucun droit n'a été accordé automatiquement.",parent=root)
        refresh()
    def revoke():
        if not messagebox.askyesno("BCP : révocation",
            "Révoquer maintenant l'accès propriétaire de ce canal ?",
            default="no",parent=root):return
        try:
            owner.local_revoke()
            messagebox.showinfo("BCP","Profil propriétaire révoqué.",parent=root)
        except Exception as e:
            messagebox.showerror("BCP","Révocation impossible : "+
                  type(e).__name__,parent=root)
        refresh()
    ttk.Button(buttons,text="Activer une seule fois",command=activate).pack(side="left")
    ttk.Button(buttons,text="Révoquer",command=revoke).pack(side="left",padx=12)
    ttk.Button(buttons,text="Actualiser",command=refresh).pack(side="right")
    refresh()
    root.mainloop()

if __name__=="__main__":
    main()
