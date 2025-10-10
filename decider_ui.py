import sys
import json
import socketio
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QTextEdit, QPushButton

SERVER_URL = "http://localhost:5002"

# Client SocketIO
sio = socketio.Client()

class DeciderWindow(QWidget):
    def __init__(self, name):
        super().__init__()
        self.decider_name = name
        self.setWindowTitle(f"Décideur {name}")
        self.setGeometry(600, 300, 600, 300)

        layout = QVBoxLayout()

        self.matrix_label = QLabel("Matrice reçue :")
        layout.addWidget(self.matrix_label)

        self.matrix_text = QTextEdit()
        self.matrix_text.setReadOnly(True)
        layout.addWidget(self.matrix_text)

        self.send_btn = QPushButton("Envoyer Préférences")
        self.send_btn.clicked.connect(self.send_preferences)
        self.send_btn.setEnabled(False)
        layout.addWidget(self.send_btn)

        self.setLayout(layout)

    def receive_matrix(self, matrix):
        self.matrix_text.setText(json.dumps(matrix, indent=2))
        self.send_btn.setEnabled(True)

    def send_preferences(self):
        prefs = {"example": "valeur"}  # ici tu peux ajouter une vraie logique
        sio.emit("preferences", {"decider": self.decider_name, "prefs": prefs})
        print(f"Préférences envoyées: {prefs}")
        self.send_btn.setEnabled(False)

# ---- SocketIO events ----
@sio.event
def connect():
    print("Connecté au serveur")

@sio.event
def disconnect():
    print("Déconnecté du serveur")

@sio.on("matrix_data")
def on_matrix(data):
    print("Matrice reçue:", data)
    window.receive_matrix(data)

@sio.on("all_preferences_received")
def on_all_prefs(data):
    print("Toutes les préférences reçues:", data)

if __name__ == "__main__":
    name = input("Nom du décideur (decider1/decider2/...): ")
    app = QApplication(sys.argv)
    window = DeciderWindow(name)
    window.show()
    sio.connect(SERVER_URL)
    sys.exit(app.exec())
