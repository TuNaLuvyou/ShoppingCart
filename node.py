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

NODE_ID      = os.environ.get("NODE_ID", "A")
PEERS        = list(filter(None, os.environ.get("PEERS", "").split(",")))
STORAGE_DIR  = "storage"
STORAGE_FILE = f"{STORAGE_DIR}/node_{NODE_ID}_db.json"

# ─── In-Memory Cache ───────────────────────────────────────────────
_db_cache = None

def load_db():
    """Đọc database từ cache (in-memory) hoặc file nếu cache trống"""
    global _db_cache
    if _db_cache is not None:
        return _db_cache
    if os.path.exists(STORAGE_FILE):
        with open(STORAGE_FILE, "r") as f:
            _db_cache = json.load(f)
    else:
        _db_cache = {}
    return _db_cache

def save_db(db):
    """Ghi database vào cache và file (persistence)"""
    global _db_cache
    _db_cache = db
    os.makedirs(STORAGE_DIR, exist_ok=True)
    with open(STORAGE_FILE, "w") as f:
        json.dump(db, f, indent=4)

# ─── Cart API ──────────────────────────────────────────────────────

@app.route('/cart/<session_id>', methods=['GET'])
def get_cart(session_id):  # hiển thị danh sách sản phẩm
    db = load_db()
    cart = db.get(session_id, {"items": {}})
    active_items = [k for k, v in cart["items"].items() if v["status"] == "active"]
    return jsonify({"session_id": session_id, "active_items": active_items, "raw_data": cart})

@app.route('/cart/<session_id>/<action>', methods=['POST'])
def modify_cart(session_id, action): # thêm hoặc xóa sản phẩm
    if action not in ["add", "remove"]:
        return jsonify({"error": "Invalid action"}), 400

    item_name = request.json.get("item")
    db = load_db() # R = 1

    if session_id not in db:
        db[session_id] = {"items": {}}

    cart = db[session_id]
    current_item = cart["items"].get(item_name, {"status": "active", "vclock": {}})
    status = "active" if action == "add" else "deleted"
    new_vclock = increment_clock(current_item.get("vclock", {}), NODE_ID)

    cart["items"][item_name] = {"status": status, "vclock": new_vclock}
    save_db(db) # W = 1

    # Active Replication — W=1: ghi cục bộ xong là trả về ngay,
    # replication sang peer là fire-and-forget (đảm bảo Availability).
    for peer in PEERS: # chuyển dữ liệu qua các node còn lại!
        if peer:
            try:
                requests.post(f"{peer}/replicate/{session_id}", json=cart, timeout=1)
            except requests.exceptions.RequestException:
                pass  # Peer offline → sync lại sau qua Anti-Entropy

    return jsonify({"message": f"Item {action}ed at Node {NODE_ID}", "cart": cart})

# ─── Replication & Sync ────────────────────────────────────────────

@app.route('/replicate/<session_id>', methods=['POST']) #tự động merge các dữ liệu nhận từ node khác
def replicate(session_id): 
    """Active Replication: nhận cart từ peer và CRDT-merge"""
    incoming_cart = request.json
    db = load_db()
    local_cart = db.get(session_id, {"items": {}})
    db[session_id] = merge_carts(local_cart, incoming_cart)
    save_db(db)
    return jsonify({"status": "replicated"})

@app.route('/sync', methods=['POST']) # khi xảy ra mấy mạng thì sẽ bắt đầu sync (giải quyết xung đột)
def sync_all():
    """Passive Anti-Entropy: pull toàn bộ data từ peers và CRDT-merge"""
    db = load_db()
    for peer in PEERS:
        if peer:
            try:
                resp = requests.get(f"{peer}/dump", timeout=2)
                if resp.status_code == 200:
                    for session_id, incoming_cart in resp.json().items():
                        local_cart = db.get(session_id, {"items": {}})
                        db[session_id] = merge_carts(local_cart, incoming_cart)
            except requests.exceptions.RequestException:
                pass
    save_db(db)
    return jsonify({"status": "synced", "db": db})

@app.route('/dump', methods=['GET'])
def dump():
    """Trích xuất toàn bộ database cho Anti-Entropy sync"""
    return jsonify(load_db())

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "ok", "node": NODE_ID})

@app.route('/clear', methods=['POST'])
def clear_db():
    """Dọn Tombstone: xóa vật lý các item đã bị đánh dấu 'deleted'"""
    db = load_db()
    for session_id in db:
        db[session_id]["items"] = {
            k: v for k, v in db[session_id]["items"].items()
            if v["status"] == "active"
        }
    save_db(db)
    return jsonify({"status": "cleaned"})

# ──────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5001)
    args = parser.parse_args()
    app.run(host="0.0.0.0", port=args.port)