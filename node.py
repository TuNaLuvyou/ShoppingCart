import os
import json
import argparse
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from core.vector_clock import increment_clock
from core.merge import merge_carts

app = Flask(__name__)
CORS(app)

# Configuration Constants
NODE_ID = os.environ.get("NODE_ID", "A")
PEERS = [p for p in os.environ.get("PEERS", "").split(",") if p]
STORAGE_DIR = "storage"
STORAGE_FILE = os.path.join(STORAGE_DIR, f"node_{NODE_ID}_db.json")
REQUEST_TIMEOUT = 1
SYNC_TIMEOUT = 2

# Database cache
_db_cache = None

def load_db():
    """Load database from file with error handling."""
    global _db_cache
    if _db_cache is not None:
        return _db_cache
    
    if os.path.exists(STORAGE_FILE):
        try:
            with open(STORAGE_FILE, "r") as f:
                content = f.read().strip()
                if content:
                    _db_cache = json.loads(content)
                    return _db_cache
        except (json.JSONDecodeError, IOError) as e:
            app.logger.warning(f"Error loading database: {e}")
    return {}

def save_db(db):
    """Save database to file and update cache."""
    global _db_cache
    os.makedirs(STORAGE_DIR, exist_ok=True)
    with open(STORAGE_FILE, "w") as f:
        json.dump(db, f, indent=2)
    _db_cache = db

def _get_cart(db, session_id):
    """Get or create cart for session."""
    if session_id not in db:
        db[session_id] = {"version": 0, "items": {}}
    return db[session_id]

def _get_active_items(items):
    """Get list of active item names."""
    return [k for k, v in items.items() if v["status"] == "active"]

def _replicate_to_peers(session_id, cart):
    """Send cart data to all peer nodes."""
    for peer in PEERS:
        try:
            requests.post(f"{peer}/replicate/{session_id}", json=cart, timeout=REQUEST_TIMEOUT)
        except requests.exceptions.RequestException:
            pass

@app.route('/cart/<session_id>', methods=['GET'])
def get_cart(session_id):
    db = load_db()
    cart = _get_cart(db, session_id)
    active_items = _get_active_items(cart["items"])
    return jsonify({
        "session_id": session_id,
        "version": cart.get("version", 0),
        "active_items": active_items,
        "raw_data": cart
    })

@app.route('/cart/<session_id>/<action>', methods=['POST'])
def modify_cart(session_id, action):
    if action not in ["add", "remove"]:
        return jsonify({"error": "Invalid action"}), 400
    
    item_name = request.json.get("item") if request.json else None
    if not item_name:
        return jsonify({"error": "Item name required"}), 400
    
    db = load_db()
    cart = _get_cart(db, session_id)
    current_item = cart["items"].get(item_name, {"status": "active", "vclock": {}})
    
    # Update item status and vector clock
    status = "active" if action == "add" else "deleted"
    new_vclock = increment_clock(current_item.get("vclock", {}), NODE_ID)
    
    cart["items"][item_name] = {"status": status, "vclock": new_vclock}
    cart["version"] = cart.get("version", 0) + 1
    save_db(db)
    
    # Replicate to peers
    _replicate_to_peers(session_id, cart)
    
    return jsonify({
        "message": f"Item {action}ed at Node {NODE_ID}",
        "version": cart.get("version", 0),
        "cart": cart
    })

@app.route('/replicate/<session_id>', methods=['POST'])
def replicate(session_id):
    incoming_cart = request.json
    db = load_db()
    local_cart = _get_cart(db, session_id)
    
    merged_cart = merge_carts(local_cart, incoming_cart)
    db[session_id] = merged_cart
    save_db(db)
    
    return jsonify({
        "status": "replicated",
        "version": merged_cart.get("version", 0)
    })

@app.route('/sync', methods=['POST'])
def sync_all():
    db = load_db()
    for peer in PEERS:
        try:
            resp = requests.get(f"{peer}/dump", timeout=SYNC_TIMEOUT)
            if resp.status_code == 200:
                peer_db = resp.json()
                for session_id, incoming_cart in peer_db.items():
                    local_cart = _get_cart(db, session_id)
                    db[session_id] = merge_carts(local_cart, incoming_cart)
        except requests.exceptions.RequestException:
            pass
    save_db(db)
    return jsonify({"status": "synced", "db": db})

@app.route('/dump', methods=['GET'])
def dump():
    return jsonify(load_db())

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "ok", "node": NODE_ID})

@app.route('/clear', methods=['POST'])
def clear_db():
    db = load_db()
    for session_id, cart in db.items():
        # Keep only active items, remove tombstones
        cart["items"] = {
            k: v for k, v in cart["items"].items()
            if v["status"] == "active"
        }
        cart["version"] = cart.get("version", 0) + 1
    save_db(db)
    return jsonify({"status": "cleaned"})

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5001)
    args = parser.parse_args()
    app.run(host="0.0.0.0", port=args.port)