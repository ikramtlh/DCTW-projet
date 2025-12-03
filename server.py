from flask import Flask, request, jsonify
from flask_cors import CORS
import socketio

app = Flask(__name__)
CORS(app)
sio = socketio.Server(cors_allowed_origins="*")
app.wsgi_app = socketio.WSGIApp(sio, app.wsgi_app)

connected_deciders = {}  # store decider info
latest_matrix = None     # last uploaded matrix


@app.route("/")
def home():
    """Show connected deciders and matrix status"""
    deciders_list = [
        {"name": d["name"], "prefs": d.get("prefs"), "weight": d.get("weight")}
        for d in connected_deciders.values()
    ]
    return jsonify({"connected_deciders": deciders_list, "matrix_ready": latest_matrix is not None})


@app.route("/upload_matrix", methods=["POST"])
def upload_matrix():
    """Coordinator uploads matrix and broadcasts to deciders"""
    global latest_matrix
    data = request.get_json()
    latest_matrix = data.get("matrix")

    if not latest_matrix:
        return jsonify({"status": "error", "message": "No matrix provided"}), 400

    sio.emit("matrix_update", {"matrix": latest_matrix})
    print("✅ Matrix sent to all deciders")
    return jsonify({"status": "ok", "message": "Matrix broadcasted"})


@app.route("/deciders", methods=["GET"])
def get_deciders():
    """Return list of deciders (fixed example)"""
    return jsonify({
        "connected_deciders": [
            {"name": "decider_policeman", "weight": 40.0},
            {"name": "decider_economist", "weight": 25.0},
            {"name": "decider_environmental representative", "weight": 20.0},
            {"name": "decider_public representative", "weight": 15.0},
        ]
    })


@sio.event
def connect(sid, environ):
    print(f"🔌 Decider connected: {sid}")
    connected_deciders[sid] = {"name": f"decider_{sid[:4]}", "prefs": None}


@sio.event
def disconnect(sid):
    print(f"❌ Decider disconnected: {sid}")
    connected_deciders.pop(sid, None)


@sio.event
def final_ranking(sid, data):
    decider_name = data.get("decider")
    ranking = data.get("ranking")
    phi = data.get("phi")
    print(f"📊 Received ranking from {decider_name}: {ranking}")

    # sauvegarde côté serveur
    connected_deciders[sid]["ranking"] = ranking
    connected_deciders[sid]["phi"] = phi

    # émet au client coordonnateur
    sio.emit("final_ranking", {
        "decider": decider_name,
        "ranking": ranking,
        "phi": phi
    })

if __name__ == "__main__":
    import eventlet
    import eventlet.wsgi

    print("🚀 Coordinator server running on port 5003...")
    # eventlet WSGI server pour supporter Socket.IO
    eventlet.wsgi.server(eventlet.listen(("0.0.0.0", 5003)), app)