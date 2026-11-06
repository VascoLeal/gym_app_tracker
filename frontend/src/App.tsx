import type { ReactNode } from "react";
import { BrowserRouter, Navigate, Routes, Route, useNavigate, useParams } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { ConnectingScreen } from "./components/ConnectingScreen";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";
import { HomePage } from "./pages/HomePage";
import { WorkoutPage } from "./pages/WorkoutPage";
import { MesocycleBuilderPage } from "./pages/MesocycleBuilderPage";
import { ExerciseLibraryPage } from "./pages/ExerciseLibraryPage";
import "./App.css";

// Added with the mesocycle builder milestone: that screen has enough of its
// own sub-navigation (settings / templates / prescriptions) that hand-rolled
// state-passing (the pre-router approach) would get tangled fast — this is
// the "fifth screen" the previous milestone's comment flagged as the point
// a router starts paying for itself.

function RequireAuth({ children }: { children: ReactNode }) {
  const { athlete, isLoading } = useAuth();
  if (isLoading) return <div className="loading-screen">Loading…</div>;
  if (!athlete) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function RedirectIfAuthed({ children }: { children: ReactNode }) {
  const { athlete, isLoading } = useAuth();
  if (isLoading) return <div className="loading-screen">Loading…</div>;
  if (athlete) return <Navigate to="/home" replace />;
  return <>{children}</>;
}

function LoginRoute() {
  const navigate = useNavigate();
  return <LoginPage onSwitchToRegister={() => navigate("/register")} />;
}

function RegisterRoute() {
  const navigate = useNavigate();
  return <RegisterPage onSwitchToLogin={() => navigate("/login")} />;
}

function HomeRoute() {
  const navigate = useNavigate();
  return (
    <HomePage
      onOpenSession={(sessionId) => navigate(`/workout/${sessionId}`)}
      onCreateMesocycle={() => navigate("/mesocycles/new")}
      onEditMesocycle={(mesocycleId) => navigate(`/mesocycles/${mesocycleId}/edit`)}
      onOpenExerciseLibrary={() => navigate("/exercise-library")}
    />
  );
}

function ExerciseLibraryRoute() {
  const navigate = useNavigate();
  return <ExerciseLibraryPage onDone={() => navigate("/home")} />;
}

function WorkoutRoute() {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  return <WorkoutPage sessionId={Number(sessionId)} onExit={() => navigate("/home")} />;
}

function MesocycleBuilderRoute() {
  const { mesocycleId } = useParams();
  const navigate = useNavigate();
  return (
    <MesocycleBuilderPage
      mesocycleId={mesocycleId ? Number(mesocycleId) : null}
      onDone={() => navigate("/home")}
    />
  );
}

function AppContent() {
  const { isLoading, serverUnreachable, retryConnection } = useAuth();
  if (isLoading) {
    // Shown on app start while the server wakes and any saved token is checked.
    return <ConnectingScreen />;
  }

  if (serverUnreachable) {
    return (
      <div className="loading-screen">
        <p>Can't reach the server. Check your connection and try again.</p>
        <button type="button" onClick={retryConnection}>
          Try again
        </button>
      </div>
    );
  }

  return (
    <Routes>
      <Route
        path="/login"
        element={
          <RedirectIfAuthed>
            <LoginRoute />
          </RedirectIfAuthed>
        }
      />
      <Route
        path="/register"
        element={
          <RedirectIfAuthed>
            <RegisterRoute />
          </RedirectIfAuthed>
        }
      />
      <Route
        path="/home"
        element={
          <RequireAuth>
            <HomeRoute />
          </RequireAuth>
        }
      />
      <Route
        path="/workout/:sessionId"
        element={
          <RequireAuth>
            <WorkoutRoute />
          </RequireAuth>
        }
      />
      <Route
        path="/mesocycles/new"
        element={
          <RequireAuth>
            <MesocycleBuilderRoute />
          </RequireAuth>
        }
      />
      <Route
        path="/mesocycles/:mesocycleId/edit"
        element={
          <RequireAuth>
            <MesocycleBuilderRoute />
          </RequireAuth>
        }
      />
      <Route
        path="/exercise-library"
        element={
          <RequireAuth>
            <ExerciseLibraryRoute />
          </RequireAuth>
        }
      />
      <Route path="*" element={<Navigate to="/home" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
