// CRDT Shopping Cart - Main App Module

import { NODES, CONFIG, SELECTORS, cache, nodeStatus } from "./constants.js";
import { getSessionId, addToQueue, showToast } from "./storage.js";
import { call } from "./api.js";
import { processQueue } from "./queue.js";
import { updateUI } from "./ui.js";

// Global Functions for HTML onclick handlers
window.doAction = async (id, port, act, item) => {
  const sid = getSessionId();
  cache[id] = null;

  if (!nodeStatus[id]) {
    console.log(`📱 Offline: Queuing ${act} ${item} to Node ${id}`);
    addToQueue(id, port, sid, act, item);
    showToast(`Thao tác được lưu. Bấm Sync để đồng bộ.`);
    updateUI();
    return;
  }

  const result = await call(port, `/cart/${sid}/${act}`, "POST", { item });
  if (result) {
    console.log(`✅ Success: ${id} ${act} ${item}`);
  } else {
    console.log(`⚠️ API failed for Node ${id}: Queuing operation`);
    addToQueue(id, port, sid, act, item);
  }

  updateUI();
};

window.clearHistory = async (id, port) => {
  if (!nodeStatus[id]) {
    alert("Không thể dọn dẹp Tombstones khi Node đang offline!");
    return;
  }

  if (
    !confirm(
      `Dọn dẹp tất cả sản phẩm đã xóa (Tombstones) tại Node ${id}? Các sản phẩm đang Active sẽ được giữ lại.`,
    )
  ) {
    return;
  }

  cache[id] = null;
  await call(port, "/clear", "POST");
  updateUI();
};

// ─── Benchmark (CAP Theorem Analysis) ─────────────────────────────

const runBenchmark = async () => {
  const resultsDiv = document.getElementById("benchmark-results");
  resultsDiv.innerHTML = `<div class="benchmark-loading"><i class="fa-solid fa-spinner fa-spin"></i> Đang đo write latency trên tất cả node...</div>`;

  const benchResults = [];

  for (const n of NODES) {
    const result = await call(n.p, "/metrics/write-test", "POST");
    benchResults.push({ node: n, result });
  }

  let html = `
    <div class="benchmark-summary">
      <div class="cap-explanation">
        <h3>📐 CAP Theorem Analysis</h3>
        <p>Hệ thống chọn <strong>AP</strong> (Availability + Partition Tolerance), hy sinh Strong Consistency:</p>
        <ul>
          <li><strong>W = 1</strong>: Ghi chỉ cần thành công tại node cục bộ → client nhận phản hồi ngay</li>
          <li><strong>R = 1</strong>: Đọc từ node cục bộ, không cần quorum</li>
          <li><strong>Eventual Consistency</strong>: CRDT merge đảm bảo hội tụ khi sync</li>
        </ul>
      </div>
    </div>
    <div class="benchmark-table-wrapper">
      <table class="benchmark-table">
        <thead>
          <tr>
            <th>Node</th>
            <th>Local Write (ms)</th>
            <th>Replication</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
  `;

  for (const { node, result } of benchResults) {
    if (!result) {
      html += `
        <tr class="bench-offline">
          <td><strong>Node ${node.id}</strong> (${node.label})</td>
          <td colspan="3" class="text-muted">⬚ Offline — Không kết nối được</td>
        </tr>
      `;
      continue;
    }

    const repDetails = result.replication
      .map((r) => {
        const latency = r.latency_ms !== null ? `${r.latency_ms}ms` : "N/A";
        const icon = r.status === "ok" ? "✅" : "⚠️";
        return `${icon} ${r.peer.split("//")[1]}: ${latency}`;
      })
      .join("<br>");

    html += `
      <tr>
        <td><strong>Node ${result.node}</strong> (${node.label})</td>
        <td class="latency-value ${result.local_write_ms < 10 ? 'latency-good' : 'latency-warn'}">${result.local_write_ms} ms</td>
        <td class="rep-details">${repDetails}</td>
        <td class="latency-good">✅ W=1 OK</td>
      </tr>
    `;
  }

  html += `
        </tbody>
      </table>
    </div>
    <div class="benchmark-conclusion">
      <p><i class="fa-solid fa-circle-info"></i> <strong>Kết luận:</strong> 
      Local write luôn &lt; 10ms (W=1). Replication là fire-and-forget — 
      nếu peer offline, dữ liệu sẽ được đồng bộ sau qua Anti-Entropy (/sync).</p>
    </div>
  `;

  resultsDiv.innerHTML = html;
};

// Initialize Event Listeners
const initEventListeners = () => {
  NODES.forEach((n) => {
    const card = document.querySelector(SELECTORS.nodeCard(n.id));
    if (!card) return; // Node card might not exist yet

    card.querySelector(SELECTORS.btnAdd).onclick = () => {
      const input = card.querySelector(SELECTORS.inputItem);
      if (input.value) {
        doAction(n.id, n.p, "add", input.value);
        input.value = "";
      }
    };

    card.querySelector(
      ".raw-data-toggle .btn-raw:not(.btn-clear-history)",
    ).onclick = () =>
      card.querySelector(SELECTORS.rawDataView).classList.toggle("hidden");
  });

  // Global Sync
  document.querySelector(SELECTORS.syncBtn).onclick = async (e) => {
    const btn = e.currentTarget;
    btn.innerHTML = '<i class="fa-solid fa-rotate fa-spin"></i> Syncing...';
    NODES.forEach((n) => (cache[n.id] = null));
    const onlineNodes = NODES.filter((n) => nodeStatus[n.id]);
    await processQueue(onlineNodes.map((n) => n.id));
    await Promise.all(onlineNodes.map((n) => call(n.p, "/sync", "POST")));
    await updateUI();
    btn.innerHTML = '<i class="fa-solid fa-rotate"></i> Global Sync';
  };

  // Benchmark Modal
  const modal = document.getElementById("benchmark-modal");
  document.getElementById("btn-benchmark").onclick = () => {
    modal.classList.remove("hidden");
  };
  document.getElementById("btn-close-benchmark").onclick = () => {
    modal.classList.add("hidden");
  };
  document.getElementById("btn-run-benchmark").onclick = runBenchmark;
  modal.onclick = (e) => {
    if (e.target === modal) modal.classList.add("hidden");
  };
};

// Start Application
initEventListeners();
setInterval(updateUI, CONFIG.UI_UPDATE_INTERVAL);
updateUI();
