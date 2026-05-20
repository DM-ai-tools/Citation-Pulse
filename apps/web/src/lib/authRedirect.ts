/** Post-login destination (honours ``?next=`` when safe). */
export function postAuthPath(fallback = "/landing"): string {
  if (typeof window === "undefined") return fallback;
  const params = new URLSearchParams(window.location.search);
  const next = params.get("next");
  if (next && next.startsWith("/") && next !== "/login" && next !== "/signup") {
    return next;
  }
  return fallback;
}

/** Client navigation after auth (keeps React session; prefer over full reload). */
export function redirectAfterAuth(path?: string) {
  return postAuthPath(path ?? "/landing");
}
