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

# Hằng số cấu hình
NODE_ID      = os.environ.get("NODE_ID", "A")
PEERS        = list(filter(None, os.environ.get("PEERS", "").split(",")))
STORAGE_DIR  = "storage"
STORAGE_FILE = f"{STORAGE_DIR}/node_{NODE_ID}_db.json"
REQUEST_TIMEOUT = 1
SYNC_TIMEOUT    = 2

# ─── In-Memory Cache ───────────────────────────────────────────────
# Bộ nhớ tạm để tránh đọc file JSON mỗi request
_db_cache = None

def load_db():
    """Đọc database từ cache (in-memory) hoặc file nếu cache trống. R=1"""
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
    """Ghi database vào cache và file (persistence). W=1"""
    global _db_cache
    _db_cache = db
    os.makedirs(STORAGE_DIR, exist_ok=True)
    with open(STORAGE_FILE, "w") as f:
        json.dump(db, f, indent=4)

# ─── Helper Functions ──────────────────────────────────────────────

def _get_cart(db, session_id):
    """Lấy hoặc tạo mới giỏ hàng cho phiên (session)."""
    if session_id not in db:
        db[session_id] = {"version": 0, "items": {}}
    return db[session_id]

def _replicate_to_peers(session_id, cart): # Gửi dữ liệu qua các node còn lại
    """Active Replication: gửi cart tới tất cả node khác (fire-and-forget, W=1)."""
    for peer in PEERS: # chuyển dữ liệu qua các node còn lại!
        try:
            requests.post(f"{peer}/replicate/{session_id}", json=cart, timeout=REQUEST_TIMEOUT)
        except requests.exceptions.RequestException:
            pass  # Peer offline → sync lại sau qua Anti-Entropy

# ─── Cart API ──────────────────────────────────────────────────────

@app.route('/cart/<session_id>', methods=['GET'])
def get_cart(session_id):  # hiển thị danh sách sản phẩm
    db   = load_db()
    cart = _get_cart(db, session_id)
    # Ẩn các item đã bị xóa (Tombstone) khỏi người dùng
    active_items = [k for k, v in cart["items"].items() if v["status"] == "active"]
    return jsonify({
        "session_id":   session_id,
        "version":      cart.get("version", 0),
        "active_items": active_items,
        "raw_data":     cart
    })

@app.route('/cart/<session_id>/<action>', methods=['POST'])
def modify_cart(session_id, action): # thêm hoặc xóa sản phẩm
    if action not in ["add", "remove", "increase", "decrease"]:
        return jsonify({"error": "Invalid action"}), 400

    item_name = request.json.get("item") if request.json else None
    if not item_name:
        return jsonify({"error": "Item name required"}), 400

    # Chuẩn hóa tên sản phẩm
    item_name = item_name.strip().title()

    db   = load_db()  # R = 1
    cart = _get_cart(db, session_id)
    current_item = cart["items"].get(item_name, {"status": "active", "vclock": {}, "quantity": {}})

    qty_dict = current_item.get("quantity", {})
    if not isinstance(qty_dict, dict):
        qty_dict = {NODE_ID: current_item.get("quantity", 0)}
    else:
        qty_dict = dict(qty_dict)  # copy để tránh lỗi tham chiếu

    current_node_qty = qty_dict.get(NODE_ID, 0)

    if action == "add":
        status = "active"
        # Nếu item đã bị xóa trước đó, reset số lượng về 1
        qty_dict = {NODE_ID: 1} if current_item.get("status") == "deleted" else {NODE_ID: current_node_qty + 1}
    elif action == "increase":
        status = "active"
        qty_dict[NODE_ID] = current_node_qty + 1
    elif action == "decrease":
        status = "active"
        qty_dict[NODE_ID] = max(0, current_node_qty - 1)
    else:  # remove: đánh dấu Tombstone (deleted), xóa logic
        status   = "deleted"
        qty_dict = {}

    new_vclock = increment_clock(current_item.get("vclock", {}), NODE_ID)

    cart["items"][item_name] = {"status": status, "vclock": new_vclock, "quantity": qty_dict}
    cart["version"] = cart.get("version", 0) + 1
    save_db(db)  # W = 1

    # Active Replication — W=1: ghi cục bộ xong là trả về ngay,
    # replication sang peer là fire-and-forget (đảm bảo Availability).
    _replicate_to_peers(session_id, cart)

    return jsonify({"message": f"Item {action}ed at Node {NODE_ID}", "version": cart.get("version", 0), "cart": cart})

# ─── Replication & Sync ────────────────────────────────────────────

@app.route('/replicate/<session_id>', methods=['POST'])  # tự động merge dữ liệu nhận từ node khác
def replicate(session_id):
    """Active Replication: nhận cart từ peer và CRDT-merge"""
    incoming_cart = request.json
    db            = load_db()
    local_cart    = _get_cart(db, session_id)
    db[session_id] = merge_carts(local_cart, incoming_cart)
    save_db(db)
    return jsonify({"status": "replicated"})

@app.route('/sync', methods=['POST'])  # khi mất mạng kết nối lại thì sẽ bắt đầu sync (giải quyết xung đột)
def sync_all():
    """Passive Anti-Entropy: pull toàn bộ data từ peers và CRDT-merge"""
    db = load_db()
    for peer in PEERS:
        if peer:
            try:
                resp = requests.get(f"{peer}/dump", timeout=SYNC_TIMEOUT)
                if resp.status_code == 200:
                    peer_db = resp.json()
                    for session_id, incoming_cart in peer_db.items():
                        local_cart     = _get_cart(db, session_id)
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
    for session_id, cart in db.items():
        # Chỉ giữ lại các sản phẩm đang active, xóa các Tombstone
        cart["items"] = {
            k: v for k, v in cart["items"].items()
            if v["status"] == "active"
        }
        cart["version"] = cart.get("version", 0) + 1
    save_db(db)
    return jsonify({"status": "cleaned"})

# ──────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5001)
    args = parser.parse_args()
    app.run(host="0.0.0.0", port=args.port)