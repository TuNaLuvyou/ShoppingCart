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
NODE_ID = os.environ.get("NODE_ID", "A")
PEERS = os.environ.get("PEERS", "").split(",")
STORAGE_DIR = "storage"
STORAGE_FILE = f"{STORAGE_DIR}/node_{NODE_ID}_db.json"

def load_db():
    if os.path.exists(STORAGE_FILE):
        with open(STORAGE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_db(db):
    os.makedirs(STORAGE_DIR, exist_ok=True)
    with open(STORAGE_FILE, "w") as f:
        json.dump(db, f, indent=4)

@app.route('/cart/<session_id>', methods=['GET'])
def get_cart(session_id):
    db = load_db()
    cart = db.get(session_id, {"items": {}})
    # Ẩn các item đã bị xóa (Tombstone) khỏi người dùng
    active_items = [k for k, v in cart["items"].items() if v["status"] == "active"]
    return jsonify({"session_id": session_id, "active_items": active_items, "raw_data": cart})

@app.route('/cart/<session_id>/<action>', methods=['POST'])
def modify_cart(session_id, action):
    if action not in ["add", "remove"]: 
        return jsonify({"error": "Invalid action"}), 400
        
    item_name = request.json.get("item")
    db = load_db()
    
    if session_id not in db:
        db[session_id] = {"items": {}}
        
    cart = db[session_id]
    current_item = cart["items"].get(item_name, {"status": "active", "vclock": {}})
    
    # Cập nhật trạng thái và Vector Clock
    status = "active" if action == "add" else "deleted"
    new_vclock = increment_clock(current_item.get("vclock", {}), NODE_ID)
    
    cart["items"][item_name] = {"status": status, "vclock": new_vclock}
    save_db(db)
    
    # Lazy Replication (Bắn dữ liệu sang các node khác, không quan tâm nếu họ đang sập)
    for peer in PEERS:
        if peer:
            try:
                requests.post(f"{peer}/replicate/{session_id}", json=cart, timeout=1)
            except requests.exceptions.RequestException:
                pass
                
    return jsonify({"message": f"Item {action}ed at Node {NODE_ID}", "cart": cart})

@app.route('/replicate/<session_id>', methods=['POST'])
def replicate(session_id):
    incoming_cart = request.json
    db = load_db()
    local_cart = db.get(session_id, {"items": {}})
    
    merged_cart = merge_carts(local_cart, incoming_cart)
    db[session_id] = merged_cart
    save_db(db)
    
    return jsonify({"status": "replicated"})

@app.route('/sync', methods=['POST'])
def sync_all():
    db = load_db()
    for peer in PEERS:
        if peer:
            try:
                resp = requests.get(f"{peer}/dump", timeout=2)
                if resp.status_code == 200:
                    peer_db = resp.json()
                    for session_id, incoming_cart in peer_db.items():
                        local_cart = db.get(session_id, {"items": {}})
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
    for session_id in db:
        cart = db[session_id]
        # Chỉ giữ lại các món có status là 'active'
        cart["items"] = {k: v for k, v in cart["items"].items() if v["status"] == "active"}
    save_db(db)
    return jsonify({"status": "cleaned"})

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5001)
    args = parser.parse_args()
    app.run(host="0.0.0.0", port=args.port)