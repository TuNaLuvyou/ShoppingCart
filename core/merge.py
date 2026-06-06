from core.vector_clock import compare_clocks, merge_clocks

def merge_quantities(item1, item2):
    q1 = item1.get("quantity", {})
    q2 = item2.get("quantity", {})
    if not isinstance(q1, dict): q1 = {"A": q1}
    if not isinstance(q2, dict): q2 = {"B": q2}
    
    v1 = item1.get("vclock", {})
    v2 = item2.get("vclock", {})
    
    res = {}
    for n in set(q1.keys()) | set(q2.keys()):
        if v1.get(n, 0) > v2.get(n, 0):
            res[n] = q1.get(n, 0)
        else:
            res[n] = q2.get(n, 0)
    return res

def merge_carts(cart1, cart2):
    """Hợp nhất 2 giỏ hàng dựa trên Vector Clock, Tombstone và Version"""
    merged_items = {}
    all_keys = set(cart1.get("items", {}).keys()) | set(cart2.get("items", {}).keys())
    
    for key in all_keys:
        item1 = cart1.get("items", {}).get(key)
        item2 = cart2.get("items", {}).get(key)
        
        if item1 and not item2:
            merged_items[key] = item1
        elif item2 and not item1:
            merged_items[key] = item2
        else: 
            #khi sync (thao tác trên cùng món hàng sẽ bị xung đột)
            rel = compare_clocks(item1["vclock"], item2["vclock"])
            if rel == 'vc1_newer':
                merged_items[key] = item1
            elif rel == 'vc2_newer':
                merged_items[key] = item2
            else:
                # Concurrent (Xung đột) -> Ưu tiên Tombstone (xóa thắng thêm)
                new_status = "deleted" if (item1["status"] == "deleted" or item2["status"] == "deleted") else "active"
                new_qty = merge_quantities(item1, item2) if new_status == "active" else {}
                merged_items[key] = {
                    "status": new_status,
                    "quantity": new_qty,
                    "vclock": merge_clocks(item1["vclock"], item2["vclock"])
                }
    
    # Lấy version cao nhất từ 2 cart và tăng thêm 1
    merged_version = max(cart1.get("version", 0), cart2.get("version", 0)) + 1
    
    return {"version": merged_version, "items": merged_items}