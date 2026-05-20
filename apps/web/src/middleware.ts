import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { isAuthBypass, isDevOnlyBypass } from "@/lib/authBypass";
import { hasServerJwtSecret, verifyAccessToken } from "@/lib/sessionToken";

const PUBLIC_EXACT = new Set(["/login", "/signup", "/privacy", "/terms", "/admin/login"]);

function isPublicSharePath(pathname: string) {
  return pathname.startsWith("/r/");
}

function isPublicPath(pathname: string) {
  return PUBLIC_EXACT.has(pathname) || isPublicSharePath(pathname);
}

function isDevBypassSignedOut(request: NextRequest) {
  return request.cookies.get("cp_dev_signed_out")?.value === "1";
}

async function sessionFromRequest(request: NextRequest) {
  const token = request.cookies.get("cp_token")?.value?.trim() ?? "";
  if (token) {
    const claims = await verifyAccessToken(token);
    if (claims) {
      return { authenticated: true as const, role: claims.role, token };
    }
    if (!hasServerJwtSecret() && process.env.NODE_ENV !== "production") {
      const role = (request.cookies.get("cp_role")?.value as "user" | "admin") ?? "user";
      return { authenticated: true as const, role, token };
    }
  }
  if (isAuthBypass() && !(isDevOnlyBypass() && isDevBypassSignedOut(request))) {
    return { authenticated: true as const, role: "user" as const, token: "guest" };
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

function redirectAdminLogin(request: NextRequest) {
  const url = request.nextUrl.clone();
  url.pathname = "/admin/login";
  url.search = "";
  return NextResponse.redirect(url);
}

function isAdminPanelPath(pathname: string) {
  return pathname.startsWith("/admin") && pathname !== "/admin/login";
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
  const devSignedOut = isDevOnlyBypass() && isDevBypassSignedOut(request);

  if (pathname === "/") {
    const url = request.nextUrl.clone();
    url.pathname = bypass || session.authenticated ? "/landing" : "/login";
    url.search = "";
    return NextResponse.redirect(url);
  }

  if (isPublicPath(pathname)) {
    if (bypass && (pathname === "/login" || pathname === "/signup") && !devSignedOut) {
      const next = request.nextUrl.searchParams.get("next");
      const url = request.nextUrl.clone();
      url.pathname =
        next && next.startsWith("/") && !isPublicPath(next) ? next : "/landing";
      url.search = "";
      return NextResponse.redirect(url);
    }
    return NextResponse.next();
  }

  if (isAdminPanelPath(pathname)) {
    if (!session.authenticated) {
      return redirectAdminLogin(request);
    }
    if (session.role !== "admin") {
      return redirectAdminLogin(request);
    }
    return NextResponse.next();
  }

  if (!bypass && !session.authenticated) {
    return redirectLogin(request, pathname);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next|api|.*\\..*).*)"],
};
