import requests

NODE_A = "http://localhost:5001"

def generate():
    session = "user_dat_123"
    print(f"🚀 Bắt đầu tạo 10 sản phẩm vào Session: {session}...")
    for i in range(1, 11):
        item = f"Product_{i}"
        requests.post(f"{NODE_A}/cart/{session}/add", json={"item": item})
        print(f"Đã thêm: {item}")
    print("✅ Đã tạo xong dữ liệu! Hãy kiểm tra giao diện Web.")

if __name__ == "__main__":
    generate()