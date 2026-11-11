const key = "oi-pending-preparation-end";
export function pendingEnd(): string | null {
  try {
    const id = sessionStorage.getItem(key);
    return id && /^[A-Za-z0-9_-]{3,80}$/.test(id) ? id : null;
  } catch {
    return null;
  }
}
export function markPendingEnd(id: string) {
  try {
    sessionStorage.setItem(key, id);
  } catch {
    /* Backend still owns expiry; no media exists in preparation. */
  }
}
export function clearPendingEnd(id: string) {
  try {
    if (sessionStorage.getItem(key) === id) sessionStorage.removeItem(key);
  } catch {}
}
