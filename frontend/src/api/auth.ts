import { apiFetch } from "./client";

// These mirror the backend's Pydantic response schemas exactly — see
// app/api/schemas.py AthleteResponse / LoginResponse. Keeping them in sync
// by hand is a real limitation (nothing enforces it), but generating types
// from the OpenAPI schema is a nice-to-have for later, not needed yet.
export interface Athlete {
  id: number;
  email: string;
  created_at: string;
}

export interface LoginResult {
  access_token: string;
  token_type: string;
  athlete: Athlete;
}

export function registerAthlete(
  email: string,
  password: string
): Promise<Athlete> {
  return apiFetch<Athlete>("/auth/register", {
    method: "POST",
    body: { email, password },
  });
}

export function loginAthlete(
  email: string,
  password: string
): Promise<LoginResult> {
  return apiFetch<LoginResult>("/auth/login", {
    method: "POST",
    body: { email, password },
  });
}

export function fetchCurrentAthlete(token: string): Promise<Athlete> {
  return apiFetch<Athlete>("/auth/me", { token });
}
