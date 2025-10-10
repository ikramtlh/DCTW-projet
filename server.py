from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

matrix_data = None  # pour stocker la dernière matrice envoyée


@app.route("/")
def home():
    return jsonify({"message": "✅ Serveur DCTW SocketIO en ligne"})


@app.route("/upload_matrix", methods=["POST"])
def upload_matrix():
    """Reçoit une matrice du coordinateur et la diffuse à tous les décideurs connectés"""
    global matrix_data
    data = request.get_json()
    matrix_data = data.get("matrix")

    if not matrix_data:
        return jsonify({"status": "error", "message": "Aucune matrice reçue"}), 400

    print("📩 Nouvelle matrice reçue du coordinateur :", matrix_data)
    socketio.emit("matrix_update", {"matrix": matrix_data})
    return jsonify({"status": "ok", "message": "Matrice diffusée"})


@socketio.on("connect")
def handle_connect():
    print("🔌 Un client s'est connecté")
    if matrix_data:
        emit("matrix_update", {"matrix": matrix_data})  # Envoie la matrice actuelle au nouveau client


@socketio.on("disconnect")
def handle_disconnect():
    print("❌ Un client s'est déconnecté")


if __name__ == "__main__":
    print("🚀 Serveur DCTW en ligne sur le port 5003...")
    socketio.run(app, host="0.0.0.0", port=5003)
