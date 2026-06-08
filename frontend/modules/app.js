// CRDT Shopping Cart - Module Ứng dụng chính

import { NODES, CONFIG, SELECTORS, cache, nodeStatus } from "./constants.js";
import { getSessionId, addToQueue, showToast } from "./storage.js";
import { call } from "./api.js";
import { processQueue } from "./queue.js";
import { updateUI, addDynamicNode } from "./ui.js";
import {
  buildLogPanel, updateCountBadge,
  logAdd, logRemove, logOffline, logOnline, logQueue,
  logSync, logMerge, logTombstone, logInfo, logError, logReplicate,
} from "./logger.js";

// Build log panel on startup
buildLogPanel();
logInfo("Nodes registered: Phone (5001), Laptop (5002)");

// Các hàm toàn cục (Global) cho các sự kiện onclick trên HTML
window.doAction = async (id, port, act, item) => {
  const sid = getSessionId();
  cache[id] = null;

  if (!nodeStatus[id]) {
    console.log(`📱 Offline: Queuing ${act} ${item} to Node ${id}`);
    addToQueue(id, port, sid, act, item);
    showToast(`Thao tác được lưu. Bấm Sync để đồng bộ.`);
    logQueue(id, act, item);  // chỉ log thao tác bị queue, không log offline lặp
    updateCountBadge();
    updateUI();
    return;
  }

  const result = await call(port, `/cart/${sid}/${act}`, "POST", { item });
  if (result) {
    console.log(`✅ Success: ${id} ${act} ${item}`);
    // Log một lần duy nhất sau khi API trả về, kèm vclock thực tế
    const vclock = result?.cart?.ItemList?.[item]?.vclock;
    if (act === "add") logAdd(id, item, vclock);
    else logRemove(id, item, vclock);
    // Ghi log replication fire-and-forget sang các peer
    NODES.filter((n) => n.id !== id).forEach((peer) => {
      logReplicate(id, peer.id, item);
    });
  } else {
    console.log(`⚠️ API failed for Node ${id}: Queuing operation`);
    addToQueue(id, port, sid, act, item);
    logError(id, `API unreachable — "${item}" queued for later sync`);
  }

  updateCountBadge();
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
  const result = await call(port, "/clear", "POST");
  if (result) logTombstone(id, "all");
  updateCountBadge();
  updateUI();
};



// ─── Event Listeners ──────────────────────────────────────────────

const bindNodeCard = (nodeId) => {
  const card = document.querySelector(SELECTORS.nodeCard(nodeId));
  if (!card) return;

  card.querySelector(SELECTORS.btnAdd).onclick = () => {
    const input = card.querySelector(SELECTORS.inputItem);
    if (input.value.trim()) {
      const n = NODES.find((x) => x.id === nodeId);
      doAction(nodeId, n.p, "add", input.value.trim());
      input.value = "";
    }
  };

  card.querySelector(".raw-data-toggle .btn-raw:not(.btn-clear-history)").onclick = () =>
    card.querySelector(SELECTORS.rawDataView).classList.toggle("hidden");
};

// Khởi tạo các bộ lắng nghe sự kiện
const initEventListeners = () => {
  NODES.forEach((n) => bindNodeCard(n.id));

  // Global Sync
  document.querySelector(SELECTORS.syncBtn).onclick = async (e) => {
    const btn = e.currentTarget;
    btn.innerHTML = '<i class="fa-solid fa-rotate fa-spin"></i> Syncing...';
    NODES.forEach((n) => (cache[n.id] = null));
    const onlineNodes = NODES.filter((n) => nodeStatus[n.id]);

    logInfo(`🔄 Global Sync triggered — ${onlineNodes.length} node(s) online`);
    updateCountBadge();

    await processQueue(onlineNodes.map((n) => n.id));
    const syncResults = await Promise.all(
      onlineNodes.map((n) => call(n.p, "/sync", "POST"))
    );

    // Log kết quả sync
    onlineNodes.forEach((n, i) => {
      const res = syncResults[i];
      if (res) {
        logSync(n.id, "peers");
        const sessions = res.db ? Object.keys(res.db) : [];
        sessions.forEach((sid) => {
          const cart  = res.db[sid];
          const items = Object.entries(cart.ItemList || {});
          if (items.length > 0) {
            logMerge(n.id, sid, {
              items:   items.length,
              active:  items.filter(([, v]) => v.status === "active").length,
              deleted: items.filter(([, v]) => v.status === "deleted").length,
            });
          }
        });
        updateCountBadge();
      } else {
        logError(n.id, "Sync failed — node may be unreachable");
        updateCountBadge();
      }
    });

    await updateUI();
    btn.innerHTML = '<i class="fa-solid fa-rotate"></i> Global Sync';
  };
}

// Khởi động Ứng dụng
initEventListeners();
setInterval(updateUI, CONFIG.UI_UPDATE_INTERVAL);
updateUI();
