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
    logQueue(id, act, item);
    logOffline(id);
    updateCountBadge();
    updateUI();
    return;
  }

  // Log before call
  if (act === "add") logAdd(id, item, null);
  else logRemove(id, item, null);
  updateCountBadge();

  const result = await call(port, `/cart/${sid}/${act}`, "POST", { item });
  if (result) {
    console.log(`✅ Success: ${id} ${act} ${item}`);
    // Log the resulting vclock if available
    const vclock = result?.cart?.items?.[item]?.vclock;
    if (act === "add") logAdd(id, item, vclock);
    else logRemove(id, item, vclock);
    // Try to log replication to peers (fire-and-forget indicator)
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

// ─── Dynamic Node (Horizontal Scaling Demo) ───────────────────────
let dynamicNodeCounter = 0;
const DYNAMIC_NODE_IDS = ["C", "D", "E", "F"];
const DYNAMIC_NODE_PORTS = [5003, 5004, 5005, 5006];
const DYNAMIC_NODE_ICONS = [
  "fa-tablet-screen-button",
  "fa-tv",
  "fa-desktop",
  "fa-server",
];

const initAddNodeModal = () => {
  const modal = document.getElementById("add-node-modal");
  const btnOpen = document.getElementById("btn-add-node");
  const btnClose = document.getElementById("btn-close-add-node");
  const btnConfirm = document.getElementById("btn-confirm-add-node");
  const nameInput = document.getElementById("new-node-name");

  btnOpen.onclick = () => {
    nameInput.value = "";
    modal.classList.remove("hidden");
    setTimeout(() => nameInput.focus(), 100);
  };

  btnClose.onclick = () => modal.classList.add("hidden");
  modal.onclick = (e) => { if (e.target === modal) modal.classList.add("hidden"); };

  nameInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") btnConfirm.click();
  });

  btnConfirm.onclick = () => {
    if (dynamicNodeCounter >= DYNAMIC_NODE_IDS.length) {
      showToast("Đã đạt giới hạn node demo!");
      modal.classList.add("hidden");
      return;
    }

    const label = nameInput.value.trim() || `Node ${DYNAMIC_NODE_IDS[dynamicNodeCounter]}`;
    const nodeId = DYNAMIC_NODE_IDS[dynamicNodeCounter];
    const port = DYNAMIC_NODE_PORTS[dynamicNodeCounter];
    const icon = DYNAMIC_NODE_ICONS[dynamicNodeCounter];
    dynamicNodeCounter++;

    // Register node globally
    NODES.push({ id: nodeId, p: port, label });
    nodeStatus[nodeId] = false;
    cache[nodeId] = null;

    // Render the new node card (inserted BEFORE the log panel)
    addDynamicNode(nodeId, port, label, icon);
    modal.classList.add("hidden");
    showToast(`✅ Đã thêm node "${label}" (port ${port}) — Horizontal Scaling!`);
    logInfo(`🆕 Horizontal Scaling: Node ${nodeId} "${label}" joined cluster on port ${port}`);
    updateCountBadge();

    bindNodeCard(nodeId);
    updateUI();
  };
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

// Khởi tạo các bộ lắng nghe sự kiện (Event Listeners)
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

    // Log sync results
    onlineNodes.forEach((n, i) => {
      const res = syncResults[i];
      if (res) {
        logSync(n.id, "peers");
        const sessions = res.db ? Object.keys(res.db) : [];
        sessions.forEach((sid) => {
          const cart = res.db[sid];
          const items = Object.entries(cart.items || {});
          if (items.length > 0) {
            logMerge(n.id, sid, {
              items: items.length,
              active: items.filter(([, v]) => v.status === "active").length,
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

  initAddNodeModal();
};

// Khởi động Ứng dụng
initEventListeners();
setInterval(updateUI, CONFIG.UI_UPDATE_INTERVAL);
updateUI();
