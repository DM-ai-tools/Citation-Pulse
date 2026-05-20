/** Full navigation after auth so cookies are applied before the next route loads. */
export function redirectAfterAuth(path?: string) {
  if (typeof window === "undefined") return;
  const params = new URLSearchParams(window.location.search);
  const next = params.get("next");
  const target =
    path ??
    (next && next.startsWith("/") && next !== "/login" && next !== "/signup" ? next : "/landing");
  window.location.assign(target);
}
