import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type PropsWithChildren,
} from "react";

import { authApi, isApiError } from "../api";
import type { ApiError, StaffSession } from "../api";

type AuthStatus = "loading" | "authenticated" | "unauthenticated";

type AuthContextValue = {
  status: AuthStatus;
  session: StaffSession | null;
  error: ApiError | null;
  isAuthenticated: boolean;
  login: (credentials: { email: string; password: string }) => Promise<StaffSession>;
  logout: () => Promise<void>;
  refreshSession: () => Promise<StaffSession | null>;
  clearError: () => void;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

function normalizeUnknownError(error: unknown): ApiError {
  if (isApiError(error)) {
    return error;
  }

  return {
    name: "ApiError",
    status: 0,
    code: "unknown",
    message: "We could not reach the server. Please try again.",
    details: error,
  };
}

export function AuthProvider({ children }: PropsWithChildren) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [session, setSession] = useState<StaffSession | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const didHydrateRef = useRef(false);

  const refreshSession = useCallback(async () => {
    setError(null);

    try {
      const nextSession = await authApi.me();
      setSession(nextSession);
      setStatus("authenticated");
      return nextSession;
    } catch (caughtError) {
      const apiError = normalizeUnknownError(caughtError);

      if (apiError.status === 401) {
        setSession(null);
        setStatus("unauthenticated");
        setError(null);
        return null;
      }

      setSession(null);
      setStatus("unauthenticated");
      setError(apiError);
      return null;
    }
  }, []);

  const login = useCallback(
    async (credentials: { email: string; password: string }) => {
      setError(null);
      await authApi.login(credentials);

      const nextSession = await authApi.me();
      setSession(nextSession);
      setStatus("authenticated");
      return nextSession;
    },
    [],
  );

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } finally {
      setSession(null);
      setStatus("unauthenticated");
      setError(null);
    }
  }, []);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  useEffect(() => {
    if (didHydrateRef.current) {
      return;
    }

    didHydrateRef.current = true;
    void refreshSession();
  }, [refreshSession]);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      session,
      error,
      isAuthenticated: status === "authenticated" && session !== null,
      login,
      logout,
      refreshSession,
      clearError,
    }),
    [clearError, error, login, logout, refreshSession, session, status],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error("useAuth must be used inside an AuthProvider.");
  }

  return context;
}
