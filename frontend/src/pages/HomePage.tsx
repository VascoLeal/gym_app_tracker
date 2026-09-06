import { useAuth } from "../auth/AuthContext";

export function HomePage() {
  const { athlete, logout } = useAuth();

  return (
    <div className="home-screen">
      <h1>voacs</h1>
      {/* If you're seeing your real email here, the whole loop worked:
          login issued a token -> it got stored -> it was sent back on
          the /auth/me call -> the backend verified it and returned you. */}
      <p>Logged in as {athlete?.email}</p>
      <button type="button" onClick={logout}>
        Log out
      </button>
    </div>
  );
}
