// CRDT Shopping Cart - UI Rendering Module

import { NODES, SELECTORS, cache, nodeStatus } from "./constants.js";
import {
  getQueue,
  getLocalCart,
  saveLocalCart,
  getDefaultCart,
  getSessionId,
} from "./storage.js";
import { call } from "./api.js";
import { getIsUpdating, setIsUpdating } from "./state.js";

export const renderItemHTML = (name, info, nodeId, nodePort) => {
  const isActive = info.status === "active";
  const vclockStr = JSON.stringify(info.vclock || {}).replace(/"/g, "");
  return `
    <div class="cart-item ${info.status === "deleted" ? "is-deleted" : ""}">
      <div class="item-main">
        <span class="item-name">${name}</span>
        <div style="display: flex; align-items: center; gap: 5px;">
          ${info.isPending ? `<span class="badge badge-pending" style="font-size: 0.6rem; padding: 0.1rem 0.3rem; animation: pulse-pending 2s infinite;">Pending</span>` : ""}
          <span class="badge status-badge ${info.status}">${info.status}</span>
          ${isActive ? `<button onclick="doAction('${nodeId}', ${nodePort}, 'remove', '${name}')" class="btn-remove"><i class="fa-solid fa-trash"></i></button>` : ""}
        </div>
      </div>
      <div class="item-meta"><i class="fa-regular fa-clock"></i> ${vclockStr}</div>
    </div>
  `;
};

export const updateUI = async () => {
  if (getIsUpdating()) return;
  setIsUpdating(true);

  try {
    const sid = getSessionId();

    const results = await Promise.all(
      NODES.map(async (n) => {
        const data = await call(n.p, `/cart/${sid}`);
        return { n, data };
      }),
    );

    for (const { n, data } of results) {
      const card = document.querySelector(SELECTORS.nodeCard(n.id));
      const isOnline = !!data;
      nodeStatus[n.id] = isOnline;

      let displayData = data;
      if (isOnline) {
        saveLocalCart(sid, n.id, data);
      } else {
        displayData = getLocalCart(sid, n.id) || getDefaultCart(sid);
      }

      const queue = getQueue();
      const nodePendingOps = queue.filter((op) => op.nodeId === n.id);
      const pendingOpsCount = nodePendingOps.length;

      if (displayData && displayData.raw_data) {
        displayData.raw_data.items = displayData.raw_data.items || {};
        for (const op of nodePendingOps) {
          const currentItem = displayData.raw_data.items[op.item] || {
            status: "active",
            vclock: {},
          };
          const status = op.action === "add" ? "active" : "deleted";
          displayData.raw_data.items[op.item] = {
            ...currentItem,
            status,
            isPending: true,
          };
        }
      }

      const stateStr = JSON.stringify({
        isOnline,
        displayData,
        pendingOpsCount,
      });
      if (stateStr === cache[n.id]) continue;
      cache[n.id] = stateStr;

      card.classList.toggle("offline", !isOnline);
      const indicator = card.querySelector(SELECTORS.indicator);
      const metaRow = card.querySelector(SELECTORS.metaRow);
      const itemsContainer = card.querySelector(SELECTORS.cartItems);

      const items = displayData.raw_data.items || {};
      const activeCount = Object.values(items).filter(
        (i) => i.status === "active",
      ).length;
      const version =
        displayData.version !== undefined
          ? displayData.version
          : displayData.raw_data?.version || 0;

      const statusDot = isOnline
        ? `<div class="dot online"></div><span class="status-text">Online</span>`
        : `<div class="dot offline"></div><span class="status-text">Offline</span>`;
      indicator.innerHTML = statusDot;

      const syncBadge =
        pendingOpsCount > 0
          ? `<span class="badge ${isOnline ? "badge-syncing" : "badge-pending"}">${isOnline ? `↻ ${pendingOpsCount}` : `${pendingOpsCount} pending`}</span>`
          : "";
      metaRow.innerHTML = `
        <span class="badge badge-port">${activeCount} items</span>
        <span class="badge badge-version">v${version}</span>
        ${syncBadge}
      `;

      const itemsHTML =
        Object.entries(items)
          .map(([name, info]) => renderItemHTML(name, info, n.id, n.p))
          .join("") ||
        (isOnline
          ? '<div style="color:var(--text-secondary); text-align:center; padding:1rem; font-size:0.85rem">Giỏ hàng trống</div>'
          : '<div style="color:var(--text-secondary); text-align:center; padding:1rem; font-size:0.85rem"><i class="fa-solid fa-plug-circle-xmark"></i> Giỏ hàng trống (Offline)</div>');
      itemsContainer.innerHTML = itemsHTML;

      card.querySelector(SELECTORS.rawDataView).innerText = JSON.stringify(
        displayData.raw_data,
        null,
        2,
      );
    }
  } finally {
    setIsUpdating(false);
  }
};
