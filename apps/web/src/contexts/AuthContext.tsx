"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  clearAuthSession,
  getStoredToken,
  getStoredUser,
  normalizeAuthUser,
  setAuthSession,
  type AuthUser,
} from "@/lib/authSession";
import { fetchMe } from "@/services/auth";

const BYPASS_AUTH = (process.env.NEXT_PUBLIC_AUTH_BYPASS || "").toLowerCase() === "true";

type AuthContextValue = {
  user: AuthUser | null;
  token: string | null;
  loading: boolean;
  setSession: (token: string, user: AuthUser) => void;
  signOut: () => void;
  getToken: () => Promise<string | null>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const t = getStoredToken();
    const u = getStoredUser();
    if (!t || !u) {
      setLoading(false);
      return;
    }
    setToken(t);
    setUser(u);
    setLoading(false);

    if (BYPASS_AUTH) {
      return;
    }

    // Background refresh only — never block UI. Ignore stale responses after login/logout.
    void fetchMe(t)
      .then((fresh) => {
        if (cancelled || getStoredToken() !== t) return;
        setUser(fresh);
        setAuthSession(t, fresh, true);
      })
      .catch((err: unknown) => {
        if (cancelled || getStoredToken() !== t) return;
        const msg = err instanceof Error ? err.message : "";
        if (msg === "Session expired") {
          clearAuthSession();
          setToken(null);
          setUser(null);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const setSession = useCallback((t: string, u: AuthUser) => {
    setToken(t);
    setUser(normalizeAuthUser(u));
  }, []);

  const signOut = useCallback(() => {
    clearAuthSession();
    setToken(null);
    setUser(null);
  }, []);

  const getToken = useCallback(async () => token ?? getStoredToken(), [token]);

  const value = useMemo(
    () => ({ user, token, loading, setSession, signOut, getToken }),
    [user, token, loading, setSession, signOut, getToken],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
