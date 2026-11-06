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
import { ApiError } from "../api/client";
import { waitForServer } from "../api/serverStatus";

const TOKEN_STORAGE_KEY = "voacs_access_token";

// This is the shape of data + functions any component can pull out of
// auth context via useAuth() below, without it having to be passed down
// as props through every level of the component tree ("prop drilling").
interface AuthContextValue {
  athlete: Athlete | null;
  token: string | null;
  isLoading: boolean; // true while waking the server and checking a stored token
  serverUnreachable: boolean; // the server never answered; any saved login is kept
  retryConnection: () => void;
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
  const [serverUnreachable, setServerUnreachable] = useState(false);
  const [connectionAttempt, setConnectionAttempt] = useState(0);

  // useEffect runs after the first render, and again whenever a value in its
  // dependency array changes — here, when "Try again" bumps connectionAttempt.
  // Its cleanup sets `cancelled`, so an outdated run can't overwrite state.
  useEffect(() => {
    let cancelled = false;

    async function connect() {
      const serverIsUp = await waitForServer();
      if (cancelled) return;
      if (!serverIsUp) {
        setServerUnreachable(true);
        setIsLoading(false);
        return;
      }

      const storedToken = localStorage.getItem(TOKEN_STORAGE_KEY);
      if (storedToken) {
        // A stored token might be expired or otherwise invalid (e.g. the
        // JWT_SECRET_KEY changed) — verify it against /auth/me rather than
        // trusting it blindly. Only a 401 means the token is bad. Any other
        // failure says nothing about it, so it must not log the athlete out.
        try {
          const fetchedAthlete = await fetchCurrentAthlete(storedToken);
          if (cancelled) return;
          setToken(storedToken);
          setAthlete(fetchedAthlete);
        } catch (err) {
          if (cancelled) return;
          if (err instanceof ApiError && err.status === 401) {
            localStorage.removeItem(TOKEN_STORAGE_KEY);
          } else {
            setServerUnreachable(true);
          }
        }
      }
      setIsLoading(false);
    }

    connect();
    return () => {
      cancelled = true;
    };
  }, [connectionAttempt]);

  function retryConnection() {
    setServerUnreachable(false);
    setIsLoading(true);
    setConnectionAttempt((attempt) => attempt + 1);
  }

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
      value={{
        athlete,
        token,
        isLoading,
        serverUnreachable,
        retryConnection,
        login,
        register,
        logout,
      }}
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
