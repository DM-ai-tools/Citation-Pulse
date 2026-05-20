/** True when local bypass env flags are set (ignored in production builds/runtime). */
function bypassEnvEnabled(): boolean {
  return (
    (process.env.AUTH_DISABLE_JWT || "").toLowerCase() === "true" ||
    (process.env.NEXT_PUBLIC_AUTH_DISABLE_JWT || "").toLowerCase() === "true" ||
    (process.env.NEXT_PUBLIC_AUTH_BYPASS || "").toLowerCase() === "true"
  );
}

/** Local dev only: skip JWT/cookie crypto — API uses open Phase-1 access. Never active on Railway/production. */
export function isAuthBypass(): boolean {
  if (process.env.NODE_ENV === "production") return false;
  return bypassEnvEnabled();
}

export const DEV_BYPASS_USER = {
  id: "dev-local",
  name: "Local Dev",
  email: "dev@local",
  role: "user" as const,
  tenant_id: null,
};
