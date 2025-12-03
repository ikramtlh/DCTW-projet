import tkinter as tk
from tkinter import ttk

from coordinator_tk import CoordinatorApp
from decider_tk import DeciderApp

def launch_all():
    root = tk.Tk()
    root.title("Launch Interfaces")
    root.geometry("300x180")
    ttk.Label(root, text="Launch the interfaces:", font=("Arial", 12, "bold")).pack(pady=8)

    btn_frame = ttk.Frame(root)
    btn_frame.pack(pady=10)

    def open_all():
        coord_win = tk.Toplevel(root)
        CoordinatorApp(coord_win)

        for i, name in enumerate([
            "decider_policeman",
            "decider_economist",
            "decider_environmental representative",
            "decider_public representative"
        ], start=1):
            w = tk.Toplevel(root)
            DeciderApp(w, name)

        root.withdraw()  
    ttk.Button(btn_frame, text="Launch all interfaces", command=open_all).pack()

    root.mainloop()

if __name__ == "__main__":
    launch_all()