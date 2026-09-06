import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import {
  fetchCurrentAthlete,
  loginAthlete,
  registerAthlete,
  type Athlete,
} from "../api/auth";

const TOKEN_STORAGE_KEY = "voacs_access_token";

// This is the shape of data + functions any component can pull out of
// auth context via useAuth() below, without it having to be passed down
// as props through every level of the component tree ("prop drilling").
interface AuthContextValue {
  athlete: Athlete | null;
  token: string | null;
  isLoading: boolean; // true while we're checking a stored token on first load
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  // useState holds values that, when changed, make React re-render
  // whatever reads them — e.g. setting `athlete` here is what makes the
  // app switch from the login screen to the logged-in view.
  const [athlete, setAthlete] = useState<Athlete | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // useEffect with an empty dependency array ([]) runs ONCE, right after
  // the component first renders — the standard place to do "on app start"
  // work like checking for a previously-saved login.
  useEffect(() => {
    const storedToken = localStorage.getItem(TOKEN_STORAGE_KEY);
    if (!storedToken) {
      setIsLoading(false);
      return;
    }

    // A stored token might be expired or otherwise invalid (e.g. the
    // JWT_SECRET_KEY changed) — verify it against /auth/me rather than
    // trusting it blindly, so a stale token doesn't silently keep failing
    // every real API call later.
    fetchCurrentAthlete(storedToken)
      .then((fetchedAthlete) => {
        setToken(storedToken);
        setAthlete(fetchedAthlete);
      })
      .catch(() => {
        localStorage.removeItem(TOKEN_STORAGE_KEY);
      })
      .finally(() => setIsLoading(false));
  }, []);

  async function login(email: string, password: string) {
    const result = await loginAthlete(email, password);
    localStorage.setItem(TOKEN_STORAGE_KEY, result.access_token);
    setToken(result.access_token);
    setAthlete(result.athlete);
  }

  async function register(email: string, password: string) {
    await registerAthlete(email, password);
    // Registering doesn't log you in by itself (the backend's /register
    // deliberately just creates the account) — so immediately log in
    // right after, for a one-step signup experience.
    await login(email, password);
  }

  function logout() {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    setToken(null);
    setAthlete(null);
  }

  return (
    <AuthContext.Provider
      value={{ athlete, token, isLoading, login, register, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}

// A custom hook is just a function starting with "use" that calls other
// hooks — this one saves every component from importing useContext and
// AuthContext directly, and throws a clear error if someone forgets to
// wrap the app in <AuthProvider>.
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (context === null) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
