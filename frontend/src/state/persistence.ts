/**
 * Thin localStorage wrapper for the stores in this directory. Wrapped
 * in try/catch on both sides -- private-browsing modes and
 * quota-exceeded conditions can make localStorage throw, and a
 * persistence failure should degrade to in-memory-only behavior, not
 * crash the app.
 */
export function readPersisted<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    if (raw === null) {
      return fallback;
    }
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

export function writePersisted<T>(key: string, value: T): void {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Storage unavailable or full -- silently degrade to in-memory-only.
  }
}

export function clearPersisted(key: string): void {
  try {
    localStorage.removeItem(key);
  } catch {
    // Storage unavailable -- nothing to clear.
  }
}
