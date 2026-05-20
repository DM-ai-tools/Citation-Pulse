/** True when local bypass env flags are set. */
function bypassEnvEnabled(): boolean {
  return (
    (process.env.AUTH_DISABLE_JWT || "").toLowerCase() === "true" ||
    (process.env.NEXT_PUBLIC_AUTH_DISABLE_JWT || "").toLowerCase() === "true" ||
    (process.env.NEXT_PUBLIC_AUTH_BYPASS || "").toLowerCase() === "true"
  );
}

/** Production: open funnel — skip login/signup and go straight to landing (Railway Web build). */
function productionSkipAuthEnabled(): boolean {
  if (process.env.NODE_ENV !== "production") return false;
  const flag = (process.env.NEXT_PUBLIC_SKIP_AUTH || "true").toLowerCase();
  return flag !== "false" && flag !== "0";
}

/** Skip JWT/login gates (local dev flags or production public landing mode). */
export function isAuthBypass(): boolean {
  if (productionSkipAuthEnabled()) return true;
  if (process.env.NODE_ENV === "production") return false;
  return bypassEnvEnabled();
}

/** Local-only bypass (respects dev sign-out cookie). */
export function isDevOnlyBypass(): boolean {
  return process.env.NODE_ENV !== "production" && isAuthBypass();
}

export const DEV_BYPASS_USER = {
  id: "dev-local",
  name: "Local Dev",
  email: "dev@local",
  role: "user" as const,
  tenant_id: null,
};

export const PUBLIC_GUEST_USER = {
  id: "guest",
  name: "Guest",
  email: "guest@citationpulse.app",
  role: "user" as const,
  tenant_id: null,
};
