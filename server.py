from flask import Flask, jsonify, request
from flask_socketio import SocketIO, emit
import random

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# ---- Données du coordinateur ----
matrix = []
deciders = ["decider1", "decider2", "decider3", "decider4"]
# Générer des valeurs aléatoires
raw_weights = [random.uniform(0.1, 1.0) for _ in deciders]

# Normaliser pour que la somme soit 100
total = sum(raw_weights)
weights = {decider: round((w/total)*100, 2) for decider, w in zip(deciders, raw_weights)}

preferences = {}

# ---- Routes HTTP ----
@app.route('/')
def home():
    return jsonify({
        "message": "Serveur coordinateur DCTW en ligne ✅",
        "deciders": deciders,
        "weights": weights
    })

@app.route('/upload_matrix', methods=['POST'])
def upload_matrix():
    """Upload ou créer une matrice de performance depuis le coordinateur"""
    global matrix
    data = request.get_json()
    matrix = data.get("matrix", [])
    print("✅ Matrice reçue :", matrix)
    # Envoyer la matrice à tous les décideurs connectés
    socketio.emit("matrix_data", matrix)
    return jsonify({"status": "ok", "matrix": matrix})

# ---- Communication temps réel ----
@socketio.on('connect')
def handle_connect():
    print("🔗 Un client s'est connecté")

@socketio.on('disconnect')
def handle_disconnect():
    print("❌ Un client s'est déconnecté")

# @socketio.on('preferences')
# def handle_preferences(data):
#     """Réception des préférences d’un décideur"""
#     decider = data.get("decider")
#     prefs = data.get("prefs")
#     preferences[decider] = prefs
#     print(f"📩 Préférences reçues de {decider}: {prefs}")

#     # Si tous les décideurs ont envoyé leurs prefs
#     if len(preferences) == len(deciders):
#         print("✅ Toutes les préférences reçues, agrégation possible !")
#         socketio.emit("all_preferences_received", preferences)

if __name__ == '__main__':
    print("🚀 Démarrage du serveur coordinateur DCTW...")
    socketio.run(app, host='0.0.0.0', port=5000)
