# 🛒 CRDT Shopping Cart — Distributed Systems

**Nhóm:** 18367 &nbsp;|&nbsp; **Sinh viên:** Trần Hoàng Đạt — N23DCCN009  
**Đề tài:** #60 — Version-Based Conflict Resolution: Shopping Cart — Category 6

---

## 1. Giới Thiệu

Đây là hệ thống **giỏ hàng phân tán đa chủ (Multi-Master Distributed Shopping Cart)** giải quyết bài toán xung đột dữ liệu trên môi trường phân tán. 

Hệ thống cho phép người dùng thao tác thêm/xóa sản phẩm từ nhiều thiết bị độc lập (Smartphone, Laptop, Tablet) ngay cả khi **mất kết nối mạng hoàn toàn** (mạng phân rã), sau đó tự động hội tụ dữ liệu về trạng thái nhất quán cuối cùng (**Eventual Consistency**) khi kết nối trở lại.

### Các công nghệ cốt lõi ứng dụng:
- **State-based CRDT**: Thuật toán hợp nhất dữ liệu cho kết quả tất định ở mọi nút.
- **Vector Clock**: Theo dõi quan hệ nhân quả giữa các thao tác để phát hiện xung đột mà không phụ thuộc thời gian hệ thống.
- **Tombstone Mechanism**: Đánh dấu logic sản phẩm bị xóa thay vì xóa vật lý, giải quyết xung đột bằng chính sách *Tombstone-wins* (Thao tác Xóa ưu tiên hơn Thêm).
- **AP Choice (CAP Theorem)**: Đảm bảo khả năng sẵn sàng cao bằng cấu hình ghi/đọc cục bộ **W=1, R=1**.

---

## 2. Cách Cài Đặt

### Yêu cầu hệ thống:
- **Docker Desktop** (Đang chạy)
- **Python 3.10+** (Để chạy kịch bản demo và kiểm thử hiệu năng)

### Các bước khởi động:

1. **Khởi động các node trong container độc lập:**
   ```bash
   docker compose up --build
   ```
   Hệ thống sẽ chạy các node tương ứng với các thiết bị độc lập:
   - **Node A** (Smartphone): `http://localhost:5001`
   - **Node B** (Computer): `http://localhost:5002`

2. **Cài thư viện Python (dành cho kịch bản test):**
   ```bash
   pip install flask flask-cors
   ```
   > Lưu ý: `demo.py` và `benchmark.py` gọi trực tiếp thuật toán Python nội bộ, không cần Docker hay `requests`.

---

## 3. Cách Sử Dụng

### 3.1. Sử dụng Giao diện Dashboard (Trực quan)
- Mở file `frontend/index.html` trong trình duyệt (Chrome/Edge).
- **Thao tác**: Nhập tên sản phẩm và nhấn `+` để thêm, hoặc bấm biểu tượng **Thùng rác** để xóa.
- **Xem dữ liệu thô**: Nhấp vào `Raw Data` để xem trực tiếp cấu trúc JSON và trạng thái Vector Clock của từng sản phẩm.
- **Dọn dẹp giỏ hàng**: Bấm `Clean Tombstones` để xóa vật lý các sản phẩm đã đánh dấu xóa logic.
- **Đồng bộ thủ công**: Bấm nút `Global Sync` để kích hoạt giao tiếp ngang hàng hội tụ dữ liệu giữa các node đang online.
- **Xem phân tích CAP**: Bấm `Benchmark` trên thanh công cụ để xem giải thích trực quan về định lý CAP và đo tốc độ write latency cục bộ.

### 3.2. Sử dụng Kịch bản Demo tự động
Chạy kịch bản giả lập các thiết bị ghi offline đồng thời và giải quyết xung đột:
```bash
python demo.py
```

### 3.3. Sử dụng Script kiểm thử hiệu năng (Benchmark)
Chạy script đo hiệu năng thuật toán CRDT thuần (không cần Docker). Gồm 5 giai đoạn: khởi tạo → ghi W=1 → replicate → giả lập xung đột → merge và chốt thời gian từng bước:
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
├── node.py                  # API chính của mỗi node (Flask) và In-memory cache
├── core/
│   ├── vector_clock.py      # Logic so sánh và merge Vector Clock
│   └── merge.py             # Hàm merge_carts() áp dụng Tombstone-wins
├── frontend/
│   ├── index.html           # Giao diện Dashboard dark-mode glassmorphism
│   ├── style.css            # Stylesheets cho Dashboard và Benchmark Modal
│   └── modules/             # Các module xử lý JS (api, ui, storage, queue...)
├── data/
│   └── generate_data.py     # Script tự động sinh dữ liệu mẫu
├── storage/                 # Thư mục chứa file JSON database độc lập của các node
├── demo.py                  # Kịch bản giả lập xung đột dữ liệu
├── benchmark.py             # Script đo write latency, merge time và độ chính xác
├── Dockerfile               # File cấu hình build image cho các node
├── docker-compose.yml       # Định nghĩa Cluster (Node A, B và Node C scale động)
└── requirements.txt         # Các thư viện phụ thuộc của Python
```
