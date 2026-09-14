import { useState } from "react";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";
import { HomePage } from "./pages/HomePage";
import { WorkoutPage } from "./pages/WorkoutPage";
import "./App.css";

// The actual screen-switching logic lives in its own component, separate
// from <App>, specifically so it can call useAuth() — that hook only
// works INSIDE an <AuthProvider>, and App is what renders the provider.
function AppContent() {
  const { athlete, isLoading } = useAuth();
  // No router yet (react-router) — still just plain state to flip between
  // screens. Four screens (login/register/home/workout) is arguably the
  // point where a router starts paying for itself; revisit if a fifth
  // screen gets added.
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [activeSessionId, setActiveSessionId] = useState<number | null>(null);

  if (isLoading) {
    // Shown briefly on app start while we check localStorage for a saved
    // token and verify it's still valid against the backend.
    return <div className="loading-screen">Loading…</div>;
  }

  if (athlete) {
    if (activeSessionId !== null) {
      return (
        <WorkoutPage
          sessionId={activeSessionId}
          onExit={() => setActiveSessionId(null)}
        />
      );
    }
    return <HomePage onOpenSession={setActiveSessionId} />;
  }

  return authMode === "login" ? (
    <LoginPage onSwitchToRegister={() => setAuthMode("register")} />
  ) : (
    <RegisterPage onSwitchToLogin={() => setAuthMode("login")} />
  );
}

function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}

export default App;
