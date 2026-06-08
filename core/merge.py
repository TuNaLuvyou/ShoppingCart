from core.vector_clock import compare_clocks, merge_clocks

def merge_carts(cart1, cart2):
    """Hop nhat 2 gio hang dua tren Vector Clock va Tombstone - OR-Set CRDT"""
    merged_items = {}
    all_keys = set(cart1.get("ItemList", {}).keys()) | set(cart2.get("ItemList", {}).keys())

    for key in all_keys:
        item1 = cart1.get("ItemList", {}).get(key)
        item2 = cart2.get("ItemList", {}).get(key)

        if item1 and not item2:
            merged_items[key] = item1
        elif item2 and not item1:
            merged_items[key] = item2
        else:
            # Khi sync: so sanh Vector Clock de phat hien xung dot
            rel = compare_clocks(item1["vclock"], item2["vclock"])
            if rel == "vc1_newer":
                merged_items[key] = item1
            elif rel == "vc2_newer":
                merged_items[key] = item2
            else:
                # Concurrent -> Tombstone-wins (xoa thang them)
                new_status = (
                    "deleted"
                    if (item1["status"] == "deleted" or item2["status"] == "deleted")
                    else "active"
                )
                merged_items[key] = {
                    "status": new_status,
                    "vclock": merge_clocks(item1["vclock"], item2["vclock"]),
                }

    # Lay version cao nhat tu 2 cart
    merged_version = max(cart1.get("version", 0), cart2.get("version", 0))

    return {"version": merged_version, "ItemList": merged_items}