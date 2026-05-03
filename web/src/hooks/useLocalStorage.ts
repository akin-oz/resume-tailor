import { useEffect, useState } from "react";

/**
 * Like useState, but persists to localStorage and rehydrates on mount.
 *
 * The serialized form lives at `key` as JSON. On parse failure (corrupt
 * data from a previous version, e.g.), we fall back to `initial` rather
 * than throwing — better UX than a crash on first load.
 */
export function useLocalStorage<T>(
  key: string,
  initial: T,
): [T, (value: T) => void] {
  const [value, setValue] = useState<T>(() => {
    try {
      const raw = window.localStorage.getItem(key);
      return raw ? (JSON.parse(raw) as T) : initial;
    } catch {
      return initial;
    }
  });

  useEffect(() => {
    try {
      window.localStorage.setItem(key, JSON.stringify(value));
    } catch {
      // Quota exceeded or private browsing — silent: state still works in-memory.
    }
  }, [key, value]);

  return [value, setValue];
}
