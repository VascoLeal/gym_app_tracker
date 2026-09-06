// The backend's URL, read from the environment (see .env / .env.example).
// import.meta.env is Vite's equivalent of process.env — anything prefixed
// VITE_ gets baked into the browser bundle at build time.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

/**
 * A custom Error subclass so callers can check `error.status` to react
 * differently to, say, a 401 (bad credentials) vs a 409 (already exists)
 * vs a network failure, instead of parsing error.message strings.
 */
export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  token?: string | null;
}

/**
 * Every API call in this app goes through here. It handles:
 * - JSON serialization of the request body
 * - attaching the Authorization: Bearer header when a token is provided
 * - turning a non-2xx response into a thrown ApiError, so callers can just
 *   `try { await apiFetch(...) } catch (e) { ... }` instead of manually
 *   checking response.ok every single time.
 */
export async function apiFetch<T>(
  path: string,
  { method = "GET", body, token }: RequestOptions = {}
): Promise<T> {
  const headers: Record<string, string> = {};
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    // FastAPI's error responses look like: {"detail": "some message"}
    const errorBody = await response.json().catch(() => ({}));
    throw new ApiError(
      response.status,
      errorBody.detail ?? `Request failed with status ${response.status}`
    );
  }

  // 204 No Content responses have no body to parse.
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}
