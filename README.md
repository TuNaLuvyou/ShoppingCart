# 🛒 CRDT Shopping Cart — Distributed Systems

**Nhóm:** 18367 &nbsp;|&nbsp; **Sinh viên:** Trần Hoàng Đạt — N23DCCN009  
**Đề tài:** #60 — Version-Based Conflict Resolution: Shopping Cart — Category 6

---

## 1. Giới Thiệu

Đây là hệ thống **giỏ hàng phân tán đa chủ (Multi-Master Distributed Shopping Cart)** giải quyết bài toán xung đột dữ liệu trên môi trường phân tán. 

Hệ thống cho phép người dùng thao tác thêm/xóa sản phẩm từ nhiều thiết bị độc lập (Phone, Laptop) ngay cả khi **mất kết nối mạng hoàn toàn** (mạng phân rã), sau đó tự động hội tụ dữ liệu về trạng thái nhất quán cuối cùng (**Eventual Consistency**) khi kết nối trở lại.

### Các công nghệ cốt lõi ứng dụng:
- **State-based CRDT (OR-Set)**: Thuật toán `merge_carts()` hợp nhất dữ liệu cho kết quả tất định ở mọi nút.
- **Vector Clock**: Theo dõi quan hệ nhân quả giữa các thao tác để phát hiện xung đột mà không phụ thuộc thời gian hệ thống.
- **Tombstone Mechanism**: Đánh dấu logic sản phẩm bị xóa (`status=deleted`) thay vì xóa vật lý, giải quyết xung đột bằng chính sách *Tombstone-wins* (Thao tác Xóa ưu tiên hơn Thêm).
- **AP Choice (CAP Theorem)**: Đảm bảo khả năng sẵn sàng cao bằng cấu hình ghi/đọc cục bộ **W=1, R=1**.
- **Active Replication**: Sau mỗi thao tác ghi, node tự động replicate sang peer dưới nền bằng `threading.Thread` (bất đồng bộ, không chặn UI).

---

## 2. Cách Cài Đặt

### Yêu cầu hệ thống:
- **Docker Desktop** (Đang chạy)
- **Python 3.9+** (Để chạy kịch bản demo và kiểm thử hiệu năng)

### Các bước khởi động:

1. **Khởi động các node trong container độc lập:**
   ```bash
   docker compose up --build
   ```
   Hệ thống sẽ chạy các node tương ứng với các thiết bị độc lập:
   - **Node A** (Phone): `http://localhost:5001`
   - **Node B** (Laptop): `http://localhost:5002`

2. **Cài thư viện Python (dành cho kịch bản test):**
   ```bash
   pip install -r requirements.txt
   ```
   > Lưu ý: `demo.py` và `benchmark.py` gọi trực tiếp thuật toán Python nội bộ (`core/merge.py`, `core/vector_clock.py`), không cần Docker hay kết nối mạng.

---

## 3. Cách Sử Dụng

### 3.1. Sử dụng Giao diện Dashboard (Trực quan)
- Mở file `frontend/index.html` trong trình duyệt (Chrome/Edge).
- **Thao tác**: Nhập tên sản phẩm và nhấn `+` để thêm, hoặc bấm biểu tượng **Thùng rác** để xóa (Tombstone).
- **Xem dữ liệu thô**: Nhấp vào `Raw Data` để xem trực tiếp cấu trúc JSON (`ItemList`, `version`, `vclock`) của từng sản phẩm.
- **Dọn dẹp giỏ hàng**: Bấm `Clean Tombstones` để xóa vật lý các sản phẩm đã đánh dấu `deleted`. Chỉ thực hiện sau khi chắc chắn tất cả node đã đồng bộ xong.
- **Đồng bộ thủ công**: Bấm nút `Global Sync` để kích hoạt Anti-Entropy — kéo dữ liệu từ tất cả peer đang online và CRDT-merge về trạng thái hội tụ.

### 3.2. Sử dụng Kịch bản Demo tự động
Chạy kịch bản giả lập các thiết bị ghi offline đồng thời và giải quyết xung đột:
```bash
python demo.py
```

### 3.3. Sử dụng Script kiểm thử hiệu năng (Benchmark)
Chạy script đo hiệu năng thuật toán CRDT thuần (không cần Docker). Gồm 5 giai đoạn: khởi tạo → ghi W=1 (10,000 món) → replicate → giả lập xung đột (A thêm 5k, B xóa 5k) → merge và chốt thời gian từng bước:
```bash
python benchmark.py
```

### 3.4. Mô phỏng thêm nút mới (Horizontal Scaling)
Để mở rộng hệ thống thêm **Node C (Cổng 5003)** trực tiếp khi cluster đang chạy:
```bash
docker compose --profile scale up node_c --build -d
```
Sau khi Node C khởi động, nó chưa có dữ liệu. Kích hoạt giao thức tham gia (Join Protocol) bằng cách gọi Anti-Entropy thủ công trên Node C:
```bash
curl -X POST http://localhost:5003/sync
```
Mở file `storage/node_C_db.json` để kiểm chứng toàn bộ giỏ hàng đã được CRDT-merge sang Node mới.

### 3.5. Mô phỏng Phân rã mạng
```bash
# Cô lập Node A khỏi mạng
docker network disconnect shopping-cart-crdt_default shopping-cart-crdt-node_a-1

# [Thao tác thêm/xóa dữ liệu độc lập trên giao diện Dashboard]

# Kết nối lại Node A và bấm "Global Sync" để hội tụ
docker network connect shopping-cart-crdt_default shopping-cart-crdt-node_a-1
```

---

## 4. Cấu Trúc Thư Mục

```
shopping-cart-crdt/
├── node.py                  # Flask API chính của mỗi node + In-memory Cache + Anti-Entropy
├── core/
│   ├── vector_clock.py      # increment_clock(), compare_clocks(), merge_clocks()
│   └── merge.py             # merge_carts() — OR-Set CRDT với Tombstone-wins
├── frontend/
│   ├── index.html           # Giao diện Dashboard dark-mode glassmorphism
│   ├── style.css            # Stylesheets cho Dashboard
│   ├── app-main.js          # Entry point (ES Module)
│   └── modules/             # Các module JS: api, app, ui, storage, queue, logger, state, constants
├── data/
│   └── generate_data.py     # Script tự động sinh dữ liệu mẫu
├── storage/                 # Bind mount — file JSON database độc lập của các node
├── demo.py                  # Kịch bản giả lập xung đột dữ liệu và CRDT-merge
├── benchmark.py             # Script đo write latency, merge throughput (thuật toán thuần)
├── Dockerfile               # python:3.9-slim — build image cho các node
├── docker-compose.yml       # Cluster: Node A (:5001), Node B (:5002), Node C (:5003, profile=scale)
└── requirements.txt         # Flask, requests, Flask-Cors
```
