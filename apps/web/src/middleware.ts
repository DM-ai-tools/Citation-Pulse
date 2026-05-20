import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { hasServerJwtSecret, verifyAccessToken } from "@/lib/sessionToken";

const BYPASS_AUTH = (process.env.AUTH_DISABLE_JWT || "").toLowerCase() === "true";

/** Routes reachable without a valid session (login/legal/share links only). */
const PUBLIC_EXACT = new Set(["/login", "/signup", "/privacy", "/terms", "/admin/login"]);

/** Token-based public share pages (no account required). */
function isPublicSharePath(pathname: string) {
  return pathname.startsWith("/r/");
}

function isPublicPath(pathname: string) {
  return PUBLIC_EXACT.has(pathname) || isPublicSharePath(pathname);
}

async function sessionFromRequest(request: NextRequest) {
  if (BYPASS_AUTH) {
    const token = request.cookies.get("cp_token")?.value?.trim() ?? "";
    const role = (request.cookies.get("cp_role")?.value as "user" | "admin" | undefined) ?? "user";
    return { authenticated: true as const, role, token };
  }
  const token = request.cookies.get("cp_token")?.value?.trim() ?? "";
  if (!token) {
    return { authenticated: false as const, role: null, token: "" };
  }
  const claims = await verifyAccessToken(token);
  if (claims) {
    return { authenticated: true as const, role: claims.role, token };
  }
  // Dev fallback when web service has no AUTH_JWT_SECRET: cookie presence only.
  if (!hasServerJwtSecret() && process.env.NODE_ENV !== "production") {
    const role = request.cookies.get("cp_role")?.value ?? "user";
    return { authenticated: true as const, role, token };
  }
  return { authenticated: false as const, role: null, token: "" };
}

function redirectLogin(request: NextRequest, nextPath?: string) {
  const url = request.nextUrl.clone();
  url.pathname = "/login";
  url.search = "";
  if (nextPath && nextPath !== "/login" && nextPath !== "/signup") {
    url.searchParams.set("next", nextPath);
  }
  return NextResponse.redirect(url);
}

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const session = await sessionFromRequest(request);

  if (pathname === "/") {
    const url = request.nextUrl.clone();
    url.pathname = session.authenticated ? "/landing" : "/login";
    url.search = "";
    return NextResponse.redirect(url);
  }

  if (isPublicPath(pathname)) {
    if ((pathname === "/login" || pathname === "/signup") && session.authenticated) {
      const next = request.nextUrl.searchParams.get("next");
      const url = request.nextUrl.clone();
      url.pathname =
        next && next.startsWith("/") && !isPublicPath(next) ? next : "/landing";
      url.search = "";
      return NextResponse.redirect(url);
    }
    return NextResponse.next();
  }

  if (!session.authenticated) {
    return redirectLogin(request, pathname);
  }

  if (pathname.startsWith("/admin")) {
    if (session.role !== "admin") {
      const url = request.nextUrl.clone();
      url.pathname = "/admin/login";
      url.search = "";
      return NextResponse.redirect(url);
    }
    return NextResponse.next();
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next|api|.*\\..*).*)"],
};
