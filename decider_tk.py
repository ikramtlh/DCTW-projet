import tkinter as tk
from tkinter import ttk, messagebox  
import threading
import socketio

SERVER_WS = "http://localhost:5003"

DECIDER_PREFS = {
    "decider_policeman": [
        ["Nuisances", 7.51, 0.6, 0.3, 1],
        ["Bruit", 13.63, 0.6, 0.3, 0.8],
        ["Impacts", 13.63, 0, 0, 0],
        ["Géotechnique", 13.63, 110, 55, 220],
        ["Équipements", 17.2, 10, 5, 20],
        ["Accessibilité", 17.2, 0.6, 0.3, 1.2],
        ["Climat", 17.2, 0.6, 0.3, 1.5],
    ],
    "decider_economist": [
        ["Nuisances", 17.38, 0.5, 0.25, 1],
        ["Bruit", 29.4, 0.6, 0.3, 1.2],
        ["Impacts", 6.16, 0.3, 0.15, 0.6],
        ["Géotechnique", 6.16, 99, 45, 180],
        ["Équipements", 6.16, 6, 3, 12],
        ["Accessibilité", 17.38, 0.5, 0.25, 1],
        ["Climat", 17.38, 0.5, 0.25, 1],
    ],
    "decider_environmental representative": [
        ["Nuisances", 4.96, 0.7, 0.35, 1.4],
        ["Bruit", 7.08, 0.7, 0.35, 1.4],
        ["Impacts", 17.31, 0.6, 0.3, 1.2],
        ["Géotechnique", 18.93, 100, 50, 200],
        ["Équipements", 18.93, 8, 4, 16],
        ["Accessibilité", 17.52, 1, 0.5, 2],
        ["Climat", 15.27, 0.7, 0.35, 1.4],
    ],
    "decider_public representative": [
        ["Nuisances", 6.15, 0.4, 0.2, 0.8],
        ["Bruit", 19.57, 0.4, 0.2, 0.8],
        ["Impacts", 13.79, 0.2, 0.1, 0.4],
        ["Géotechnique", 13.79, 60, 30, 120],
        ["Équipements", 13.79, 4, 2, 8],
        ["Accessibilité", 16.45, 0.6, 0.15, 0.6],
        ["Climat", 16.45, 0.4, 0.2, 0.8],
    ],
}


class DeciderApp:
    def __init__(self, root, name):
        self.root = root
        self.name = name
        self.root.title(f"DÉCIDEUR - {name}")
        self.root.geometry("600x450")

        top = ttk.Frame(root)
        top.pack(fill="x", padx=8, pady=8)
        ttk.Label(top, text=f"Décideur: {name}", font=("Arial", 14, "bold")).pack(side="left")

        self.status = ttk.Label(root, text="⏳ En attente du coordinateur...", foreground="gray")
        self.status.pack(fill="x", padx=8, pady=4)

        self.tree = ttk.Treeview(root, show="headings")
        self.tree.pack(fill="both", expand=True, padx=8, pady=6)

        btn_frame = ttk.Frame(root)
        btn_frame.pack(fill="x", padx=8, pady=6)
        self.pref_btn = ttk.Button(btn_frame, text="Préférences", command=self.show_preferences, state="disabled")
        self.pref_btn.pack(side="left")

        self.sio = socketio.Client(logger=False, reconnection=True)
        self.sio.on("matrix_update", self._on_matrix_update)
        self.sio.on("connect", lambda: self._log("🟢 Connecté au serveur – attente de matrice..."))
        self.sio.on("disconnect", lambda: self._log("🔴 Déconnecté du serveur"))

        t = threading.Thread(target=self._start_socketio, daemon=True)
        t.start()

    def _start_socketio(self):
        try:
            self.sio.connect(SERVER_WS)
            self.sio.wait()
        except Exception as e:
            self.root.after(0, lambda: self._log(f"Erreur connexion SocketIO: {e}"))

    def _log(self, msg):
        self.status.config(text=msg)

    def _on_matrix_update(self, payload):
        matrix = payload.get("matrix") if isinstance(payload, dict) else payload
        if not matrix:
            return
        self.root.after(0, lambda: self._show_matrix(matrix))

    def _show_matrix(self, matrix):
        self.tree.delete(*self.tree.get_children())

        num_cols = len(matrix[0])
        cols = [f"Col {i+1}" for i in range(num_cols)]
        self.tree["columns"] = cols

        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=120, anchor="center")

        for row in matrix:
            self.tree.insert("", "end", values=row)

        self._log("✅ Matrice reçue du coordinateur")
        self.pref_btn.config(state="enabled")

    def show_preferences(self):
        """Affiche la matrice de préférences spécifique au décideur."""
        prefs = DECIDER_PREFS.get(self.name.lower())
        if not prefs:
            messagebox.showerror("Erreur", f"Aucune préférence trouvée pour {self.name}")
            return

        pref_window = tk.Toplevel(self.root)
        pref_window.title(f"Préférences de {self.name}")
        pref_window.geometry("600x300")

        ttk.Label(pref_window, text=f"Paramètres subjectifs du {self.name}",
                  font=("Arial", 12, "bold")).pack(pady=10)

        cols = ["Critères", "Poids", "P", "Q", "V"]
        pref_tree = ttk.Treeview(pref_window, columns=cols, show="headings", height=8)
        for col in cols:
            pref_tree.heading(col, text=col)
            pref_tree.column(col, anchor="center", width=100)
        pref_tree.pack(padx=10, pady=10, fill="both", expand=True)

        for row in prefs:
            pref_tree.insert("", "end", values=row)

        ttk.Button(pref_window, text="Fermer", command=pref_window.destroy).pack(pady=10)


if __name__ == "__main__":
    import sys
    name = sys.argv[1] if len(sys.argv) > 1 else "decider_policeman"
    root = tk.Tk()
    app = DeciderApp(root, name)
    root.mainloop()
