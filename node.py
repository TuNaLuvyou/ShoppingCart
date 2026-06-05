import os
import json
import time
import argparse
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from core.vector_clock import increment_clock
from core.merge import merge_carts

app = Flask(__name__)
CORS(app)
# Hằng số cấu hình
NODE_ID = os.environ.get("NODE_ID", "A")
PEERS = list(filter(None, os.environ.get("PEERS", "").split(",")))
STORAGE_DIR = "storage"
STORAGE_FILE = f"{STORAGE_DIR}/node_{NODE_ID}_db.json"
REQUEST_TIMEOUT = 1
SYNC_TIMEOUT = 2

# ─── In-Memory Cache ───────────────────────────────────────────────
# Bộ nhớ tạm (cache) cơ sở dữ liệu để tránh đọc file JSON mỗi request
_db_cache = None

def load_db():
    """Tải cơ sở dữ liệu từ cache (in-memory) hoặc từ file nếu cache trống"""
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
    """Lưu cơ sở dữ liệu vào cả cache (in-memory) lẫn file (persistence)"""
    global _db_cache
    _db_cache = db
    os.makedirs(STORAGE_DIR, exist_ok=True)
    with open(STORAGE_FILE, "w") as f:
        json.dump(db, f, indent=4)

# ─── Cart API ──────────────────────────────────────────────────────

def _get_cart(db, session_id):
    """Lấy hoặc tạo mới giỏ hàng cho phiên bản (session)."""
    if session_id not in db:
        db[session_id] = {"version": 0, "items": {}}
    return db[session_id]

def _replicate_to_peers(session_id, cart):
    """Gửi dữ liệu giỏ hàng tới tất cả các node khác."""
    for peer in PEERS:
        try:
            requests.post(f"{peer}/replicate/{session_id}", json=cart, timeout=REQUEST_TIMEOUT)
        except requests.exceptions.RequestException:
            pass

@app.route('/cart/<session_id>', methods=['GET'])
def get_cart(session_id):
    db = load_db()
    cart = _get_cart(db, session_id)
    # Ẩn các item đã bị xóa (Tombstone) khỏi người dùng
    active_items = [k for k, v in cart["items"].items() if v["status"] == "active"]
    return jsonify({
        "session_id": session_id,
        "version": cart.get("version", 0),
        "active_items": active_items,
        "raw_data": cart
    })

@app.route('/cart/<session_id>/<action>', methods=['POST'])
def modify_cart(session_id, action):
    if action not in ["add", "remove", "increase", "decrease"]:
        return jsonify({"error": "Invalid action"}), 400
    
    item_name = request.json.get("item") if request.json else None
    if not item_name:
        return jsonify({"error": "Item name required"}), 400
        
    # Chuẩn hóa tên sản phẩm: bỏ khoảng trắng thừa và viết hoa chữ cái đầu
    item_name = item_name.strip().title()
    
    db = load_db()
    cart = _get_cart(db, session_id)
    current_item = cart["items"].get(item_name, {"status": "active", "vclock": {}, "quantity": {}})
    
    qty_dict = current_item.get("quantity", {})
    if not isinstance(qty_dict, dict):
        qty_dict = {NODE_ID: current_item.get("quantity", 0)}
    else:
        qty_dict = dict(qty_dict) # copy để tránh lỗi tham chiếu
        
    current_node_qty = qty_dict.get(NODE_ID, 0)
    
    if action == "add":
        status = "active"
        if current_item.get("status") == "deleted":
            qty_dict = {NODE_ID: 1}
        else:
            qty_dict[NODE_ID] = current_node_qty + 1
    elif action == "increase":
        status = "active"
        qty_dict[NODE_ID] = current_node_qty + 1
    elif action == "decrease":
        status = "active"
        qty_dict[NODE_ID] = current_node_qty - 1
    else: # xóa
        status = "deleted"
        qty_dict = {}

    new_vclock = increment_clock(current_item.get("vclock", {}), NODE_ID)
    
    cart["items"][item_name] = {"status": status, "vclock": new_vclock, "quantity": qty_dict}
    cart["version"] = cart.get("version", 0) + 1
    save_db(db)
    
    # Đồng bộ tới các node khác
    _replicate_to_peers(session_id, cart)
    
    return jsonify({
        "message": f"Item {action}ed at Node {NODE_ID}",
        "version": cart.get("version", 0),
        "cart": cart
    })

# ─── Replication & Sync ────────────────────────────────────────────

@app.route('/replicate/<session_id>', methods=['POST'])
def replicate(session_id):
    """Active Replication: Nhận dữ liệu từ peer và merge"""
    incoming_cart = request.json
    db = load_db()
    local_cart = _get_cart(db, session_id)
    
    merged_cart = merge_carts(local_cart, incoming_cart)
    db[session_id] = merged_cart
    save_db(db)
    
    return jsonify({"status": "replicated"})

@app.route('/sync', methods=['POST'])
def sync_all():
    """Passive Anti-Entropy: Pull toàn bộ dữ liệu từ peers và merge"""
    db = load_db()
    for peer in PEERS:
        if peer:
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
    """Trích xuất toàn bộ database cho Anti-Entropy sync"""
    return jsonify(load_db())

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "ok", "node": NODE_ID})

@app.route('/clear', methods=['POST'])
def clear_db():
    """Dọn dẹp Tombstone: Xóa vật lý các item đã bị đánh dấu 'deleted'"""
    db = load_db()
    for session_id, cart in db.items():
        # Chỉ giữ lại các sản phẩm đang có, xóa các thẻ đánh dấu xóa (tombstones)
        cart["items"] = {
            k: v for k, v in cart["items"].items()
            if v["status"] == "active"
        }
        cart["version"] = cart.get("version", 0) + 1
    save_db(db)
    return jsonify({"status": "cleaned"})

# ─── Scalability: Dynamic Peer Registration ────────────────────────

@app.route('/register', methods=['POST'])
def register_peer():
    """Cho phép node mới tự đăng ký vào cluster (Horizontal Scaling)"""
    peer_url = request.json.get("url")
    if peer_url and peer_url not in PEERS:
        PEERS.append(peer_url)
        return jsonify({"status": "registered", "node": NODE_ID, "peers": PEERS})
    return jsonify({"status": "already_known", "node": NODE_ID, "peers": PEERS})

@app.route('/peers', methods=['GET'])
def list_peers():
    """Liệt kê tất cả peers đã biết trong cluster"""
    return jsonify({"node": NODE_ID, "peers": PEERS, "total_peers": len(PEERS)})

# ─── CAP Theorem Metrics ──────────────────────────────────────────

@app.route('/metrics/write-test', methods=['POST'])
def write_latency_test():
    """
    Đo write latency để chứng minh W=1:
    - local_write_ms: Thời gian ghi vào node cục bộ (cực nhanh)
    - replication: Thời gian replicate sang từng peer (có thể chậm/timeout)
    → Kết luận: Client chỉ cần chờ local_write_ms, không cần chờ replication
    """
    test_session = "__benchmark__"
    test_item = f"bench_{int(time.time()*1000)}"
    
    # Đo local write
    start = time.perf_counter()
    db = load_db()
    if test_session not in db:
        db[test_session] = {"items": {}}
    db[test_session]["items"][test_item] = {
        "status": "active",
        "vclock": increment_clock({}, NODE_ID)
    }
    save_db(db)
    local_write_ms = (time.perf_counter() - start) * 1000
    
    # Đo replication latency từng peer
    replication_results = []
    for peer in PEERS:
        if peer:
            try:
                rep_start = time.perf_counter()
                resp = requests.post(
                    f"{peer}/replicate/{test_session}",
                    json=db[test_session], timeout=2
                )
                rep_ms = (time.perf_counter() - rep_start) * 1000
                replication_results.append({
                    "peer": peer,
                    "latency_ms": round(rep_ms, 2),
                    "status": "ok" if resp.status_code == 200 else "error"
                })
            except requests.exceptions.RequestException:
                replication_results.append({
                    "peer": peer,
                    "latency_ms": None,
                    "status": "timeout/unreachable"
                })
    
    # Dọn dẹp benchmark data
    del db[test_session]["items"][test_item]
    if not db[test_session]["items"]:
        del db[test_session]
    save_db(db)
    
    return jsonify({
        "node": NODE_ID,
        "local_write_ms": round(local_write_ms, 2),
        "replication": replication_results,
        "cap_analysis": {
            "write_quorum": "W=1 (local only)",
            "read_quorum": "R=1 (local only)",
            "cap_choice": "AP (Availability + Partition Tolerance)",
            "consistency_model": "Eventual Consistency via CRDT merge",
            "trade_off": "Client nhận phản hồi ngay sau local write, "
                         "không cần chờ replication → latency thấp, "
                         "nhưng dữ liệu có thể tạm thời không nhất quán giữa các node"
        }
    })

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5001)
    args = parser.parse_args()
    app.run(host="0.0.0.0", port=args.port)