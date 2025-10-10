from flask import Flask, request, jsonify
from flask_cors import CORS
import socketio

# Flask + SocketIO setup
app = Flask(__name__)
CORS(app)
sio = socketio.Server(cors_allowed_origins="*")
app.wsgi_app = socketio.WSGIApp(sio, app.wsgi_app)

# Stockage
connected_deciders = {}  # { sid: {"name": "decider1", "prefs": None, "weight": None} }
latest_matrix = None

@app.route("/")
def home():
    """Afficher la liste des décideurs connectés"""
    deciders_list = [
        {"name": d["name"], "prefs": d.get("prefs"), "weight": d.get("weight")}
        for d in connected_deciders.values()
    ]
    return jsonify({"connected_deciders": deciders_list, "matrix_ready": latest_matrix is not None})

@app.route("/upload_matrix", methods=["POST"])
def upload_matrix():
    global latest_matrix
    data = request.get_json()
    latest_matrix = data.get("matrix")

    if not latest_matrix:
        return jsonify({"status": "error", "message": "No matrix provided"}), 400

    # Broadcast to all connected deciders
    sio.emit("matrix_update", {"matrix": latest_matrix})
    print("✅ Matrice envoyée à tous les décideurs")
    return jsonify({"status": "ok", "message": "Matrix broadcasted"})

# ---------------- SocketIO ---------------- #

@sio.event
def connect(sid, environ):
    print(f"🔌 Décideur connecté: {sid}")
    connected_deciders[sid] = {"name": f"decider_{sid[:4]}", "prefs": None}

@sio.event
def disconnect(sid):
    print(f"❌ Décideur déconnecté: {sid}")
    connected_deciders.pop(sid, None)

@sio.event
def preferences(sid, data):
    """Réception des préférences envoyées par un décideur"""
    decider_name = data.get("decider")
    prefs = data.get("prefs")
    if sid in connected_deciders:
        connected_deciders[sid]["prefs"] = prefs
        connected_deciders[sid]["name"] = decider_name
        print(f"📨 Préférences reçues de {decider_name}: {prefs}")
    sio.emit("preferences_update", connected_deciders)

if __name__ == "__main__":
    print("🚀 Démarrage du serveur coordinateur DCTW sur le port 5003...")
    app.run(host="0.0.0.0", port=5003)
