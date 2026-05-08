export function apiBaseUrl(): string {
  const raw = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").trim();

  // Railway env values are sometimes saved without protocol; normalise defensively.
  const withProtocol = /^https?:\/\//i.test(raw) ? raw : `https://${raw.replace(/^\/+/, "")}`;
  return withProtocol.replace(/\/+$/, "");
}

export type ApiClientOptions = RequestInit & {
  getToken?: () => Promise<string | null>;
};

export async function apiClient(path: string, init: ApiClientOptions = {}) {
  const { getToken, ...rest } = init;
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const headers = new Headers(rest.headers);
  if (!headers.has("Content-Type") && rest.body && typeof rest.body === "string") {
    headers.set("Content-Type", "application/json");
  }
  if (getToken) {
    const t = await getToken();
    if (t) headers.set("Authorization", `Bearer ${t}`);
  }
  return fetch(`${apiBaseUrl()}${normalizedPath}`, { ...rest, headers, credentials: "include" });
}

/** Public fetch without Clerk (funnel + shared reports). */
export function apiFetch(path: string, init: RequestInit = {}) {
  return apiClient(path, init);
}
