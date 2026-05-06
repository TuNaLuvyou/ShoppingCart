// CRDT Shopping Cart - API Module

import { CONFIG } from "./constants.js";

export const call = async (port, path, method = "GET", body = null) => {
  try {
    const res = await fetch(`${CONFIG.API_BASE}:${port}${path}`, {
      method,
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : null,
      signal: AbortSignal.timeout(CONFIG.API_TIMEOUT),
    });
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
};
