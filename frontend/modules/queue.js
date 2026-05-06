// CRDT Shopping Cart - Queue Processing Module

import { NODES } from "./constants.js";
import { getQueue, saveQueue } from "./storage.js";
import { call } from "./api.js";

export const processQueue = async (targetNodeIds = null) => {
  const queue = getQueue();
  const targetIds = targetNodeIds ? new Set(targetNodeIds) : null;
  const remainingQueue = [];

  for (const node of NODES) {
    if (targetIds && !targetIds.has(node.id)) {
      continue;
    }

    const nodeQueue = queue.filter((op) => op.nodeId === node.id);

    for (let index = 0; index < nodeQueue.length; index++) {
      const op = nodeQueue[index];
      const result = await call(
        op.port,
        `/cart/${op.sessionId}/${op.action}`,
        "POST",
        { item: op.item },
      );

      if (result) {
        console.log(`✅ Synced: ${op.nodeId} ${op.action} ${op.item}`);
      } else {
        remainingQueue.push(op, ...nodeQueue.slice(index + 1));
        break;
      }
    }
  }

  const untouchedQueue = targetIds
    ? queue.filter((op) => !targetIds.has(op.nodeId))
    : [];
  saveQueue([...untouchedQueue, ...remainingQueue]);
  return remainingQueue.length === 0;
};
