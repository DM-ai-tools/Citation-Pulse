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
import { DEV_BYPASS_USER, isAuthBypass } from "@/lib/authBypass";
import {
  clearAuthSession,
  getStoredToken,
  getStoredUser,
  normalizeAuthUser,
  setAuthSession,
  type AuthUser,
} from "@/lib/authSession";

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
    if (isAuthBypass()) {
      const devUser = normalizeAuthUser(DEV_BYPASS_USER);
      setToken("dev-local");
      setUser(devUser);
      setAuthSession("dev-local", devUser, true);
      setLoading(false);
      return;
    }
    const t = getStoredToken();
    const u = getStoredUser();
    if (t && u) {
      setToken(t);
      setUser(u);
    }
    setLoading(false);
  }, []);

  const setSession = useCallback((t: string, u: AuthUser) => {
    setToken(t);
    setUser(normalizeAuthUser(u));
  }, []);

  const signOut = useCallback(() => {
    if (isAuthBypass()) {
      const devUser = normalizeAuthUser(DEV_BYPASS_USER);
      setAuthSession("dev-local", devUser, true);
      setToken("dev-local");
      setUser(devUser);
      return;
    }
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
