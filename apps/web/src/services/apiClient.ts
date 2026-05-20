import { isFreshLogin } from "@/lib/authSession";

let _warnedMisconfiguredApi = false;
const BYPASS_AUTH = (process.env.NEXT_PUBLIC_AUTH_BYPASS || "").toLowerCase() === "true";

/**
 * When ``NEXT_PUBLIC_API_URL`` is ``same-origin`` (or ``relative``), the browser calls
 * ``/api/v1/...`` on the Next.js host. Configure ``API_PROXY_TARGET`` in ``next.config.ts``
 * rewrites so those requests forward to FastAPI (avoids pointing the browser at the wrong
 * public hostname and getting HTML 404s for ``/brands/.../sov/...``).
 */
function isLocalApiHost(url: string): boolean {
  try {
    const h = new URL(url).hostname;
    return h === "localhost" || h === "127.0.0.1" || h === "[::1]";
  } catch {
    return /localhost|127\.0\.0\.1/i.test(url);
  }
}

function base(): string {
  const raw = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").trim();
  const mode = raw.toLowerCase();
  if (mode === "same-origin" || mode === "relative") {
    if (typeof window !== "undefined") {
      return "";
    }
    const upstream = (process.env.API_PROXY_TARGET || "").trim().replace(/\/+$/, "");
    return upstream || "http://localhost:8000";
  }
  // Strip trailing slash so fetch(`${base()}${path}`) never produces double-slash.
  // Also ensure the value has a protocol — missing https:// would make fetch treat
  // the whole string as a relative path, routing API calls through the frontend service.
  let u = raw.replace(/\/+$/, "");
  if (u && !u.startsWith("http://") && !u.startsWith("https://")) {
    u = `https://${u}`;
  }
  if (typeof window !== "undefined") {
    const pageHost = window.location.hostname;
    const onRailway = pageHost.endsWith(".up.railway.app");
    // Production bundle still defaults to localhost when NEXT_PUBLIC_API_URL was not set at build.
    if (onRailway && isLocalApiHost(u)) {
      return "";
    }
    if (
      !_warnedMisconfiguredApi &&
      isLocalApiHost(u) &&
      !/^localhost$|^127\.0\.0\.1$/i.test(pageHost)
    ) {
      _warnedMisconfiguredApi = true;
      console.warn(
        "[CitationPulse] NEXT_PUBLIC_API_URL points at localhost but this page is not on localhost. " +
          "Set NEXT_PUBLIC_API_URL to your public API URL at Next.js build time (Railway: Web service → Variables → rebuild). " +
          "Or use NEXT_PUBLIC_API_URL=same-origin with API_PROXY_TARGET rewrites (see infra/railway/README.md)."
      );
    }
  }
  return u;
}

/** True when the UI will call the API on the same host (Next rewrites or Railway fallback). */
export function apiUsesSameOrigin(): boolean {
  return base() === "";
}

/** Resolved API origin (same value used for fetch). Exposed for user-facing errors — not a secret. */
export function publicApiBaseUrl(): string {
  const b = base();
  if (b) return b;
  if (typeof window !== "undefined") {
    return window.location.origin;
  }
  const upstream = (process.env.API_PROXY_TARGET || "").trim().replace(/\/+$/, "");
  return upstream || "http://localhost:8000";
}

const TOKEN_KEY = "cp_access_token";

function storedAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export type ApiClientOptions = RequestInit & {
  getToken?: () => Promise<string | null>;
  /** When false, never attach Authorization (public funnel endpoints). Default true in browser. */
  auth?: boolean;
  /** When false, 401 does not clear storage or redirect (e.g. session probe on boot). Default true. */
  clearSessionOn401?: boolean;
};

function redirectToLogin() {
  if (typeof window === "undefined") return;
  const path = window.location.pathname;
  if (path === "/login" || path === "/signup" || path.startsWith("/r/")) return;
  const next = encodeURIComponent(path + window.location.search);
  window.location.assign(`/login?next=${next}`);
}

export async function apiClient(path: string, init: ApiClientOptions = {}) {
  const { getToken, auth = true, clearSessionOn401 = true, ...rest } = init;
  const headers = new Headers(rest.headers);
  if (!headers.has("Content-Type") && rest.body && typeof rest.body === "string") {
    headers.set("Content-Type", "application/json");
  }
  if (auth && !headers.has("Authorization")) {
    const t = getToken ? await getToken() : storedAccessToken();
    if (t) headers.set("Authorization", `Bearer ${t}`);
    else if (!BYPASS_AUTH && typeof window !== "undefined") {
      redirectToLogin();
      throw new Error("Sign in required");
    }
  }
  const r = await fetch(`${base()}${path}`, { ...rest, headers, credentials: "include" });
  if (
    auth &&
    clearSessionOn401 &&
    !isFreshLogin() &&
    r.status === 401 &&
    !BYPASS_AUTH &&
    typeof window !== "undefined"
  ) {
    const { clearAuthSession } = await import("@/lib/authSession");
    clearAuthSession();
    redirectToLogin();
    throw new Error("Session expired — sign in again");
  }
  return r;
}

/** Authenticated API call (default for app data). */
export function apiFetch(path: string, init: ApiClientOptions = {}) {
  return apiClient(path, { auth: true, ...init });
}

/** Unauthenticated call — only for token-based public share endpoints. */
export function publicApiFetch(path: string, init: ApiClientOptions = {}) {
  return apiClient(path, { auth: false, ...init });
}
