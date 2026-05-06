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

// Initialize Event Listeners
const initEventListeners = () => {
  NODES.forEach((n) => {
    const card = document.querySelector(SELECTORS.nodeCard(n.id));

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

  document.querySelector(SELECTORS.syncBtn).onclick = async (e) => {
    const btn = e.currentTarget;
    btn.innerHTML = "Syncing...";
    NODES.forEach((n) => (cache[n.id] = null));
    const onlineNodes = NODES.filter((n) => nodeStatus[n.id]);
    await processQueue(onlineNodes.map((n) => n.id));
    await Promise.all(onlineNodes.map((n) => call(n.p, "/sync", "POST")));
    await updateUI();
    btn.innerHTML = "Global Sync";
  };
};

// Start Application
initEventListeners();
setInterval(updateUI, CONFIG.UI_UPDATE_INTERVAL);
updateUI();
