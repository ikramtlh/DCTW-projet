import sys
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QLineEdit, QMessageBox
from coordinator_ui import CoordinatorWindow
from decider_ui import DeciderWindow

class LoginWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Connexio")
        self.setGeometry(600, 300, 600, 300)

        layout = QVBoxLayout()

        self.label = QLabel("Entrez votre rôle ou nom :")
        layout.addWidget(self.label)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("coordinateur ou decider1/decider2/...")
        layout.addWidget(self.input_field)

        self.login_btn = QPushButton("Se connecter")
        self.login_btn.clicked.connect(self.login)
        layout.addWidget(self.login_btn)

        self.setLayout(layout)

    def login(self):
        role = self.input_field.text().strip().lower()
        if role == "coordinateur":
            self.open_coordinator()
        elif role in ["decider1", "decider2", "decider3", "decider4"]:
            self.open_decider(role)
        else:
            QMessageBox.warning(self, "Erreur", "Rôle invalide !")

    def open_coordinator(self):
        self.coord_window = CoordinatorWindow()
        self.coord_window.show()
        self.close()  # fermer la fenêtre de login

    def open_decider(self, name):
        self.decider_window = DeciderWindow(name)
        self.decider_window.show()
        self.close()  # fermer la fenêtre de login

if __name__ == "__main__":
    app = QApplication(sys.argv)
    login_window = LoginWindow()
    login_window.show()
    sys.exit(app.exec())
