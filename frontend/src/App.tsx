import { useState } from "react";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";
import { HomePage } from "./pages/HomePage";
import "./App.css";

// The actual screen-switching logic lives in its own component, separate
// from <App>, specifically so it can call useAuth() — that hook only
// works INSIDE an <AuthProvider>, and App is what renders the provider.
function AppContent() {
  const { athlete, isLoading } = useAuth();
  // No router yet (react-router) — with just two auth screens, a plain
  // bit of state to flip between them is simpler than pulling in a
  // routing library this early. Worth revisiting once there are more
  // than a couple of screens to navigate between.
  const [authMode, setAuthMode] = useState<"login" | "register">("login");

  if (isLoading) {
    // Shown briefly on app start while we check localStorage for a saved
    // token and verify it's still valid against the backend.
    return <div className="loading-screen">Loading…</div>;
  }

  if (athlete) {
    return <HomePage />;
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
