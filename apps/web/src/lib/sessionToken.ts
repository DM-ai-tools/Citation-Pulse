import { jwtVerify } from "jose";

export type SessionClaims = {
  sub: string;
  role: string;
  email?: string;
};

const WEAK_SECRETS = new Set([
  "",
  "change-me-set-AUTH_JWT_SECRET-in-production",
  "change-me-use-openssl-rand-hex-32",
]);

function jwtSecret(): Uint8Array | null {
  const raw = (process.env.AUTH_JWT_SECRET || "").trim();
  if (!raw || WEAK_SECRETS.has(raw)) return null;
  return new TextEncoder().encode(raw);
}

/** Verify Citation Pulse access JWT (same secret as API). */
export async function verifyAccessToken(token: string): Promise<SessionClaims | null> {
  const secret = jwtSecret();
  if (!secret) return null;
  try {
    const { payload } = await jwtVerify(token, secret, { algorithms: ["HS256"] });
    if (payload.type !== "access" || typeof payload.sub !== "string") return null;
    return {
      sub: payload.sub,
      role: typeof payload.role === "string" ? payload.role : "user",
      email: typeof payload.email === "string" ? payload.email : undefined,
    };
  } catch {
    return null;
  }
}

/** True when middleware can cryptographically validate sessions (production-ready). */
export function hasServerJwtSecret(): boolean {
  return jwtSecret() !== null;
}
