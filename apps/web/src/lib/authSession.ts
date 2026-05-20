const TOKEN_KEY = "cp_access_token";
const USER_KEY = "cp_user";

export type AuthUser = {
  id: string;
  name: string;
  email: string;
  role: "user" | "admin";
  tenant_id?: string | null;
};

export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function getStoredUser(): AuthUser | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? (JSON.parse(raw) as AuthUser) : null;
  } catch {
    return null;
  }
}

export function setAuthSession(token: string, user: AuthUser, remember = false) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
  const maxAge = remember ? 60 * 60 * 24 * 30 : 60 * 60 * 72;
  const secure = typeof window !== "undefined" && window.location.protocol === "https:" ? "; Secure" : "";
  document.cookie = `cp_token=${encodeURIComponent(token)}; path=/; max-age=${maxAge}; SameSite=Lax${secure}`;
  document.cookie = `cp_role=${user.role}; path=/; max-age=${maxAge}; SameSite=Lax${secure}`;
}

export function clearAuthSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  document.cookie = "cp_token=; path=/; max-age=0";
  document.cookie = "cp_role=; path=/; max-age=0";
}
