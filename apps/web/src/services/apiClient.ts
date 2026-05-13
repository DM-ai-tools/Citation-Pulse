let _warnedMisconfiguredApi = false;

/**
 * When ``NEXT_PUBLIC_API_URL`` is ``same-origin`` (or ``relative``), the browser calls
 * ``/api/v1/...`` on the Next.js host. Configure ``API_PROXY_TARGET`` in ``next.config.ts``
 * rewrites so those requests forward to FastAPI (avoids pointing the browser at the wrong
 * public hostname and getting HTML 404s for ``/brands/.../sov/...``).
 */
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
  if (
    !_warnedMisconfiguredApi &&
    typeof window !== "undefined" &&
    (u.includes("127.0.0.1") || u.includes("localhost")) &&
    !/^localhost$|^127\.0\.0\.1$/i.test(window.location.hostname)
  ) {
    _warnedMisconfiguredApi = true;
    console.warn(
      "[CitationPulse] NEXT_PUBLIC_API_URL points at localhost but this page is not on localhost. " +
        "Set NEXT_PUBLIC_API_URL to your public API URL at Next.js build time (Railway: Web service → Variables → rebuild). " +
        "Or use NEXT_PUBLIC_API_URL=same-origin with API_PROXY_TARGET rewrites (see infra/railway/README.md). " +
        "Otherwise the UI may call the wrong host and sections like Share of voice can 404."
    );
  }
  return u;
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

export type ApiClientOptions = RequestInit & {
  getToken?: () => Promise<string | null>;
};

export async function apiClient(path: string, init: ApiClientOptions = {}) {
  const { getToken, ...rest } = init;
  const headers = new Headers(rest.headers);
  if (!headers.has("Content-Type") && rest.body && typeof rest.body === "string") {
    headers.set("Content-Type", "application/json");
  }
  if (getToken) {
    const t = await getToken();
    if (t) headers.set("Authorization", `Bearer ${t}`);
  }
  return fetch(`${base()}${path}`, { ...rest, headers, credentials: "include" });
}

/** Public fetch without Clerk (funnel + shared reports). */
export function apiFetch(path: string, init: RequestInit = {}) {
  return apiClient(path, init);
}
