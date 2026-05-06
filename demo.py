#!/usr/bin/env python3
"""
Demo: Divergent Cart Merging (Giỏ hàng phân kỳ)

Kịch bản:
1. Người dùng thêm sản phẩm từ điện thoại (Node A) - Offline
2. Người dùng thêm sản phẩm từ laptop (Node B) - Offline
3. Người dùng xóa sản phẩm từ tablet (Node C)
4. Tất cả 3 node đồng bộ với nhau
5. Hệ thống hợp nhất (merge) các thay đổi không xung đột
"""

import requests
import json
import time

# API endpoints
NODES = {
    'A': 'http://localhost:5001',
    'B': 'http://localhost:5002',
    'C': 'http://localhost:5003'
}

SESSION = 'demo_session_123'

def call_api(node_id, method, path, data=None):
    """Gửi request tới node"""
    try:
        url = f"{NODES[node_id]}{path}"
        if method == 'GET':
            resp = requests.get(url, timeout=2)
        elif method == 'POST':
            resp = requests.post(url, json=data, timeout=2)
        
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception as e:
        print(f"❌ Lỗi kết nối Node {node_id}: {e}")
        return None

def print_cart_state(node_id, title=""):
    """In ra trạng thái giỏ hàng của một node"""
    result = call_api(node_id, 'GET', f'/cart/{SESSION}')
    if not result:
        print(f"  ⚠️  Không kết nối được Node {node_id}")
        return None
    
    cart = result.get('raw_data', {})
    version = result.get('version', 0)
    
    print(f"\n📦 Node {node_id} {title}")
    print(f"   Version: {version}")
    
    items = cart.get('items', {})
    active = [k for k, v in items.items() if v['status'] == 'active']
    deleted = [k for k, v in items.items() if v['status'] == 'deleted']
    
    if active:
        print(f"   ✅ Active items ({len(active)}): {', '.join(active)}")
    if deleted:
        print(f"   ❌ Deleted items ({len(deleted)}): {', '.join(deleted)}")
    
    if not active and not deleted:
        print(f"   (Trống)")
    
    return cart

def demo():
    print("\n" + "="*70)
    print("🛒 DEMO: DIVERGENT CART MERGING")
    print("="*70)
    
    # BƯỚC 1: Reset tất cả node
    print("\n[1] 🔄 Reset tất cả nodes...")
    for node in ['A', 'B', 'C']:
        call_api(node, 'POST', '/clear')
    time.sleep(0.5)
    
    # BƯỚC 2: Thêm dữ liệu từ các node khác nhau (OFFLINE - không đồng bộ ngay)
    print("\n[2] 📱 Node A (Smartphone) - Thêm sản phẩm OFFLINE")
    call_api('A', 'POST', f'/cart/{SESSION}/add', {'item': 'Laptop'})
    print("   ➕ Thêm: Laptop (vclock: A=1)")
    time.sleep(0.3)
    
    call_api('A', 'POST', f'/cart/{SESSION}/add', {'item': 'Mouse'})
    print("   ➕ Thêm: Mouse (vclock: A=2)")
    time.sleep(0.3)
    
    print_cart_state('A', "sau khi thêm sản phẩm")
    
    print("\n[3] 💻 Node B (Laptop) - Thêm sản phẩm OFFLINE (khác với A)")
    call_api('B', 'POST', f'/cart/{SESSION}/add', {'item': 'Keyboard'})
    print("   ➕ Thêm: Keyboard (vclock: B=1)")
    time.sleep(0.3)
    
    call_api('B', 'POST', f'/cart/{SESSION}/add', {'item': 'Monitor'})
    print("   ➕ Thêm: Monitor (vclock: B=2)")
    time.sleep(0.3)
    
    print_cart_state('B', "sau khi thêm sản phẩm")
    
    print("\n[4] 📱 Node C (Tablet) - Thêm một số sản phẩm OFFLINE")
    call_api('C', 'POST', f'/cart/{SESSION}/add', {'item': 'Charger'})
    print("   ➕ Thêm: Charger (vclock: C=1)")
    time.sleep(0.3)
    
    call_api('C', 'POST', f'/cart/{SESSION}/add', {'item': 'USB Cable'})
    print("   ➕ Thêm: USB Cable (vclock: C=2)")
    time.sleep(0.3)
    
    print_cart_state('C', "sau khi thêm sản phẩm")
    
    # BƯỚC 3: Mô phỏng xung đột - cùng một item được thêm/xóa từ 2 node
    print("\n[5] 🔥 XUNG ĐỘT: Cùng một item được thêm và xóa từ 2 node")
    print("   (Trong khi các node OFFLINE)")
    
    # Cả A và B đều có item "Headphone"
    call_api('A', 'POST', f'/cart/{SESSION}/add', {'item': 'Headphone'})
    print("   ➕ Node A: Thêm Headphone")
    time.sleep(0.2)
    
    call_api('B', 'POST', f'/cart/{SESSION}/remove', {'item': 'Headphone'})
    print("   ➖ Node B: Xóa Headphone")
    time.sleep(0.2)
    
    print_cart_state('A', "- Node A muốn GIỮ Headphone")
    print_cart_state('B', "- Node B muốn XÓA Headphone")
    
    # BƯỚC 4: Đồng bộ dữ liệu
    print("\n[6] 🔗 ĐỒNG BỘ DỮ LIỆU (Mô phỏng Node kết nối lại)")
    print("   Gọi Global Sync...")
    
    # Sync Node A
    call_api('A', 'POST', '/sync')
    time.sleep(0.5)
    
    # Sync Node B
    call_api('B', 'POST', '/sync')
    time.sleep(0.5)
    
    # Sync Node C
    call_api('C', 'POST', '/sync')
    time.sleep(0.5)
    
    # BƯỚC 5: Hiển thị kết quả sau merge
    print("\n[7] ✅ KẾT QUẢ SAU MERGE")
    print("   Tất cả 3 node bây giờ phải GIỐNG NHAU:")
    
    cart_a = print_cart_state('A', "(Smartphone)")
    cart_b = print_cart_state('B', "(Laptop)")
    cart_c = print_cart_state('C', "(Tablet)")
    
    # BƯỚC 6: Phân tích kết quả
    print("\n[8] 📊 PHÂN TÍCH MERGE LOGIC")
    print("   ✓ Tất cả item từ A, B, C được HỢPNHẤT")
    print("   ✓ Vector Clock theo dõi quan hệ nhân quả")
    
    if cart_a and cart_b and cart_c:
        items_a = cart_a.get('items', {})
        items_b = cart_b.get('items', {})
        items_c = cart_c.get('items', {})
        
        # Check Headphone - nên bị XÓA vì Tombstone thắng
        headphone_a = items_a.get('Headphone', {}).get('status')
        headphone_b = items_b.get('Headphone', {}).get('status')
        headphone_c = items_c.get('Headphone', {}).get('status')
        
        print(f"\n   🎯 Chi tiết Headphone (Conflict Resolution):")
        print(f"      - Node A: Headphone status = {headphone_a}")
        print(f"      - Node B: Headphone status = {headphone_b}")
        print(f"      - Node C: Headphone status = {headphone_c}")
        print(f"      → Kết quả: {'✅ DELETED (Tombstone wins)' if headphone_a == 'deleted' else '❌ INCONSISTENT'}")
    
    print("\n[9] 🎓 KIẾN THỨC ÁP DỤNG")
    print("   ✓ Causal Ordering: Vector Clock theo dõi mối quan hệ nhân quả")
    print("   ✓ Tombstone Mechanism: Item bị xóa được đánh dấu 'deleted'")
    print("   ✓ Last-Write-Wins with Tombstone: Xóa thắng thêm trong xung đột")
    print("   ✓ Version Tracking: Cart version tăng mỗi lần merge")
    print("   ✓ Eventual Consistency: Tất cả node cuối cùng đều đạt trạng thái nhất quán")
    
    print("\n" + "="*70)
    print("✨ Demo hoàn thành!")
    print("="*70)

if __name__ == "__main__":
    print("\n⏳ Chờ servers khởi động... (Hãy chắc chắn 3 nodes đã chạy)")
    print("Bạn có thể chạy: docker-compose up\n")
    
    # Test connection
    max_retry = 3
    for attempt in range(max_retry):
        if call_api('A', 'GET', '/health') and call_api('B', 'GET', '/health') and call_api('C', 'GET', '/health'):
            demo()
            break
        if attempt < max_retry - 1:
            print(f"🔄 Thử lại ({attempt + 1}/{max_retry})...")
            time.sleep(2)
    else:
        print("❌ Không thể kết nối các nodes. Hãy chắc chắn Docker containers đã khởi động.")
