/** Local dev: skip JWT/cookie crypto — API uses open Phase-1 access. */
export function isAuthBypass(): boolean {
  return (
    (process.env.NEXT_PUBLIC_AUTH_BYPASS || "").toLowerCase() === "true" ||
    (process.env.NEXT_PUBLIC_AUTH_DISABLE_JWT || "").toLowerCase() === "true"
  );
}

export const DEV_BYPASS_USER = {
  id: "dev-local",
  name: "Local Dev",
  email: "dev@local",
  role: "user" as const,
  tenant_id: null,
};
