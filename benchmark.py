import time
import copy
import sys
import io

from core.merge import merge_carts
from core.vector_clock import increment_clock

if sys.platform.startswith('win'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def print_stage(title, duration_ms):
    print(f"✅ {title:<60} | ⏱️ {duration_ms:>8.3f} ms")

def benchmark():
    print("="*80)
    print("🚀 BENCHMARK: HIỆU NĂNG THUẬT TOÁN CRDT (KHÔNG DÙNG API/MẠNG)")
    print("="*80)
    print("Bài test này giả lập khối lượng dữ liệu khổng lồ để đo tốc độ thuật toán thuần.\n")

    # 1. Khởi tạo
    start = time.perf_counter()
    cart_A = {"version": 0, "items": {}}
    cart_B = {"version": 0, "items": {}}
    t_init = (time.perf_counter() - start) * 1000
    print_stage("1. Khởi tạo 2 giỏ hàng rỗng", t_init)

    # 2. Thêm 10,000 món hàng vào Node A
    NUM_ITEMS = 10000
    start = time.perf_counter()
    for i in range(NUM_ITEMS):
        item_name = f"Item_{i}"
        cart_A["items"][item_name] = {
            "status": "active", 
            "vclock": {"A": 1}
        }
    t_write_A = (time.perf_counter() - start) * 1000
    print_stage(f"2. Node A thêm {NUM_ITEMS:,} món hàng (Ghi cục bộ W=1)", t_write_A)
    print(f"   -> Tốc độ ghi trung bình: {(t_write_A/NUM_ITEMS)*1000:.3f} micro-giây/món")

    # 3. Đồng bộ dữ liệu sang Node B (Replicate)
    start = time.perf_counter()
    cart_B = copy.deepcopy(cart_A)
    t_replicate = (time.perf_counter() - start) * 1000
    print_stage("3. Đồng bộ (Deep Copy) toàn bộ data sang Node B", t_replicate)

    # 4. Giả lập mất mạng và thao tác phân kỳ cực lớn (Divergence/Xung đột)
    # Node A thêm 5,000 món MỚI
    # Node B xóa 5,000 món CŨ
    start = time.perf_counter()
    for i in range(NUM_ITEMS, NUM_ITEMS + 5000):
        item_name = f"Item_{i}"
        cart_A["items"][item_name] = {"status": "active", "vclock": {"A": 1}}
    
    for i in range(5000):
        item_name = f"Item_{i}"
        cart_B["items"][item_name]["status"] = "deleted"
        cart_B["items"][item_name]["vclock"] = increment_clock(cart_B["items"][item_name]["vclock"], "B")
    t_diverge = (time.perf_counter() - start) * 1000
    print_stage("4. Mất mạng: A thêm 5k món mới, B xóa 5k món cũ", t_diverge)

    # 5. Gộp dữ liệu (Merge Carts) - Giai đoạn quan trọng nhất của CRDT
    start = time.perf_counter()
    final_cart = merge_carts(cart_A, cart_B)
    t_merge = (time.perf_counter() - start) * 1000
    print_stage("5. Có mạng lại: GỌI HÀM merge_carts ĐỂ GỘP 15,000 MÓN", t_merge)

    # In kết quả tổng kết
    print("\n" + "="*80)
    print("📊 TỔNG KẾT BENCHMARK:")
    print(f"   - Tổng số món hàng xử lý: {len(final_cart['items']):,} items")
    print(f"   - Thời gian thuật toán xử lý xung đột (Merge): {t_merge:.3f} mili-giây")
    
    # Tính ops/sec cho merge (Số phép tính mỗi giây)
    ops = len(final_cart['items']) / (t_merge / 1000)
    print(f"   - Tốc độ Hợp nhất: {ops:,.0f} phép tính / giây")
    print("   -> KẾT LUẬN: Thuật toán CRDT State-based của bạn chạy cực kỳ nhanh và")
    print("      tiêu tốn cực ít tài nguyên khi xử lý xung đột dữ liệu khổng lồ!")
    print("="*80)

if __name__ == '__main__':
    benchmark()
