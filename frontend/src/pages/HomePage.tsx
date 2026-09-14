import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { ApiError } from "../api/client";
import { listMyMesocycles, type Mesocycle } from "../api/mesocycles";
import { startSession } from "../api/sessions";

export function HomePage({ onOpenSession }: { onOpenSession: (sessionId: number) => void }) {
  const { athlete, token, logout } = useAuth();
  const [mesocycles, setMesocycles] = useState<Mesocycle[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isStarting, setIsStarting] = useState(false);

  // Re-fetched on mount only — there's no "pull to refresh" yet, and the
  // workout screen is where session state actually changes, not here.
  useEffect(() => {
    if (!token) return;
    listMyMesocycles(token)
      .then(setMesocycles)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Something went wrong."));
  }, [token]);

  async function handleStart(mesocycle: Mesocycle) {
    if (!token) return;
    setError(null);
    setIsStarting(true);
    try {
      const session = await startSession(mesocycle.id, token);
      onOpenSession(session.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setIsStarting(false);
    }
  }

  if (mesocycles === null && !error) {
    return (
      <div className="home-screen">
        <h1>voacs</h1>
        <p>Loading…</p>
      </div>
    );
  }

  const active = mesocycles?.find((m) => m.status === "active") ?? null;

  return (
    <div className="home-screen">
      <h1>voacs</h1>
      <p className="home-subtitle">{athlete?.email}</p>

      {error && <p className="auth-error">{error}</p>}

      {active ? (
        <div className="mesocycle-card">
          <h2>{active.name}</h2>
          <p>
            Week {active.current_week_number} of {active.number_of_weeks}
          </p>
          <button
            type="button"
            onClick={() =>
              active.in_progress_session_id
                ? onOpenSession(active.in_progress_session_id)
                : handleStart(active)
            }
            disabled={isStarting}
          >
            {active.in_progress_session_id
              ? "Continue Workout"
              : isStarting
                ? "Starting…"
                : "Start Workout"}
          </button>
        </div>
      ) : (
        mesocycles !== null && (
          <p>
            No active mesocycle. Create and start one via the API's{" "}
            <code>/docs</code> page for now — there's no in-app creation
            screen yet.
          </p>
        )
      )}

      <button type="button" className="link-button" onClick={logout}>
        Log out
      </button>
    </div>
  );
}
