let _warnedMisconfiguredApi = false;

function base(): string {
  const u = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
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
        "Otherwise the UI may call the wrong host and sections like Top gap opportunities can look empty."
    );
  }
  return u;
}

/** Resolved API origin (same value used for fetch). Exposed for user-facing errors — not a secret. */
export function publicApiBaseUrl(): string {
  return base();
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
