from core.vector_clock import compare_clocks, merge_clocks

def merge_carts(cart1, cart2):
    """Hợp nhất 2 giỏ hàng dựa trên Vector Clock và Tombstone"""
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
            rel = compare_clocks(item1["vclock"], item2["vclock"])
            if rel == 'vc1_newer':
                merged_items[key] = item1
            elif rel == 'vc2_newer':
                merged_items[key] = item2
            else:
                # Concurrent (Xung đột) -> Ưu tiên Tombstone (xóa thắng thêm)
                new_status = "deleted" if (item1["status"] == "deleted" or item2["status"] == "deleted") else "active"
                merged_items[key] = {
                    "status": new_status,
                    "vclock": merge_clocks(item1["vclock"], item2["vclock"])
                }
                
    return {"items": merged_items}