const STORAGE_KEY = "wealth-copilot-thread";
const nodeStorage = new Map();

function getStorage() {
  if (typeof window !== "undefined" && window.localStorage) return window.localStorage;

  return {
    getItem: (key) => nodeStorage.get(key) ?? null,
    setItem: (key, value) => {
      nodeStorage.set(key, String(value));
    },
    removeItem: (key) => {
      nodeStorage.delete(key);
    },
    clear: () => {
      nodeStorage.clear();
    },
    key: (index) => Array.from(nodeStorage.keys())[index] ?? null,
    get length() {
      return nodeStorage.size;
    },
  };
}

export function readStoredThread(key = STORAGE_KEY) {
  try {
    const raw = getStorage().getItem(key);
    if (!raw) return null;

    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return null;
    if (!Array.isArray(parsed.messages)) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function writeStoredThread(threadOrKey, maybeThread) {
  const key = typeof threadOrKey === "string" ? threadOrKey : STORAGE_KEY;
  const thread = typeof threadOrKey === "string" ? maybeThread : threadOrKey;

  try {
    if (!thread) return;
    getStorage().setItem(key, JSON.stringify(thread));
  } catch {
    // Storage can be unavailable; the in-memory flow still works.
  }
}

export function clearStoredThread(key = STORAGE_KEY) {
  try {
    getStorage().removeItem(key);
  } catch {
    // Ignore storage failures.
  }
}

export { STORAGE_KEY };