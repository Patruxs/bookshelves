import { useCallback, useEffect, useState } from "react";

export const STORAGE_KEYS = {
  theme: "theme",
  recent: "recentIds",
  view: "browseView"
} as const;

export function readStorage<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    if (raw === null) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

export function writeStorage<T>(key: string, value: T): void {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    return;
  }
}

export function useStoredState<T>(key: string, fallback: T): [T, (next: T | ((current: T) => T)) => void] {
  const [value, setValue] = useState<T>(() => readStorage(key, fallback));
  useEffect(() => {
    writeStorage(key, value);
  }, [key, value]);
  const update = useCallback((next: T | ((current: T) => T)) => {
    setValue(current => (typeof next === "function" ? (next as (current: T) => T)(current) : next));
  }, []);
  return [value, update];
}
