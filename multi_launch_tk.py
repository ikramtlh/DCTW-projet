import tkinter as tk
from tkinter import ttk
import subprocess
import sys
import os

from coordinator_tk import CoordinatorApp
from decider_tk import DeciderApp

def launch_all():
    root = tk.Tk()
    root.title("Control Panel - Lancer interfaces")
    root.geometry("300x180")
    ttk.Label(root, text="Lancer les interfaces :", font=("Arial", 12, "bold")).pack(pady=8)

    btn_frame = ttk.Frame(root)
    btn_frame.pack(pady=10)

    def open_all():
        coord_win = tk.Toplevel(root)
        CoordinatorApp(coord_win)

        for i, name in enumerate(["decider1","decider2","decider3","decider4"], start=1):
            w = tk.Toplevel(root)
            DeciderApp(w, name)

        root.withdraw()  
    ttk.Button(btn_frame, text="Lancer toutes les interfaces", command=open_all).pack()

    root.mainloop()

if __name__ == "__main__":
    launch_all()
