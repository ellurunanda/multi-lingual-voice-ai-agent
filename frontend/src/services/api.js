/**
 * Central API client.
 * Uses VITE_API_URL env var so the same build works locally (via Vite proxy)
 * and on Render Static Site (direct calls to the backend service URL).
 *
 * Local dev  : VITE_API_URL is empty → relative paths → Vite proxy handles it
 * Production : VITE_API_URL=https://voiceai-backend.onrender.com
 */

const BASE = import.meta.env.VITE_API_URL ?? "";

/**
 * Thin wrapper around fetch that prepends the base URL.
 * @param {string} path  - Must start with /api/...
 * @param {RequestInit} [init]
 */
export async function apiFetch(path, init) {
  const url = `${BASE}${path}`;
  const res = await fetch(url, init);
  return res;
}