// CRDT Shopping Cart - State Management Module

let isUpdating = false;

export const getIsUpdating = () => isUpdating;

export const setIsUpdating = (value) => {
  isUpdating = value;
};
