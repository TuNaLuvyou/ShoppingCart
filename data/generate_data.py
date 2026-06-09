import requests

NODE_A = "http://localhost:5001"

def generate():
    session = "user_dat_123"
    print(f"🚀 Bắt đầu tạo 10 sản phẩm vào Session: {session}...")
    for i in range(1, 11):
        item = f"Product_{i}"
        try:
            response = requests.post(f"{NODE_A}/cart/{session}/add", json={"item": item})
            if response.status_code == 200:
                print(f"Đã thêm: {item}")
            else:
                print(f"Lỗi khi thêm {item}: {response.status_code}")
        except requests.exceptions.ConnectionError:
            print(f"❌ Lỗi: Không thể kết nối tới {NODE_A}. Vui lòng đảm bảo server đang chạy!")
            return
    print("✅ Đã tạo xong dữ liệu! Hãy kiểm tra giao diện Web.")

if __name__ == "__main__":
    generate()