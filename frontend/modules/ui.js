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
  let totalQty = 1;
  if (typeof info.quantity === 'object') {
      totalQty = Object.values(info.quantity).reduce((a, b) => a + b, 0);
  } else if (info.quantity !== undefined) {
      totalQty = info.quantity;
  }
  totalQty = Math.max(1, totalQty);

  return `
    <div class="cart-item ${info.status === "deleted" ? "is-deleted" : ""}">
      <div class="item-main">
        <span class="item-name">${name}</span>
        <div style="display: flex; align-items: center; gap: 5px;">
          ${info.isPending ? `<span class="badge badge-pending" style="font-size: 0.6rem; padding: 0.1rem 0.3rem; animation: pulse-pending 2s infinite;">Pending</span>` : ""}
          <span class="badge status-badge ${info.status}">${info.status}</span>
          ${isActive ? `
          <button onclick="doAction('${nodeId}', ${nodePort}, 'decrease', '${name}')" class="btn-qty" style="padding: 2px 6px; font-size: 0.8rem; cursor: pointer; border-radius: 4px; background: rgba(255, 255, 255, 0.1); border: 1px solid var(--border-color); color: white;">-</button>
          <span style="font-weight: bold; margin: 0 5px;">${totalQty}</span>
          <button onclick="doAction('${nodeId}', ${nodePort}, 'increase', '${name}')" class="btn-qty" style="padding: 2px 6px; font-size: 0.8rem; cursor: pointer; border-radius: 4px; background: rgba(255, 255, 255, 0.1); border: 1px solid var(--border-color); color: white;">+</button>
          <button onclick="doAction('${nodeId}', ${nodePort}, 'remove', '${name}')" class="btn-remove" style="margin-left: 5px;"><i class="fa-solid fa-trash"></i></button>
          ` : ""}
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
            quantity: {}
          };
          
          let status = currentItem.status;
          let qtyDict = currentItem.quantity;
          if (typeof qtyDict !== 'object') qtyDict = { [n.id]: qtyDict || 1 };
          
          let myQty = qtyDict[n.id] || 0;
          
          if (op.action === "add") {
             status = "active";
             myQty = currentItem.status === "deleted" ? 1 : myQty + 1;
          } else if (op.action === "increase") {
             status = "active";
             myQty += 1;
          } else if (op.action === "decrease") {
             status = "active";
             myQty -= 1;
          } else if (op.action === "remove") {
             status = "deleted";
             qtyDict = {};
          }
          
          if (op.action !== "remove") {
             qtyDict = { ...qtyDict, [n.id]: myQty };
          }
          
          displayData.raw_data.items[op.item] = {
            ...currentItem,
            status,
            quantity: qtyDict,
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
