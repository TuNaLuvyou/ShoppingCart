import json
import copy
import sys
import io

from core.merge import merge_carts
from core.vector_clock import increment_clock

if sys.platform.startswith('win'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def print_dict(title, d):
    print(f"\n{title}")
    print(json.dumps(d, indent=2, ensure_ascii=False))

def demo():
    print("="*60)
    print("🛒 DEMO THUẬT TOÁN CRDT")
    print("="*60)

    # 1. Khởi tạo giỏ hàng rỗng
    cart_A = {"version": 0, "items": {}}
    cart_B = {"version": 0, "items": {}}

    print("\n[1] TRẠNG THÁI BAN ĐẦU: 2 Node có giỏ hàng rỗng")

    # 2. Hoạt động bình thường: Node A và Node B tự thêm món hàng
    print("\n[2] HOẠT ĐỘNG BÌNH THƯỜNG (CÓ MẠNG)")
    
    # Node A thêm Màn hình
    cart_A["items"]["Màn hình"] = {"status": "active", "vclock": {"A": 1}}
    print("   👉 Node A thêm [Màn hình]")
    
    # Node B thêm Bàn phím
    cart_B["items"]["Bàn phím"] = {"status": "active", "vclock": {"B": 1}}
    print("   👉 Node B thêm [Bàn phím]")

    # 3. Replicate (Đồng bộ lần 1)
    print("\n[3] REPLICATE (TỰ ĐỘNG ĐỒNG BỘ CHÉO)")
    print("   -> Node A và Node B gửi dữ liệu cho nhau...")
    
    # Ở ngoài đời thực, Node A sẽ gọi merge_carts với data của B, và ngược lại.
    # Để giả lập 2 bên đã giống hệt nhau sau khi sync, ta chỉ cần gộp 1 lần và chép ra cho 2 Node.
    cart_A = merge_carts(cart_A, cart_B)
    cart_B = copy.deepcopy(cart_A) 
    
    print_dict("🟢 TRẠNG THÁI SAU KHI REPLICATE (Cả 2 Node đều giống nhau):", cart_A)

    # 4. Mất mạng
    print("\n" + "-"*60)
    print("🔴 ĐỨT MẠNG! 2 Node bị cô lập...")
    print("-" * 60)

    # Node A quyết định thêm một món mới: Chuột
    cart_A["items"]["Chuột"] = {"status": "active", "vclock": increment_clock(cart_A.get("items", {}).get("Chuột", {}).get("vclock", {}), "A")}
    print("   👉 Node A: Bấm THÊM [Chuột] (Lúc này A chưa biết B làm gì)")

    # Node B quyết định xóa Màn hình (món đã có sẵn từ trước)
    cart_B["items"]["Màn hình"]["status"] = "deleted"
    cart_B["items"]["Màn hình"]["vclock"] = increment_clock(cart_B["items"]["Màn hình"]["vclock"], "B")
    print("   👉 Node B: Bấm XÓA [Màn hình] (Lúc này B chưa biết A làm gì)")

    print_dict("⚠️ GIỎ HÀNG NODE A (Đang Offline):", cart_A)
    print_dict("⚠️ GIỎ HÀNG NODE B (Đang Offline):", cart_B)

    # 5. Có mạng lại và Merge
    print("\n" + "-"*60)
    print("🔗 CÓ MẠNG TRỞ LẠI! GỌI HÀM `merge_carts` ĐỂ GIẢI QUYẾT XUNG ĐỘT")
    print("-" * 60)

    final_cart = merge_carts(cart_A, cart_B)
    
    print_dict("✅ KẾT QUẢ CUỐI CÙNG SAU KHI GỘP:", final_cart)

    print("\n" + "="*60)
    print("🎯 CHỐT SỔ KẾT QUẢ THUẬT TOÁN:")
    print(f"   - Món [Chuột] (chỉ A mới thêm): Hệ thống tự động mang qua. Trạng thái: {final_cart['items']['Chuột']['status'].upper()}")
    print(f"   - Món [Bàn phím] (không ai đụng): Giữ nguyên như cũ. Trạng thái: {final_cart['items']['Bàn phím']['status'].upper()}")
    print(f"   - Món [Màn hình] (Bị Node B xóa trong lúc offline): Thuật toán dùng Bia mộ đè lên. Trạng thái: {final_cart['items']['Màn hình']['status'].upper()} (Tombstone-wins)")
    print("="*60)

if __name__ == '__main__':
    demo()
