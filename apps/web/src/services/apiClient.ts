const base = () => process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
