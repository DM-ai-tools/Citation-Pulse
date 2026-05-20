import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { isAuthBypass } from "@/lib/authBypass";
import { hasServerJwtSecret, verifyAccessToken } from "@/lib/sessionToken";

const PUBLIC_EXACT = new Set(["/login", "/signup", "/privacy", "/terms", "/admin/login"]);

function isPublicSharePath(pathname: string) {
  return pathname.startsWith("/r/");
}

function isPublicPath(pathname: string) {
  return PUBLIC_EXACT.has(pathname) || isPublicSharePath(pathname);
}

async function sessionFromRequest(request: NextRequest) {
  if (isAuthBypass()) {
    return { authenticated: true as const, role: "user" as const, token: "dev-local" };
  }
  const token = request.cookies.get("cp_token")?.value?.trim() ?? "";
  if (!token) {
    return { authenticated: false as const, role: null, token: "" };
  }
  const claims = await verifyAccessToken(token);
  if (claims) {
    return { authenticated: true as const, role: claims.role, token };
  }
  if (!hasServerJwtSecret() && process.env.NODE_ENV !== "production") {
    const role = (request.cookies.get("cp_role")?.value as "user" | "admin") ?? "user";
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
  let session: Awaited<ReturnType<typeof sessionFromRequest>>;
  try {
    session = await sessionFromRequest(request);
  } catch {
    session = { authenticated: false as const, role: null, token: "" };
  }
  const bypass = isAuthBypass();

  if (pathname === "/") {
    const url = request.nextUrl.clone();
    url.pathname = bypass || session.authenticated ? "/landing" : "/login";
    url.search = "";
    return NextResponse.redirect(url);
  }

  if (isPublicPath(pathname)) {
    // Dev bypass only: auto-skip login/signup. Production always renders these pages (Railway healthcheck uses /login).
    if (bypass && (pathname === "/login" || pathname === "/signup")) {
      const next = request.nextUrl.searchParams.get("next");
      const url = request.nextUrl.clone();
      url.pathname =
        next && next.startsWith("/") && !isPublicPath(next) ? next : "/landing";
      url.search = "";
      return NextResponse.redirect(url);
    }
    return NextResponse.next();
  }

  if (!bypass && !session.authenticated) {
    return redirectLogin(request, pathname);
  }

  if (pathname.startsWith("/admin") && !bypass) {
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
