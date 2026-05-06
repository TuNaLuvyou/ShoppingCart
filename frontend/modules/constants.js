// CRDT Shopping Cart - Constants Module

export const NODES = [
  { id: "A", p: 5001 },
  { id: "B", p: 5002 },
  { id: "C", p: 5003 },
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

// Global State
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
