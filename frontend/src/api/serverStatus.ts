import { API_BASE_URL } from "./client";

// Render's free tier puts the backend to sleep after 15 idle minutes, and
// waking it takes about a minute. Requests made during that minute can fail
// or receive Render's own loading page, so only a real answer from /health
// counts as "up".
const REQUEST_TIMEOUT_MS = 20_000;

async function isServerUp(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE_URL}/health`, {
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    });
    if (!response.ok) return false;
    const body = await response.json();
    return body.status === "ok";
  } catch {
    return false;
  }
}

interface WaitOptions {
  check?: () => Promise<boolean>;
  timeoutMs?: number;
  intervalMs?: number;
}

/**
 * Keeps asking until the server answers, and resolves false if it hasn't by
 * the timeout. Used once on app start, so every screen after it can assume
 * the server is awake. Only /health is retried, never a real request:
 * repeating a write could log the same set twice.
 */
export async function waitForServer({
  check = isServerUp,
  timeoutMs = 90_000,
  intervalMs = 3_000,
}: WaitOptions = {}): Promise<boolean> {
  const deadline = Date.now() + timeoutMs;
  for (;;) {
    if (await check()) return true;
    if (Date.now() + intervalMs > deadline) return false;
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
}
