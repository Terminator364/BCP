"""BCP G4 one-click field test: fresh ticket + user-driven Windows approval UI."""
import tkinter as tk
from tkinter import messagebox
from g4_agent import ROOT
from g4_approval_center import pending, main as approval_main
from g4_prepare_real_approval import main as prepare

def main():
    destination=ROOT/"G4-Staging-Workspace"/"G4_FIELD_APPROVAL_PROOF_20261030.txt"
    if destination.exists():
        top=tk.Tk();top.withdraw()
        messagebox.showinfo("BCP G4","Le fichier d'attestation existe déjà : l'essai a été réalisé.",parent=top)
        top.destroy()
        return
    if not any(
      entry.get("spec",{}).get("path")==str(destination)
      for entry in pending()):
        prepare()
    approval_main()
if __name__=="__main__":
    main()
