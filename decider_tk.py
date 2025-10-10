import tkinter as tk
from tkinter import ttk, messagebox
import threading
import socketio

SERVER_WS = "http://localhost:5003"

class DeciderApp:
    def __init__(self, root, name):
        self.root = root
        self.name = name
        self.root.title(f"DÉCIDEUR - {name}")
        self.root.geometry("600x450")

        top = ttk.Frame(root)
        top.pack(fill="x", padx=8, pady=8)
        ttk.Label(top, text=f"Décideur: {name}", font=("Arial", 14, "bold")).pack(side="left")

        # État de connexion / réception
        self.status = ttk.Label(root, text="⏳ En attente du coordinateur...", foreground="gray")
        self.status.pack(fill="x", padx=8, pady=4)

        # Tableau vide au départ
        self.tree = ttk.Treeview(root, show="headings")
        self.tree.pack(fill="both", expand=True, padx=8, pady=6)

        # Bouton désactivé jusqu’à réception de matrice
        btn_frame = ttk.Frame(root)
        btn_frame.pack(fill="x", padx=8, pady=6)
        self.pref_btn = ttk.Button(btn_frame, text="Envoyer Préférences", command=self.send_preferences, state="disabled")
        self.pref_btn.pack(side="left")

        # SocketIO client
        self.sio = socketio.Client(logger=False, reconnection=True)
        self.sio.on("matrix_update", self._on_matrix_update)
        self.sio.on("connect", lambda: self._log("🟢 Connecté au serveur – attente de matrice..."))
        self.sio.on("disconnect", lambda: self._log("🔴 Déconnecté du serveur"))

        # Thread SocketIO
        t = threading.Thread(target=self._start_socketio, daemon=True)
        t.start()

    def _start_socketio(self):
        """Connexion au serveur en arrière-plan."""
        try:
            self.sio.connect(SERVER_WS)
            self.sio.wait()
        except Exception as e:
            self.root.after(0, lambda: self._log(f"Erreur connexion SocketIO: {e}"))

    def _log(self, msg):
        """Met à jour le texte de statut."""
        self.status.config(text=msg)

    def _on_matrix_update(self, payload):
        """Reçoit la matrice depuis le coordinateur."""
        matrix = payload.get("matrix") if isinstance(payload, dict) else payload
        if not matrix:
            return
        self.root.after(0, lambda: self._show_matrix(matrix))

    def _show_matrix(self, matrix):
        """Affiche la matrice dans un tableau Treeview."""
        # Efface le contenu précédent
        self.tree.delete(*self.tree.get_children())
        for col in self.tree["columns"]:
            self.tree.heading(col, text="")

        # Crée les colonnes selon la taille
        num_cols = len(matrix[0])
        cols = [f"Col {i+1}" for i in range(num_cols)]
        self.tree["columns"] = cols

        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=120, anchor="center")

        # Remplit les lignes
        for row in matrix:
            self.tree.insert("", "end", values=row)

        self._log("✅ Matrice reçue du coordinateur")
        self.pref_btn.config(state="enabled")

    def send_preferences(self):
        """Envoie les préférences du décideur au serveur."""
        prefs = {"from": self.name, "prefs": "example"}
        try:
            self.sio.emit("preferences", {"decider": self.name, "prefs": prefs})
            messagebox.showinfo("Envoyé", "Préférences envoyées au coordinateur.")
            self.pref_btn.config(state="disabled")
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible d'envoyer: {e}")


if __name__ == "__main__":
    import sys
    name = sys.argv[1] if len(sys.argv) > 1 else "decider1"
    root = tk.Tk()
    app = DeciderApp(root, name)
    root.mainloop()
