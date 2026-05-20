import { isAuthBypass } from "@/lib/authBypass";

let _warnedMisconfiguredApi = false;

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
  let u = raw.replace(/\/+$/, "");
  if (u && !u.startsWith("http://") && !u.startsWith("https://")) {
    u = `https://${u}`;
  }
  if (typeof window !== "undefined") {
    const pageHost = window.location.hostname;
    const onRailway = pageHost.endsWith(".up.railway.app");
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
          "Set NEXT_PUBLIC_API_URL to your public API URL at Next.js build time, or use same-origin + API_PROXY_TARGET.",
      );
    }
  }
  return u;
}

export function apiUsesSameOrigin(): boolean {
  return base() === "";
}

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
  /** When false, never attach Authorization (public funnel endpoints). Default: false if auth bypass. */
  auth?: boolean;
  clearSessionOn401?: boolean;
};

export async function apiClient(path: string, init: ApiClientOptions = {}) {
  const bypass = isAuthBypass();
  const { getToken, auth = !bypass, clearSessionOn401 = !bypass, ...rest } = init;
  const headers = new Headers(rest.headers);
  if (!headers.has("Content-Type") && rest.body && typeof rest.body === "string") {
    headers.set("Content-Type", "application/json");
  }
  if (auth && !headers.has("Authorization")) {
    const t = getToken ? await getToken() : storedAccessToken();
    if (t) headers.set("Authorization", `Bearer ${t}`);
    else if (!bypass && typeof window !== "undefined") {
      throw new Error("Sign in required");
    }
  }
  const r = await fetch(`${base()}${path}`, { ...rest, headers, credentials: "include" });
  if (auth && clearSessionOn401 && r.status === 401 && !bypass && typeof window !== "undefined") {
    const { clearAuthSession } = await import("@/lib/authSession");
    clearAuthSession();
    throw new Error("Session expired — sign in again");
  }
  return r;
}

export function apiFetch(path: string, init: ApiClientOptions = {}) {
  const bypass = isAuthBypass();
  return apiClient(path, { auth: init.auth ?? !bypass, ...init });
}

export function publicApiFetch(path: string, init: ApiClientOptions = {}) {
  return apiClient(path, { auth: false, ...init });
}
