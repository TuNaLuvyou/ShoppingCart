// CRDT Shopping Cart - UI Rendering Module

import { NODES, SELECTORS, cache, nodeStatus } from "./constants.js";
import { getQueue, getLocalCart, saveLocalCart, getDefaultCart, getSessionId } from "./storage.js";
import { call } from "./api.js";
import { getIsUpdating, setIsUpdating } from "./state.js";
import { logOnline, logOffline, logVersion, updateCountBadge } from "./logger.js";

const _prevStatus  = {};
const _prevVersion = {};

// ─── Item HTML (Tailwind) ─────────────────────────────────────────
export const renderItemHTML = (name, info, nodeId, nodePort) => {
  const isActive  = info.status === "active";
  const vclockStr = JSON.stringify(info.vclock || {}).replace(/"/g, "");
  const pendingBadge = info.isPending
    ? `<span class="text-[0.6rem] font-bold px-1.5 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/40 anim-pulse">Pending</span>`
    : "";
  const statusBadge = isActive
    ? `<span class="text-[0.65rem] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400">active</span>`
    : `<span class="text-[0.65rem] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-red-500/15 text-red-400 line-through">deleted</span>`;
  const removeBtn = isActive
    ? `<button onclick="doAction('${nodeId}',${nodePort},'remove','${name}')" class="text-slate-500 hover:text-red-400 transition-colors ml-1"><i class="fa-solid fa-trash text-xs"></i></button>`
    : "";
  return `
    <div class="bg-black/20 border border-white/5 rounded-lg px-4 py-3 transition-all hover:border-white/20 anim-fade-in ${!isActive ? "opacity-50" : ""}">
      <div class="flex justify-between items-center mb-1">
        <span class="font-semibold text-sm ${!isActive ? "line-through text-slate-400" : ""}">${name}</span>
        <div class="flex items-center gap-1.5">
          ${pendingBadge}${statusBadge}${removeBtn}
        </div>
      </div>
      <div class="text-xs text-slate-500 flex items-center gap-1.5">
        <i class="fa-regular fa-clock"></i>
        <span class="font-mono bg-black/30 px-1.5 py-0.5 rounded text-[0.68rem]">${vclockStr}</span>
      </div>
    </div>`;
};

// ─── Update UI ────────────────────────────────────────────────────
export const updateUI = async () => {
  if (getIsUpdating()) return;
  setIsUpdating(true);
  try {
    const sid = getSessionId();
    const results = await Promise.all(
      NODES.map(async (n) => ({ n, data: await call(n.p, `/cart/${sid}`) }))
    );

    for (const { n, data } of results) {
      const card = document.querySelector(SELECTORS.nodeCard(n.id));
      if (!card) continue;

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
      if (displayData?.raw_data) {
        displayData.raw_data.items = displayData.raw_data.items || {};
        for (const op of nodePendingOps) {
          const cur = displayData.raw_data.items[op.item] || { status: "active", vclock: {} };
          displayData.raw_data.items[op.item] = { ...cur, status: op.action === "add" ? "active" : "deleted", isPending: true };
        }
      }

      const stateStr = JSON.stringify({ isOnline, displayData, pendingOpsCount: nodePendingOps.length });
      if (stateStr === cache[n.id]) continue;
      cache[n.id] = stateStr;

      // ── Offline class ──
      card.classList.toggle("node-offline", !isOnline);

      // ── Status indicator ──
      const indicator = card.querySelector(SELECTORS.indicator);
      if (isOnline) {
        indicator.innerHTML = `<div class="dot w-2.5 h-2.5 rounded-full bg-emerald-500 dot-glow"></div><span class="status-text text-sm">Online</span>`;
      } else {
        indicator.innerHTML = `<div class="dot w-2.5 h-2.5 rounded-full bg-red-500"></div><span class="status-text text-sm">Offline</span>`;
      }

      // ── Log changes ──
      if (_prevStatus[n.id] !== undefined && _prevStatus[n.id] !== isOnline) {
        isOnline ? logOnline(n.id) : logOffline(n.id);
        updateCountBadge();
      }
      _prevStatus[n.id] = isOnline;

      // ── Meta row ──
      const items   = displayData.raw_data?.items || {};
      const active  = Object.values(items).filter((i) => i.status === "active").length;
      const version = displayData.version ?? displayData.raw_data?.version ?? 0;

      if (_prevVersion[n.id] !== undefined && _prevVersion[n.id] !== version) {
        logVersion(n.id, version, _prevVersion[n.id]);
        updateCountBadge();
      }
      _prevVersion[n.id] = version;

      const syncBadge = nodePendingOps.length > 0
        ? `<span class="text-xs font-semibold px-2 py-0.5 rounded-full ${isOnline ? "bg-blue-500/20 text-blue-300" : "bg-amber-500/20 text-amber-300 anim-pulse"}">${isOnline ? `↻ ${nodePendingOps.length}` : `${nodePendingOps.length} pending`}</span>`
        : "";
      card.querySelector(SELECTORS.metaRow).innerHTML = `
        <span class="text-xs font-semibold px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-300">${active} items</span>
        <span class="text-xs font-semibold px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">v${version}</span>
        ${syncBadge}`;

      // ── Cart items ──
      const itemsHTML = Object.entries(items)
        .map(([name, info]) => renderItemHTML(name, info, n.id, n.p))
        .join("") ||
        (isOnline
          ? `<div class="text-slate-500 text-center py-8 text-sm">Giỏ hàng trống</div>`
          : `<div class="text-slate-500 text-center py-8 text-sm"><i class="fa-solid fa-plug-circle-xmark mb-2 block text-xl"></i>Giỏ hàng trống (Offline)</div>`);
      card.querySelector(SELECTORS.cartItems).innerHTML = itemsHTML;

      card.querySelector(SELECTORS.rawDataView).innerText = JSON.stringify(displayData.raw_data, null, 2);
    }
  } finally {
    setIsUpdating(false);
  }
};

// ─── Dynamic Node Renderer (Tailwind) ─────────────────────────────
export const addDynamicNode = (nodeId, port, label, icon) => {
  const dashboard = document.getElementById("dashboard");
  const logPanel  = document.getElementById("activity-log-panel");
  const card = document.createElement("div");
  card.className = "bg-slate-800/70 backdrop-blur-xl border border-white/10 rounded-2xl overflow-hidden shadow-xl flex flex-col h-[750px] transition-all duration-300";
  card.id = `card-node-${nodeId}`;
  card.dataset.node = nodeId;
  card.dataset.port = port;
  card.innerHTML = `
    <div class="px-4 py-3 bg-white/[0.03] border-b border-white/10 flex flex-col gap-2 flex-shrink-0">
      <div class="flex justify-between items-center">
        <h2 class="text-base font-semibold flex items-center gap-2">
          <i class="fa-solid ${icon}"></i> ${label}
          <span class="text-xs font-semibold px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-300">${port}</span>
          <span class="text-[0.6rem] font-bold px-2 py-0.5 rounded-full bg-gradient-to-r from-violet-500/30 to-pink-500/30 text-violet-200 border border-violet-500/40 tracking-widest">SCALE</span>
        </h2>
        <div class="status-indicator flex items-center gap-2">
          <div class="dot w-2.5 h-2.5 rounded-full bg-red-500"></div>
          <span class="status-text text-sm">Offline</span>
        </div>
      </div>
      <div class="node-meta-row flex flex-wrap gap-2 items-center"></div>
    </div>
    <div class="p-5 flex-1 flex flex-col overflow-hidden">
      <div class="add-item-form flex gap-2 mb-4 flex-shrink-0">
        <input type="text" class="input-item flex-1 bg-slate-900/80 border border-white/10 text-slate-100 px-3 py-2 rounded-lg outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all text-sm" placeholder="Nhập tên sản phẩm..." />
        <button class="btn-add bg-white/10 hover:bg-blue-500 text-white px-3 py-2 rounded-lg font-semibold transition-all duration-200">
          <i class="fa-solid fa-plus"></i>
        </button>
      </div>
      <div class="cart-items flex flex-col gap-3 flex-1 overflow-y-auto pr-1 mb-3 scrollbar-slim"></div>
      <div class="raw-data-toggle flex-shrink-0 pt-3 border-t border-white/5 flex justify-center gap-2">
        <button onclick="clearHistory('${nodeId}',${port})" class="btn-clear-history text-amber-400 border border-amber-400/40 hover:bg-amber-400/10 text-xs px-3 py-1.5 rounded-lg transition-all flex items-center gap-1.5">
          <i class="fa-solid fa-broom"></i> Clean Tombstones
        </button>
        <button class="btn-raw text-slate-400 border border-white/10 hover:bg-white/5 hover:text-white text-xs px-3 py-1.5 rounded-lg transition-all flex items-center gap-1.5">
          <i class="fa-solid fa-code"></i> Raw Data
        </button>
      </div>
      <pre class="raw-data-view hidden mt-3 bg-black/50 p-4 rounded-lg text-xs overflow-x-auto text-violet-400 font-mono"></pre>
    </div>`;
  dashboard.insertBefore(card, logPanel);
};
