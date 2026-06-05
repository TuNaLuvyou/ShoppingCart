// CRDT Shopping Cart - Module Hằng số

export const NODES = [
  { id: "A", p: 5001, label: "Smartphone" },
  { id: "B", p: 5002, label: "Computer" },
  { id: "C", p: 5003, label: "Tablet" },
  { id: "D", p: 5004, label: "New Node (Scale)" },
];

export const CONFIG = {
  QUEUE_KEY: "cart_pending_ops",
  CART_CACHE_KEY: "local_cart_",
  API_TIMEOUT: 1000,
  API_BASE: "http://localhost",
  UI_UPDATE_INTERVAL: 3000,
  TOAST_DURATION: 2000,
};

export const SELECTORS = {
  sessionInput: "#session-id",
  syncBtn: "#btn-sync-all",
  nodeCard: (id) => `#card-node-${id}`,
  cartItems: ".cart-items",
  indicator: ".status-indicator",
  metaRow: ".node-meta-row",
  rawDataView: ".raw-data-view",
  btnAdd: ".btn-add",
  inputItem: ".input-item",
};

// Trạng thái Toàn cục (Global State)
export const cache = {};
export const nodeStatus = NODES.reduce(
  (acc, n) => ({ ...acc, [n.id]: false }),
  {},
);
export let isUpdating = false;

export const setIsUpdating = (value) => {
  isUpdating = value;
};

export const getIsUpdating = () => isUpdating;
