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
import { clearAuthSession, getStoredToken, getStoredUser, type AuthUser } from "@/lib/authSession";
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

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const t = getStoredToken();
    const u = getStoredUser();
    if (!t || !u) {
      setLoading(false);
      return;
    }
    setToken(t);
    setUser(u);
    if (BYPASS_AUTH) {
      setLoading(false);
      return;
    }
    fetchMe(t)
      .then((fresh) => setUser(fresh))
      .catch(() => {
        clearAuthSession();
        setToken(null);
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const setSession = useCallback((t: string, u: AuthUser) => {
    setToken(t);
    setUser(u);
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
