const TOKEN_KEY = "cp_access_token";
const USER_KEY = "cp_user";
const FRESH_LOGIN_KEY = "cp_fresh_login";
const DEV_SIGNED_OUT_KEY = "cp_dev_signed_out";

export type AuthUser = {
  id: string;
  name: string;
  email: string;
  role: "user" | "admin";
  tenant_id?: string | null;
};

/** Coerce API ``UserPublic`` (UUID fields, extra keys) into client session shape. */
export function normalizeAuthUser(raw: AuthUser | Record<string, unknown>): AuthUser {
  return {
    id: String(raw.id),
    name: String(raw.name),
    email: String(raw.email),
    role: raw.role === "admin" ? "admin" : "user",
    tenant_id: raw.tenant_id != null && raw.tenant_id !== "" ? String(raw.tenant_id) : null,
  };
}

export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function hasStoredSession(): boolean {
  return Boolean(getStoredToken() && getStoredUser());
}

export function getStoredUser(): AuthUser | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? normalizeAuthUser(JSON.parse(raw) as AuthUser) : null;
  } catch {
    return null;
  }
}

/** Set after a successful login/signup so guards do not fight navigation for a few seconds. */
export function markFreshLogin() {
  if (typeof window === "undefined") return;
  sessionStorage.setItem(FRESH_LOGIN_KEY, String(Date.now()));
}

export function isFreshLogin(maxAgeMs = 15_000): boolean {
  if (typeof window === "undefined") return false;
  const raw = sessionStorage.getItem(FRESH_LOGIN_KEY);
  if (!raw) return false;
  const ts = Number(raw);
  if (!Number.isFinite(ts)) return false;
  return Date.now() - ts < maxAgeMs;
}

export function clearFreshLogin() {
  if (typeof window === "undefined") return;
  sessionStorage.removeItem(FRESH_LOGIN_KEY);
}

export function setAuthSession(token: string, user: AuthUser | Record<string, unknown>, remember = false) {
  const normalized = normalizeAuthUser(user);
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(normalized));
  const maxAge = remember ? 60 * 60 * 24 * 30 : 60 * 60 * 72;
  const secure = typeof window !== "undefined" && window.location.protocol === "https:" ? "; Secure" : "";
  document.cookie = `cp_token=${encodeURIComponent(token)}; path=/; max-age=${maxAge}; SameSite=Lax${secure}`;
  document.cookie = `cp_role=${normalized.role}; path=/; max-age=${maxAge}; SameSite=Lax${secure}`;
}

export function clearAuthSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  clearFreshLogin();
  document.cookie = "cp_token=; path=/; max-age=0";
  document.cookie = "cp_role=; path=/; max-age=0";
}

/** Local dev bypass: user clicked sign out — skip auto dev session until next login. */
export function markDevBypassSignedOut() {
  if (typeof window === "undefined") return;
  sessionStorage.setItem(DEV_SIGNED_OUT_KEY, "1");
  document.cookie = "cp_dev_signed_out=1; path=/; max-age=86400; SameSite=Lax";
}

export function isDevBypassSignedOut(): boolean {
  if (typeof window === "undefined") return false;
  return sessionStorage.getItem(DEV_SIGNED_OUT_KEY) === "1";
}

export function clearDevBypassSignedOut() {
  if (typeof window === "undefined") return;
  sessionStorage.removeItem(DEV_SIGNED_OUT_KEY);
  document.cookie = "cp_dev_signed_out=; path=/; max-age=0";
}
