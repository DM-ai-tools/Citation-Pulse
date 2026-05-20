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

/** Navigate after login/signup; falls back to full load if the SPA transition stalls. */
export function navigateAfterAuth(
  router: { replace: (href: string) => void },
  path?: string,
) {
  const target = redirectAfterAuth(path);
  router.replace(target);
  if (typeof window === "undefined") return;
  window.setTimeout(() => {
    const p = window.location.pathname;
    if (p === "/login" || p === "/signup") {
      window.location.assign(target);
    }
  }, 400);
}
