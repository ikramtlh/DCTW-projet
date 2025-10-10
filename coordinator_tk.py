import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import requests
from openpyxl import load_workbook, Workbook

SERVER_UPLOAD = "http://localhost:5003/upload_matrix"

class CoordinatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Coordinateur DCTW")
        self.root.geometry("900x450")

        self.matrix = []
        self.entries = []

        # 🔸 Définis ici tes décideurs et leurs poids (somme = 100%)
        self.deciders_local = [
            {"name": "decider_ikram", "weight": 40.0},
            {"name": "decider_2", "weight": 25.0},
            {"name": "decider_3", "weight": 20.0},
            {"name": "decider_4", "weight": 15.0},
        ]

        # Top info
        top = ttk.Frame(root)
        top.pack(fill="x", padx=10, pady=8)
        self.info_label = ttk.Label(top, text="Welcome coordinateur", font=("Arial", 14, "bold"))
        self.info_label.pack(side="left")

        # Buttons
        btn_frame = ttk.Frame(root)
        btn_frame.pack(fill="x", padx=10, pady=6)
        ttk.Button(btn_frame, text="📂 Upload Excel", command=self.load_excel).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="➕ New", command=self.create_matrix_dialog).pack(side="left", padx=4)
        self.save_btn = ttk.Button(btn_frame, text="💾 Save Excel", command=self.save_excel, state="disabled")
        self.save_btn.pack(side="left", padx=4)
        self.send_btn = ttk.Button(btn_frame, text="🚀 Send", command=self.send_matrix, state="disabled")
        self.send_btn.pack(side="left", padx=4)
        ttk.Button(btn_frame, text="👥 Show Deciders", command=self.show_deciders_local).pack(side="left", padx=4)

        # Status area
        self.status = tk.Text(root, height=6, wrap="word", state="disabled")
        self.status.pack(fill="x", padx=10, pady=6)

        # Matrix frame
        self.canvas = tk.Canvas(root)
        self.frame_container = ttk.Frame(self.canvas)
        self.vsb = ttk.Scrollbar(root, orient="vertical", command=self.canvas.yview)
        self.hsb = ttk.Scrollbar(root, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=self.vsb.set, xscrollcommand=self.hsb.set)
        self.vsb.pack(side="right", fill="y")
        self.hsb.pack(side="bottom", fill="x")
        self.canvas.pack(fill="both", expand=True, padx=10, pady=6)
        self.canvas.create_window((0, 0), window=self.frame_container, anchor="nw")
        self.frame_container.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

    # --- Log Helper ---
    def log(self, msg):
        self.status.configure(state="normal")
        self.status.insert("end", msg + "\n")
        self.status.see("end")
        self.status.configure(state="disabled")

    # --- Matrice ---
    def clear_grid(self):
        for row in self.entries:
            for e in row:
                e.destroy()
        self.entries = []

    def build_grid(self):
        self.clear_grid()
        rows = len(self.matrix)
        cols = len(self.matrix[0]) if rows > 0 else 0
        self.entries = [[None for _ in range(cols)] for _ in range(rows)]
        for i in range(rows):
            for j in range(cols):
                val = self.matrix[i][j] if i < len(self.matrix) and j < len(self.matrix[i]) else ""
                e = ttk.Entry(self.frame_container, width=15)
                e.grid(row=i, column=j, padx=2, pady=2, sticky="nsew")
                e.insert(0, val)
                e.bind("<KeyRelease>", lambda ev: self.on_edit())
                self.entries[i][j] = e

    def update_matrix_from_entries(self):
        self.matrix = [[cell.get() for cell in row] for row in self.entries]

    def on_edit(self):
        self.save_btn.config(state="enabled")
        self.send_btn.config(state="enabled")

    # --- Excel ---
    def load_excel(self):
        path = filedialog.askopenfilename(title="Choisir fichier Excel", filetypes=[("Excel files","*.xlsx")])
        if not path:
            return
        try:
            wb = load_workbook(path)
            ws = wb.active
            self.matrix = [[str(c) if c is not None else "" for c in r] for r in ws.iter_rows(values_only=True)]
            if not self.matrix:
                messagebox.showwarning("Vide", "Feuille Excel vide.")
                return
            self.build_grid()
            self.log(f"✅ Matrice chargée depuis {path}")
            self.save_btn.config(state="enabled")
            self.send_btn.config(state="enabled")
            self.info_label.config(text=f"📂 Chargée: {path}")
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de charger Excel: {e}")

    def create_matrix_dialog(self):
        rows = simpledialog.askinteger("Lignes", "Combien de choix (lignes) ?", initialvalue=3, minvalue=1, maxvalue=50)
        if rows is None:
            return
        cols = simpledialog.askinteger("Colonnes", "Combien de critères (colonnes) ?", initialvalue=3, minvalue=1, maxvalue=50)
        if cols is None:
            return
        self.matrix = [["" for _ in range(cols)] for _ in range(rows)]
        self.build_grid()
        self.log("🧮 Nouvelle matrice créée (vide).")
        self.save_btn.config(state="enabled")
        self.send_btn.config(state="enabled")
        self.info_label.config(text="➕ Nouvelle matrice")

    def save_excel(self):
        self.update_matrix_from_entries()
        path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel files","*.xlsx")])
        if not path:
            return
        try:
            wb = Workbook()
            ws = wb.active
            for i, row in enumerate(self.matrix, start=1):
                for j, val in enumerate(row, start=1):
                    ws.cell(row=i, column=j, value=val)
            wb.save(path)
            self.log(f"💾 Matrice sauvegardée: {path}")
            self.info_label.config(text=f"💾 Sauvegardée: {path}")
            self.save_btn.config(state="disabled")
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de sauvegarder: {e}")

    def send_matrix(self):
        self.update_matrix_from_entries()
        if not self.matrix:
            messagebox.showwarning("Erreur", "Aucune matrice à envoyer.")
            return
        try:
            r = requests.post(SERVER_UPLOAD, json={"matrix": self.matrix}, timeout=5)
            if r.status_code == 200:
                self.log("🚀 Matrice envoyée au serveur.")
                self.info_label.config(text="🚀 Matrice envoyée.")
                self.save_btn.config(state="disabled")
            else:
                messagebox.showerror("Erreur serveur", f"{r.status_code}: {r.text}")
        except Exception as e:
            messagebox.showerror("Erreur", f"Connexion serveur impossible: {e}")

    # --- Décideurs locaux ---
    def show_deciders_local(self):
        win = tk.Toplevel(self.root)
        win.title("Décideurs définis ")
        win.geometry("400x300")

        cols = ("Nom du Décideur", "Poids (%)")
        tree = ttk.Treeview(win, columns=cols, show="headings")
        tree.heading("Nom du Décideur", text="Nom du Décideur")
        tree.heading("Poids (%)", text="Poids (%)")
        tree.column("Nom du Décideur", width=200)
        tree.column("Poids (%)", width=100, anchor="center")
        tree.pack(fill="both", expand=True, padx=10, pady=10)

        total_weight = 0
        for d in self.deciders_local:
            tree.insert("", "end", values=(d["name"], f"{d['weight']:.2f} %"))
            total_weight += d["weight"]

        # ttk.Label(win, text=f"Somme totale = {total_weight:.2f} %", foreground="green").pack(pady=5)
        # self.log("✅ Décideurs locaux affichés.")

if __name__ == "__main__":
    root = tk.Tk()
    app = CoordinatorApp(root)
    root.mainloop()
