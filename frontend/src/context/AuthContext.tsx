import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, AUTH_REJECTED_EVENT, errMessage, getToken, setToken } from "../api/client";
import type { Token, User } from "../api/types";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState>({
  user: null,
  loading: true,
  login: async () => {},
  logout: () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  // Backend rejected our credentials (401 / WS 4401): drop the in-memory user so
  // RequireAuth redirects to login instead of leaving pages stuck on "Loading".
  useEffect(() => {
    const onRejected = () => setUser(null);
    window.addEventListener(AUTH_REJECTED_EVENT, onRejected);
    return () => window.removeEventListener(AUTH_REJECTED_EVENT, onRejected);
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!getToken()) {
        setLoading(false);
        return;
      }
      try {
        const res = await api.get<User>("/auth/me");
        if (!cancelled) setUser(res.data);
      } catch {
        setToken(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const form = new URLSearchParams({ username, password });
    const res = await api.post<Token>("/auth/login", form, {
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    });
    setToken(res.data.access_token);
    const me = await api.get<User>("/auth/me");
    setUser(me.data);
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.post("/auth/logout");
    } catch (e) {
      void errMessage(e);
    }
    setToken(null);
    setUser(null);
  }, []);

  const value = useMemo(() => ({ user, loading, login, logout }), [user, loading, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
