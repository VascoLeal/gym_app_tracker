import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider, useAuth } from "./AuthContext";

const TOKEN_KEY = "voacs_access_token";
const ATHLETE = { id: 1, email: "a@example.com", created_at: "2026-01-01T00:00:00Z" };

// The server is awake for every test here, so each one is about /auth/me.
vi.mock("../api/serverStatus", () => ({
  waitForServer: vi.fn().mockResolvedValue(true),
}));

function Status() {
  const { athlete, isLoading, serverUnreachable } = useAuth();
  if (isLoading) return <p>loading</p>;
  if (serverUnreachable) return <p>unreachable</p>;
  return <p>{athlete ? "logged in" : "logged out"}</p>;
}

function renderWithAuthMeReturning(result: () => Promise<Response>) {
  vi.stubGlobal("fetch", vi.fn(result));
  render(
    <AuthProvider>
      <Status />
    </AuthProvider>
  );
}

function jsonResponse(status: number, body: unknown) {
  return new Response(JSON.stringify(body), { status });
}

describe("restoring a saved login on app start", () => {
  beforeEach(() => {
    localStorage.setItem(TOKEN_KEY, "saved-token");
  });

  afterEach(() => {
    cleanup();
    localStorage.clear();
    vi.unstubAllGlobals();
  });

  it("logs the athlete in when the token is valid", async () => {
    renderWithAuthMeReturning(async () => jsonResponse(200, ATHLETE));

    await waitFor(() => expect(screen.getByText("logged in")).toBeTruthy());
    expect(localStorage.getItem(TOKEN_KEY)).toBe("saved-token");
  });

  it("removes the token when the server rejects it", async () => {
    renderWithAuthMeReturning(async () => jsonResponse(401, { detail: "Invalid token" }));

    await waitFor(() => expect(screen.getByText("logged out")).toBeTruthy());
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
  });

  it("keeps the token when the network fails", async () => {
    renderWithAuthMeReturning(async () => {
      throw new TypeError("Failed to fetch");
    });

    await waitFor(() => expect(screen.getByText("unreachable")).toBeTruthy());
    expect(localStorage.getItem(TOKEN_KEY)).toBe("saved-token");
  });

  it("keeps the token when the server has an error", async () => {
    renderWithAuthMeReturning(async () => jsonResponse(503, {}));

    await waitFor(() => expect(screen.getByText("unreachable")).toBeTruthy());
    expect(localStorage.getItem(TOKEN_KEY)).toBe("saved-token");
  });
});
