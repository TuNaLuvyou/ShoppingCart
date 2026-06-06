// CRDT Shopping Cart - Activity Logger Module

const MAX_ENTRIES = 200;
const entries = [];
let listEl = null;
let isPaused = false;
let filterLevel = "all";

const ICONS = {
  add:        { icon: "fa-plus-circle",          color: "#34d399", label: "ADD" },
  remove:     { icon: "fa-trash",                color: "#f87171", label: "DEL" },
  sync:       { icon: "fa-rotate",               color: "#60a5fa", label: "SYNC" },
  merge:      { icon: "fa-code-merge",           color: "#a78bfa", label: "MERGE" },
  replicate:  { icon: "fa-paper-plane",          color: "#fbbf24", label: "REP" },
  offline:    { icon: "fa-plug-circle-xmark",    color: "#f87171", label: "OFFLINE" },
  online:     { icon: "fa-plug-circle-check",    color: "#34d399", label: "ONLINE" },
  queue:      { icon: "fa-clock-rotate-left",    color: "#fdba74", label: "QUEUE" },
  version:    { icon: "fa-tag",                  color: "#c4b5fd", label: "VER" },
  conflict:   { icon: "fa-triangle-exclamation", color: "#fb923c", label: "CONFLICT" },
  tombstone:  { icon: "fa-broom",                color: "#94a3b8", label: "CLEAN" },
  info:       { icon: "fa-circle-info",          color: "#7dd3fc", label: "INFO" },
  error:      { icon: "fa-circle-xmark",         color: "#f87171", label: "ERR" },
  diverge:    { icon: "fa-code-branch",          color: "#fb923c", label: "DIVERGE" },
};

const ts = () => {
  const d = new Date();
  return `${String(d.getHours()).padStart(2,"0")}:${String(d.getMinutes()).padStart(2,"0")}:${String(d.getSeconds()).padStart(2,"0")}.${String(d.getMilliseconds()).padStart(3,"0")}`;
};

const NODE_COLORS = { A:"#60a5fa", B:"#a78bfa", C:"#34d399", D:"#fbbf24", E:"#f472b6", F:"#fb923c" };
const nodeColor = (id) => NODE_COLORS[id] || "#94a3b8";

export const log = (type, node, msg, detail = null) => {
  const meta  = ICONS[type] || ICONS.info;
  const entry = { id: Date.now() + Math.random(), ts: ts(), type, node, msg, detail, meta };
  entries.unshift(entry);
  if (entries.length > MAX_ENTRIES) entries.pop();
  if (!isPaused) renderEntry(entry, true);
};

// ─── Shorthand helpers ────────────────────────────────────────────
export const logAdd       = (node, item, vclock)     => log("add",       node, `"${item}" added to Node ${node}`, vclock ? { vclock } : null);
export const logRemove    = (node, item, vclock)     => log("remove",    node, `"${item}" removed from Node ${node}`, vclock ? { vclock } : null);
export const logOffline   = (node)                   => log("offline",   node, `Node ${node} went OFFLINE — operations queued`);
export const logOnline    = (node)                   => log("online",    node, `Node ${node} back ONLINE`);
export const logQueue     = (node, action, item)     => log("queue",     node, `[Offline] Queued ${action} "${item}" → Node ${node}`);
export const logSync      = (nodeA, nodeB)           => log("sync",      nodeA, `Anti-Entropy SYNC: Node ${nodeA} ↔ ${nodeB}`);
export const logMerge     = (node, session, result)  => log("merge",     node, `CRDT Merge @ Node ${node} — session: ${session}`, result);
export const logReplicate = (from, to, item)         => log("replicate", from, `Replication: Node ${from} → Node ${to}${item ? ` ("${item}")` : ""}`);
export const logVersion   = (node, ver, prev)        => log("version",   node, `Node ${node}: v${prev} → v${ver}`);
export const logTombstone = (node, count)            => log("tombstone", node, `Cleaned ${count} tombstone(s) from Node ${node}`);
export const logConflict  = (node, item, res)        => log("conflict",  node, `Conflict "${item}" → resolved: ${res}`);
export const logInfo      = (msg)                    => log("info",      "",   msg);
export const logError     = (node, msg)              => log("error",     node, `Error Node ${node}: ${msg}`);

// ─── Render single entry (Tailwind) ───────────────────────────────
const renderEntry = (entry, prepend = false) => {
  if (!listEl) return;
  if (filterLevel !== "all" && entry.type !== filterLevel) return;

  const c = nodeColor(entry.node);
  const nodeTag = entry.node
    ? `<span class="text-[0.62rem] font-bold px-1.5 py-0.5 rounded-full border" style="background:${c}18;color:${c};border-color:${c}44;">Node ${entry.node}</span>`
    : `<span class="text-[0.62rem] font-bold px-1.5 py-0.5 rounded-full border border-slate-700 bg-slate-800 text-slate-400">SYS</span>`;

  const detailStr = entry.detail
    ? `<div class="mt-1 font-mono text-[0.65rem] text-slate-500 bg-black/30 px-2 py-1 rounded break-all">${JSON.stringify(entry.detail)}</div>`
    : "";

  const el = document.createElement("div");
  el.className = `log-${entry.type} border-l-2 border-transparent bg-black/25 border border-white/[0.05] rounded-lg px-3 py-2 anim-fade-entry hover:bg-white/[0.04] transition-all`;
  el.dataset.id = entry.id;
  el.innerHTML = `
    <div class="flex items-center gap-1.5 flex-wrap mb-1">
      <span class="font-mono text-[0.62rem] text-slate-600">${entry.ts}</span>
      ${nodeTag}
      <span class="ml-auto text-[0.62rem] font-bold flex items-center gap-1" style="color:${entry.meta.color}">
        <i class="fa-solid ${entry.meta.icon}"></i>${entry.meta.label}
      </span>
    </div>
    <div class="text-slate-300 text-xs leading-relaxed">${entry.msg}</div>
    ${detailStr}`;

  if (prepend && listEl.firstChild) listEl.insertBefore(el, listEl.firstChild);
  else listEl.appendChild(el);

  if (!isPaused) listEl.scrollTop = 0;
  while (listEl.children.length > MAX_ENTRIES) listEl.removeChild(listEl.lastChild);
};

const rebuildList = () => {
  if (!listEl) return;
  listEl.innerHTML = "";
  const filtered = filterLevel === "all" ? entries : entries.filter((e) => e.type === filterLevel);
  filtered.forEach((e) => renderEntry(e, false));
};

// ─── Build Panel DOM (Tailwind) ───────────────────────────────────
export const buildLogPanel = () => {
  const panel = document.createElement("div");
  panel.id = "activity-log-panel";
  panel.className = "bg-slate-800/70 backdrop-blur-xl border border-white/10 rounded-2xl overflow-hidden shadow-xl flex flex-col h-[750px]";
  panel.innerHTML = `
    <!-- Panel header -->
    <div class="px-4 py-3 bg-white/[0.03] border-b border-white/10 flex-shrink-0">
      <div class="flex justify-between items-center mb-2">
        <h2 class="text-base font-semibold flex items-center gap-2">
          <i class="fa-solid fa-terminal"></i> Activity Log
          <span id="log-count-badge" class="text-xs font-semibold px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-300">0</span>
        </h2>
        <div class="flex items-center gap-2">
          <div id="log-live-dot" class="w-2.5 h-2.5 rounded-full bg-emerald-500 dot-glow"></div>
          <span id="log-live-text" class="text-sm text-slate-400">Live</span>
        </div>
      </div>
      <!-- Toolbar -->
      <div class="flex justify-between items-center gap-2">
        <div class="flex gap-1 flex-wrap" id="log-filters">
          <button data-filter="all"      class="log-filter-btn active-filter text-[0.7rem] font-semibold px-2 py-0.5 rounded-full border border-blue-500/50 bg-blue-500/20 text-blue-300 cursor-pointer transition-all">All</button>
          <button data-filter="add"      class="log-filter-btn text-[0.7rem] font-semibold px-2 py-0.5 rounded-full border border-white/10 text-slate-400 hover:border-blue-400 hover:text-blue-300 cursor-pointer transition-all">Add</button>
          <button data-filter="remove"   class="log-filter-btn text-[0.7rem] font-semibold px-2 py-0.5 rounded-full border border-white/10 text-slate-400 hover:border-blue-400 hover:text-blue-300 cursor-pointer transition-all">Del</button>
          <button data-filter="sync"     class="log-filter-btn text-[0.7rem] font-semibold px-2 py-0.5 rounded-full border border-white/10 text-slate-400 hover:border-blue-400 hover:text-blue-300 cursor-pointer transition-all">Sync</button>
          <button data-filter="merge"    class="log-filter-btn text-[0.7rem] font-semibold px-2 py-0.5 rounded-full border border-white/10 text-slate-400 hover:border-blue-400 hover:text-blue-300 cursor-pointer transition-all">Merge</button>
          <button data-filter="offline"  class="log-filter-btn text-[0.7rem] font-semibold px-2 py-0.5 rounded-full border border-white/10 text-slate-400 hover:border-blue-400 hover:text-blue-300 cursor-pointer transition-all">Net</button>
        </div>
        <div class="flex gap-1 flex-shrink-0">
          <button id="log-pause-btn" class="text-slate-400 hover:text-white border border-white/10 hover:bg-white/10 w-7 h-7 rounded-lg flex items-center justify-center transition-all text-xs" title="Pause/Resume">
            <i class="fa-solid fa-pause"></i>
          </button>
          <button id="log-clear-btn" class="text-slate-400 hover:text-red-400 border border-white/10 hover:border-red-400/40 hover:bg-red-400/10 w-7 h-7 rounded-lg flex items-center justify-center transition-all text-xs" title="Clear">
            <i class="fa-solid fa-trash"></i>
          </button>
        </div>
      </div>
    </div>

    <!-- Log list -->
    <div class="flex-1 relative overflow-hidden">
      <div id="log-list" class="absolute inset-0 overflow-y-auto px-3 py-3 flex flex-col gap-1.5 scrollbar-slim"></div>
      <div id="log-paused-overlay" class="hidden absolute inset-0 bg-slate-950/75 backdrop-blur-sm flex items-center justify-center text-slate-400 gap-2 cursor-pointer z-10">
        <i class="fa-solid fa-pause"></i> Paused — click Resume
      </div>
    </div>

    <!-- Footer -->
    <div class="px-4 py-2 border-t border-white/10 bg-black/15 flex-shrink-0">
      <span class="text-[0.7rem] text-slate-500 flex items-center gap-1.5">
        <i class="fa-solid fa-circle-info text-blue-500/60"></i> Real-time CRDT event stream
      </span>
    </div>`;

  document.getElementById("dashboard").appendChild(panel);
  listEl = document.getElementById("log-list");

  // Filter buttons
  panel.querySelectorAll(".log-filter-btn").forEach((btn) => {
    btn.onclick = () => {
      panel.querySelectorAll(".log-filter-btn").forEach((b) => {
        b.className = "log-filter-btn text-[0.7rem] font-semibold px-2 py-0.5 rounded-full border border-white/10 text-slate-400 hover:border-blue-400 hover:text-blue-300 cursor-pointer transition-all";
      });
      btn.className = "log-filter-btn active-filter text-[0.7rem] font-semibold px-2 py-0.5 rounded-full border border-blue-500/50 bg-blue-500/20 text-blue-300 cursor-pointer transition-all";
      filterLevel = btn.dataset.filter;
      rebuildList();
    };
  });

  // Pause/Resume
  const pauseBtn = document.getElementById("log-pause-btn");
  const overlay  = document.getElementById("log-paused-overlay");
  const liveDot  = document.getElementById("log-live-dot");
  const liveText = document.getElementById("log-live-text");

  pauseBtn.onclick = () => {
    isPaused = !isPaused;
    pauseBtn.innerHTML = isPaused ? '<i class="fa-solid fa-play"></i>' : '<i class="fa-solid fa-pause"></i>';
    overlay.classList.toggle("hidden", !isPaused);
    liveDot.className = isPaused
      ? "w-2.5 h-2.5 rounded-full bg-red-500"
      : "w-2.5 h-2.5 rounded-full bg-emerald-500 dot-glow";
    liveText.textContent = isPaused ? "Paused" : "Live";
    if (!isPaused) rebuildList();
  };

  // Clear
  document.getElementById("log-clear-btn").onclick = () => {
    entries.length = 0;
    listEl.innerHTML = "";
    updateCountBadge();
  };

  logInfo("🚀 CRDT Shopping Cart started — Phone (5001) & Laptop (5002)");
  logInfo("💡 Tip: Add items on both nodes simultaneously → see Divergent Cart → CRDT Merge!");
};

export const updateCountBadge = () => {
  const el = document.getElementById("log-count-badge");
  if (el) el.textContent = entries.length;
};
