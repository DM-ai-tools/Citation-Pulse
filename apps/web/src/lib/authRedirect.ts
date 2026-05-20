/** Full navigation after auth so cookies are applied before the next route loads. */
export function redirectAfterAuth(path = "/landing") {
  if (typeof window !== "undefined") {
    window.location.assign(path);
  }
}
