// CRDT Shopping Cart - Storage Module

import { CONFIG, SELECTORS } from "./constants.js";

export const getQueue = () => {
  try {
    return JSON.parse(localStorage.getItem(CONFIG.QUEUE_KEY)) || [];
  } catch {
    return [];
  }
};

export const saveQueue = (queue) => {
  localStorage.setItem(CONFIG.QUEUE_KEY, JSON.stringify(queue));
};

export const getLocalCart = (sessionId, nodeId) => {
  try {
    const key = `${CONFIG.CART_CACHE_KEY}${sessionId}_${nodeId}`;
    return JSON.parse(localStorage.getItem(key));
  } catch {
    return null;
  }
};

export const saveLocalCart = (sessionId, nodeId, data) => {
  const key = `${CONFIG.CART_CACHE_KEY}${sessionId}_${nodeId}`;
  localStorage.setItem(key, JSON.stringify(data));
};

export const addToQueue = (nodeId, port, sessionId, action, item) => {
  const queue = getQueue();
  queue.push({ nodeId, port, sessionId, action, item, timestamp: Date.now() });
  saveQueue(queue);
};

export const showToast = (message, duration = CONFIG.TOAST_DURATION) => {
  const toast = document.createElement("div");
  toast.className = "toast-notification";
  toast.innerHTML = message;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), duration);
};

export const getDefaultCart = (sessionId) => ({
  session_id: sessionId,
  version: 0,
  active_items: [],
  raw_data: { version: 0, items: {} },
});

export const getSessionId = () =>
  document.querySelector(SELECTORS.sessionInput).value || "user_dat_123";
