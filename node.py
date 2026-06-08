import os, json, copy, argparse, threading, requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from core.vector_clock import increment_clock
from core.merge import merge_carts

app = Flask(__name__)
CORS(app)

NODE_ID      = os.environ.get("NODE_ID", "A")
PEERS        = list(filter(None, os.environ.get("PEERS", "").split(",")))
STORAGE_FILE = f"storage/node_{NODE_ID}_db.json"

_db_cache = None
db_lock   = threading.Lock()

# ─── Database helpers ──────────────────────────────────────────────
def load_db():
    """Đọc database từ In-memory Cache (R=1).
    Ưu tiên cache để tránh đọc file mỗi request, chỉ đọc file khi cache trống."""
    global _db_cache
    with db_lock:
        if _db_cache is None:
            try:
                with open(STORAGE_FILE, "r", encoding="utf-8") as f:
                    _db_cache = json.load(f)
            except Exception:
                _db_cache = {}
        return _db_cache

def save_db(db):
    """Ghi database vào Cache và file JSON (W=1 — Persistence).
    Dùng Lock để tránh Race Condition khi API và Anti-Entropy ghi đồng thời."""
    global _db_cache
    with db_lock:
        _db_cache = db
        os.makedirs("storage", exist_ok=True)
        with open(STORAGE_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=4, ensure_ascii=False)

def get_cart(db, sid):
    """Lấy giỏ hàng theo Session ID. Tự khởi tạo giỏ rỗng nếu chưa tồn tại."""
    if sid not in db:
        db[sid] = {"version": 0, "items": {}}
    return db[sid]

# ─── Anti-Entropy ──────────────────────────────────────────────────
def sync_with_peers(): # Sau khi mở rộng bằng docker xong thì hệ thống sẽ tự động merge dữ liệu qua
    """Passive Anti-Entropy: kéo toàn bộ dữ liệu từ các peer và thực hiện CRDT-merge.
    Chỉ ghi file xuống đĩa khi có sự thay đổi thực sự, tránh ghi thừa."""
    db, changed = load_db(), False
    for peer in PEERS: # Bắt đầu vòng lập đưa dữ liệu qua
        try:
            resp = requests.get(f"{peer}/dump", timeout=2)
            if resp.ok:
                for sid, incoming in resp.json().items():
                    local = get_cart(db, sid)
                    merged = merge_carts(local, incoming)
                    if json.dumps(merged, sort_keys=True) != json.dumps(local, sort_keys=True):
                        db[sid] = merged
                        changed = True
        except Exception:
            pass
    if changed:
        save_db(db)
    return db

# ─── API Routes ────────────────────────────────────────────────────
@app.get("/cart/<sid>")
def api_get_cart(sid):
    """[GET] Trả về danh sách sản phẩm của giỏ hàng (giao diện tự gọi định kỳ để cập nhật UI).
    Lọc ẩn các Tombstone (status=deleted) khỏi người dùng, chỉ hiển thị sản phẩm active."""
    db   = load_db()
    cart = get_cart(db, sid)
    active = [k for k, v in cart["items"].items() if v["status"] == "active"]
    return jsonify({"session_id": sid, "version": cart["version"], "active_items": active, "raw_data": cart})

@app.post("/cart/<sid>/<action>")
def api_modify(sid, action):
    """[POST] Thêm (add) hoặc xóa logic (remove) sản phẩm khỏi giỏ hàng
    (khi người dùng bấm nút [+] hoặc nút [Xóa] trên giao diện).
    Xóa dùng cơ chế Tombstone (status=deleted) để giữ lịch sử và đồng bộ xung đột đúng.
    Sau khi ghi cục bộ (W=1), tự động replicate sang tất cả peer dưới nền."""

    if action not in ("add", "remove"):
        return jsonify({"error": "Invalid action"}), 400
    item = (request.json or {}).get("item", "").strip().title()
    if not item:
        return jsonify({"error": "Item name required"}), 400

    db   = load_db()
    cart = get_cart(db, sid)
    curr = cart["items"].get(item, {"status": "active", "vclock": {}})
    cart["items"][item] = {"status": "active" if action == "add" else "deleted",
                           "vclock": increment_clock(curr["vclock"], NODE_ID)}
    cart["version"] += 1
    save_db(db)

    # Active replication — fire-and-forget (W=1)
    snapshot = copy.deepcopy(cart)
    def replicate():
        for peer in PEERS:
            try:
                requests.post(f"{peer}/replicate/{sid}", json=snapshot, timeout=1)
            except Exception:
                pass
    threading.Thread(target=replicate, daemon=True).start() # Luồng chạy ngầm
    return jsonify({"message": f"{item} {action}d at Node {NODE_ID}", "version": cart["version"], "cart": cart})

@app.post("/replicate/<sid>")
def api_replicate(sid):
    """[POST] Nhận dữ liệu replicate từ peer và thực hiện CRDT-merge với bản cục bộ
    (tự động gọi ngầm khi một node khác bấm [+] hoặc [Xoá] — Active Replication).
    Người dùng không thấy bước này, hệ thống tự xử lý dưới nền."""
    db = load_db()
    db[sid] = merge_carts(get_cart(db, sid), request.json)
    save_db(db)
    return jsonify({"status": "replicated"})

@app.post("/sync")
def api_sync():
    """[POST] Kích hoạt Anti-Entropy thủ công (khi người dùng bấm nút [Global Sync] trên giao diện).
    Kéo toàn bộ dữ liệu từ các peer online, thực hiện CRDT-merge và trả về trạng thái sau khi hội tụ."""
    return jsonify({"status": "synced", "db": sync_with_peers()})

@app.get("/dump")
def api_dump():
    """[GET] Xuất toàn bộ dữ liệu thô của node
    (tự động gọi ngầm khi một node khác bấm [Global Sync] — để lấy data về merge)."""
    return jsonify(load_db())

@app.get("/health")
def api_health():
    """[GET] Kiểm tra trạng thái hoạt động của node
    (giao diện tự gọi định kỳ để hiển thị Online/Offline)."""
    return jsonify({"status": "ok", "node": NODE_ID})

@app.post("/clear")
def api_clear():
    """[POST] Dọn dẹp Tombstone: xóa vật lý các sản phẩm đã bị đánh dấu deleted
    (khi người dùng bấm nút [Clean Tombstones] trên giao diện).
    Lưu ý: chỉ thực hiện sau khi chắc chắn tất cả node đã đồng bộ xong."""
    db = load_db()
    for cart in db.values():
        cart["items"] = {k: v for k, v in cart["items"].items() if v["status"] == "active"}
    save_db(db)
    return jsonify({"status": "cleaned"})

# ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5001)
    args = parser.parse_args()
    app.run(host="0.0.0.0", port=args.port)