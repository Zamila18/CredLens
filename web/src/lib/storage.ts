/**
 * Remembering small viewer choices (demo role, reason language) in the browser.
 * Storage can be blocked (private window), so every read and write is guarded and
 * the app works without it.
 */

/** Read a saved value; return the fallback when nothing valid is stored. */
export function readChoice<T extends string>(key: string, allowed: readonly T[], fallback: T): T {
  try {
    const value = window.localStorage.getItem(key)
    return value && (allowed as readonly string[]).includes(value) ? (value as T) : fallback
  } catch {
    return fallback
  }
}

/** Save a value; silently skip when storage is blocked. */
export function saveChoice(key: string, value: string) {
  try {
    window.localStorage.setItem(key, value)
  } catch {
    // Storage blocked: the choice lasts until the page reloads.
  }
}
