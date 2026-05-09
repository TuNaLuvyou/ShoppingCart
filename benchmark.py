#!/usr/bin/env python3
"""
Benchmark: Đo hiệu năng hệ thống Shopping Cart CRDT

Chỉ số đo:
  1. Local Write Latency (W=1): Thời gian ghi vào node cục bộ
  2. Merge Time: Thời gian hợp nhất 2 cart lớn
  3. Convergence Time: Thời gian để tất cả node hội tụ
  4. Scalability: So sánh hiệu năng khi tăng số lượng item
"""

import requests
import time
import json
import sys

NODES = {
    'A': 'http://localhost:5001',
    'B': 'http://localhost:5002',
    'C': 'http://localhost:5003',
}

def call_api(node_id, method, path, data=None):
    try:
        url = f"{NODES[node_id]}{path}"
        if method == 'GET':
            resp = requests.get(url, timeout=5)
        else:
            resp = requests.post(url, json=data, timeout=5)
        return resp.json() if resp.status_code == 200 else None
    except Exception:
        return None

def check_nodes():
    """Kiểm tra tất cả node đang hoạt động"""
    for nid in NODES:
        result = call_api(nid, 'GET', '/health')
        if not result:
            print(f"❌ Node {nid} không phản hồi! Hãy chạy: docker compose up")
            return False
    return True

def benchmark_write_latency(num_items=100):
    """Benchmark 1: Đo Write Latency (W=1)"""
    print(f"\n{'='*60}")
    print(f"📊 BENCHMARK 1: Write Latency (W=1) — {num_items} items")
    print(f"{'='*60}")
    
    session = f"bench_write_{int(time.time())}"
    latencies = []
    
    for i in range(num_items):
        start = time.perf_counter()
        call_api('A', 'POST', f'/cart/{session}/add', {'item': f'item_{i}'})
        elapsed = (time.perf_counter() - start) * 1000
        latencies.append(elapsed)
    
    avg = sum(latencies) / len(latencies)
    p50 = sorted(latencies)[len(latencies) // 2]
    p99 = sorted(latencies)[int(len(latencies) * 0.99)]
    min_l = min(latencies)
    max_l = max(latencies)
    
    print(f"  Items written: {num_items}")
    print(f"  Avg latency:   {avg:.2f} ms")
    print(f"  P50 latency:   {p50:.2f} ms")
    print(f"  P99 latency:   {p99:.2f} ms")
    print(f"  Min latency:   {min_l:.2f} ms")
    print(f"  Max latency:   {max_l:.2f} ms")
    print(f"  Throughput:     {1000/avg:.0f} ops/sec")
    
    return {"avg": avg, "p50": p50, "p99": p99, "min": min_l, "max": max_l}

def benchmark_merge_time():
    """Benchmark 2: Đo Merge Time (CRDT merge 2 cart lớn)"""
    print(f"\n{'='*60}")
    print(f"📊 BENCHMARK 2: Merge Time — 2 divergent carts")
    print(f"{'='*60}")
    
    session = f"bench_merge_{int(time.time())}"
    
    # Ghi 50 items vào Node A (offline từ B)
    print("  → Writing 50 items to Node A...")
    for i in range(50):
        call_api('A', 'POST', f'/cart/{session}/add', {'item': f'phone_item_{i}'})
    
    # Ghi 50 items khác vào Node B (offline từ A)
    print("  → Writing 50 items to Node B...")
    for i in range(50):
        call_api('B', 'POST', f'/cart/{session}/add', {'item': f'laptop_item_{i}'})
    
    # Đo thời gian sync (merge)
    print("  → Syncing Node A...")
    start = time.perf_counter()
    call_api('A', 'POST', '/sync')
    sync_a_ms = (time.perf_counter() - start) * 1000
    
    print("  → Syncing Node B...")
    start = time.perf_counter()
    call_api('B', 'POST', '/sync')
    sync_b_ms = (time.perf_counter() - start) * 1000
    
    print("  → Syncing Node C...")
    start = time.perf_counter()
    call_api('C', 'POST', '/sync')
    sync_c_ms = (time.perf_counter() - start) * 1000
    
    print(f"\n  Node A sync: {sync_a_ms:.2f} ms")
    print(f"  Node B sync: {sync_b_ms:.2f} ms")
    print(f"  Node C sync: {sync_c_ms:.2f} ms")
    
    # Kiểm tra convergence
    cart_a = call_api('A', 'GET', f'/cart/{session}')
    cart_b = call_api('B', 'GET', f'/cart/{session}')
    cart_c = call_api('C', 'GET', f'/cart/{session}')
    
    items_a = set(cart_a['raw_data']['items'].keys()) if cart_a else set()
    items_b = set(cart_b['raw_data']['items'].keys()) if cart_b else set()
    items_c = set(cart_c['raw_data']['items'].keys()) if cart_c else set()
    
    converged = items_a == items_b == items_c
    print(f"\n  Total items per node: A={len(items_a)}, B={len(items_b)}, C={len(items_c)}")
    print(f"  Convergence: {'✅ PASS — Tất cả node có cùng dữ liệu' if converged else '❌ FAIL'}")
    
    return {"sync_a": sync_a_ms, "sync_b": sync_b_ms, "sync_c": sync_c_ms, "converged": converged}

def benchmark_conflict_resolution():
    """Benchmark 3: Đo Conflict Resolution (Tombstone-wins)"""
    print(f"\n{'='*60}")
    print(f"📊 BENCHMARK 3: Conflict Resolution — Tombstone Wins")
    print(f"{'='*60}")
    
    session = f"bench_conflict_{int(time.time())}"
    conflicts_correct = 0
    total_tests = 20
    
    for i in range(total_tests):
        item = f"conflict_item_{i}"
        
        # Node A thêm item
        call_api('A', 'POST', f'/cart/{session}/add', {'item': item})
        # Node B xóa item (concurrent)
        call_api('B', 'POST', f'/cart/{session}/remove', {'item': item})
    
    # Sync tất cả
    call_api('A', 'POST', '/sync')
    call_api('B', 'POST', '/sync')
    call_api('C', 'POST', '/sync')
    
    # Kiểm tra kết quả
    cart = call_api('A', 'GET', f'/cart/{session}')
    if cart and cart.get('raw_data', {}).get('items'):
        items = cart['raw_data']['items']
        for i in range(total_tests):
            item = f"conflict_item_{i}"
            if item in items and items[item]['status'] == 'deleted':
                conflicts_correct += 1
    
    print(f"  Total concurrent conflicts: {total_tests}")
    print(f"  Tombstone-wins correct:     {conflicts_correct}/{total_tests}")
    print(f"  Accuracy:                   {conflicts_correct/total_tests*100:.0f}%")
    print(f"  Result: {'✅ PASS' if conflicts_correct == total_tests else '⚠️ Partial'}")
    
    return {"total": total_tests, "correct": conflicts_correct}

def benchmark_scalability():
    """Benchmark 4: Đo Scalability — So sánh hiệu năng khi tăng dataset"""
    print(f"\n{'='*60}")
    print(f"📊 BENCHMARK 4: Scalability Analysis")
    print(f"{'='*60}")
    
    sizes = [10, 50, 100, 200]
    results = []
    
    print(f"\n  {'Items':<10} {'Write Avg (ms)':<18} {'Sync (ms)':<15} {'Ops/sec':<10}")
    print(f"  {'-'*53}")
    
    for size in sizes:
        session = f"bench_scale_{size}_{int(time.time())}"
        
        # Write
        latencies = []
        for i in range(size):
            start = time.perf_counter()
            call_api('A', 'POST', f'/cart/{session}/add', {'item': f'item_{i}'})
            latencies.append((time.perf_counter() - start) * 1000)
        
        avg_write = sum(latencies) / len(latencies)
        
        # Sync
        start = time.perf_counter()
        call_api('A', 'POST', '/sync')
        sync_ms = (time.perf_counter() - start) * 1000
        
        ops_sec = 1000 / avg_write
        results.append({"size": size, "avg_write": avg_write, "sync": sync_ms, "ops_sec": ops_sec})
        
        print(f"  {size:<10} {avg_write:<18.2f} {sync_ms:<15.2f} {ops_sec:<10.0f}")
    
    return results

def main():
    print("\n" + "="*60)
    print("🚀 CRDT SHOPPING CART — PERFORMANCE BENCHMARK")
    print("="*60)
    print(f"  Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Nodes: {', '.join(f'{k} ({v})' for k, v in NODES.items())}")
    
    if not check_nodes():
        sys.exit(1)
    
    print("\n✅ Tất cả node đang hoạt động. Bắt đầu benchmark...\n")
    
    # Reset
    for nid in NODES:
        call_api(nid, 'POST', '/clear')
    
    results = {}
    results['write_latency'] = benchmark_write_latency(100)
    results['merge'] = benchmark_merge_time()
    results['conflict'] = benchmark_conflict_resolution()
    results['scalability'] = benchmark_scalability()
    
    # Summary
    print(f"\n{'='*60}")
    print(f"📋 TỔNG KẾT")
    print(f"{'='*60}")
    print(f"  Write Latency (avg):    {results['write_latency']['avg']:.2f} ms {'✅' if results['write_latency']['avg'] < 10 else '⚠️'}")
    print(f"  Write Latency (P99):    {results['write_latency']['p99']:.2f} ms")
    print(f"  Merge Convergence:      {'✅ PASS' if results['merge']['converged'] else '❌ FAIL'}")
    print(f"  Conflict Resolution:    {results['conflict']['correct']}/{results['conflict']['total']} correct")
    print(f"  CAP Choice:             AP (W=1, R=1, Eventual Consistency)")
    print(f"\n{'='*60}")
    print(f"✨ Benchmark hoàn thành!")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
