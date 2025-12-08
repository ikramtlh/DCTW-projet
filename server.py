from flask import Flask, request, jsonify
from flask_cors import CORS
import socketio

app = Flask(__name__)
CORS(app)
sio = socketio.Server(cors_allowed_origins="*", async_mode='threading')
app.wsgi_app = socketio.WSGIApp(sio, app.wsgi_app)

connected_deciders = {}  # store decider info by sid
latest_matrix = None     # last uploaded matrix
negotiation_in_progress = False
current_action_proposal = None
negotiation_responses = {}  # {decider_name: "accept"/"decline"}


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
    print(f"🔌 Client connected: {sid}")
    # Try to get name from query parameters
    query_string = environ.get('QUERY_STRING', '')
    if 'name=' in query_string:
        name = query_string.split('name=')[1].split('&')[0]
        connected_deciders[sid] = {"name": name, "sid": sid}
    else:
        connected_deciders[sid] = {"name": f"decider_{sid[:4]}", "sid": sid}
    
    print(f"   Registered as: {connected_deciders[sid]['name']}")


@sio.event
def disconnect(sid):
    print(f"❌ Client disconnected: {sid}")
    if sid in connected_deciders:
        print(f"   Removing: {connected_deciders[sid]['name']}")
        connected_deciders.pop(sid, None)


@sio.event
def final_ranking(sid, data):
    decider_name = data.get("decider")
    ranking = data.get("ranking")
    phi = data.get("phi")
    print(f"📊 Received ranking from {decider_name}: {ranking}")

    # Save locally
    if sid in connected_deciders:
        connected_deciders[sid]["ranking"] = ranking
        connected_deciders[sid]["phi"] = phi

    # Broadcast to coordinator
    sio.emit("final_ranking", {
        "decider": decider_name,
        "ranking": ranking,
        "phi": phi
    })


@sio.event
def negotiation_proposal(sid, data):
    """Coordinator proposes an action to all deciders"""
    global negotiation_in_progress, current_action_proposal, negotiation_responses
    
    action = data.get("action")
    if not action:
        return
    
    print(f"📨 Negotiation proposal from coordinator: {action}")
    
    # Reset negotiation state
    negotiation_in_progress = True
    current_action_proposal = action
    negotiation_responses = {}
    
    # Broadcast to all deciders
    sio.emit("negotiation_proposal", {"action": action})
    
    return {"status": "ok", "message": f"Proposal sent for action: {action}"}


@sio.event
def negotiation_response(sid, data):
    """Receive response from a decider"""
    global negotiation_responses
    
    decider = data.get("decider")
    answer = data.get("answer")
    action = data.get("action")
    
    print(f"📩 Response from {decider}: {answer} for action {action}")
    
    # Store response
    negotiation_responses[decider] = answer
    
    # Broadcast to coordinator
    sio.emit("negotiation_response", {
        "decider": decider,
        "action": action,
        "answer": answer
    })
    
    # Check if all deciders have responded
    if len(negotiation_responses) >= 4:  # Assuming 4 deciders
        accept_count = sum(1 for ans in negotiation_responses.values() if ans == "accept")
        accept_ratio = accept_count / len(negotiation_responses)
        
        print(f"📊 All responses received. Accept ratio: {accept_ratio:.2%}")
        
        if accept_ratio >= 0.9:  # 90% threshold
            print(f"🎉 Action {action} SELECTED!")
            sio.emit("negotiation_selected", {"action": action})
        else:
            print(f"❌ Action {action} REJECTED.")
            sio.emit("negotiation_rejected", {"action": action})
    
    return {"status": "ok"}


@sio.event
def negotiation_selected(sid, data):
    """Forward selection notification"""
    action = data.get("action")
    print(f"✅ Final selection: {action}")
    sio.emit("negotiation_selected", {"action": action})


if __name__ == "__main__":
    print("🚀 Coordinator server running on port 5003...")
    print("   - Endpoints:")
    print("     GET  /           - Server status")
    print("     POST /upload_matrix - Upload decision matrix")
    print("     GET  /deciders   - Get deciders list")
    print("   - Socket.IO events:")
    print("     final_ranking    - Send ranking to coordinator")
    print("     negotiation_proposal - Propose action")
    print("     negotiation_response - Respond to proposal")
    print("     negotiation_selected - Action selected")
    
    from werkzeug.serving import run_simple
    run_simple("0.0.0.0", 5003, app.wsgi_app, threaded=True)