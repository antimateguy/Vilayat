"use client";

import { useEffect, useState } from "react";

/**
 * The value, but only after it has stopped changing for `delayMs`. Dragging a
 * slider then sends one request when the hand rests, not one per step.
 */
export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);

  return debounced;
}
