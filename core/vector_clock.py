def increment_clock(vclock, node_id):
    """Tăng vector clock của node hiện tại lên 1"""
    new_vclock = vclock.copy()
    new_vclock[node_id] = new_vclock.get(node_id, 0) + 1
    return new_vclock

def compare_clocks(vc1, vc2):
    """
    So sánh 2 vector clock. 
    Trả về: 'vc1_newer', 'vc2_newer', 'equal', hoặc 'concurrent' (xung đột)
    """
    if vc1 == vc2:
        return 'equal'
        
    keys = set(vc1.keys()) | set(vc2.keys())
    vc1_greater_or_equal = all(vc1.get(k, 0) >= vc2.get(k, 0) for k in keys)
    vc2_greater_or_equal = all(vc2.get(k, 0) >= vc1.get(k, 0) for k in keys)
    
    if vc1_greater_or_equal:
        return 'vc1_newer'
    if vc2_greater_or_equal:
        return 'vc2_newer'
        
    return 'concurrent'

def merge_clocks(vc1, vc2):
    """Gộp 2 vector clock bằng cách lấy giá trị max của mỗi node"""
    keys = set(vc1.keys()) | set(vc2.keys())
    return {k: max(vc1.get(k, 0), vc2.get(k, 0)) for k in keys}