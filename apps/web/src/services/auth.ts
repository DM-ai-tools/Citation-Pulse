import { DEV_BYPASS_USER, PUBLIC_GUEST_USER, isAuthBypass, isDevOnlyBypass } from "@/lib/authBypass";
import { normalizeAuthUser, type AuthUser } from "@/lib/authSession";
import { apiClient } from "@/services/apiClient";

export type AuthResponse = {
  access_token: string;
  token_type: string;
  expires_at: string;
  user: AuthUser;
};

function fallbackAuthResponse(input: { email?: string; name?: string; role?: "user" | "admin" }): AuthResponse {
  const email = (input.email || "demo@citationpulse.local").trim().toLowerCase();
  const name = (input.name || email.split("@")[0] || "Demo User").trim();
  const now = new Date();
  const expires = new Date(now.getTime() + 72 * 60 * 60 * 1000);
  return {
    access_token: `bypass_${Math.random().toString(36).slice(2)}_${Date.now()}`,
    token_type: "bearer",
    expires_at: expires.toISOString(),
    user: {
      id: `demo_${Date.now()}`,
      name: name || "Demo User",
      email,
      role: input.role || "user",
      tenant_id: null,
    },
  };
}

export async function signup(payload: {
  name: string;
  email: string;
  password: string;
  confirm_password: string;
}) {
  const r = await apiClient("/api/v1/auth/signup", {
    method: "POST",
    auth: false,
    body: JSON.stringify(payload),
  });
  if (!r.ok) {
    if (r.status === 404) {
      if (isAuthBypass()) return fallbackAuthResponse({ email: payload.email, name: payload.name, role: "user" });
      throw new Error("Sign up failed");
    }
    const err = await r.json().catch(() => ({}));
    const d = err.detail;
    if (typeof d === "string") throw new Error(d);
    if (Array.isArray(d)) {
      const msg = d.map((x: { msg?: string }) => x.msg).filter(Boolean).join(" · ");
      if (msg) throw new Error(msg);
    }
    if (d && typeof d === "object") {
      if ("message" in d && Array.isArray(d.issues)) {
        throw new Error(`${d.message}: ${(d.issues as string[]).join(" · ")}`);
      }
      if ("message" in d) throw new Error(String(d.message));
    }
    throw new Error("Signup failed");
  }
  return (await r.json()) as AuthResponse;
}

export async function login(payload: { email: string; password: string; remember?: boolean }) {
  const r = await apiClient("/api/v1/auth/login", {
    method: "POST",
    auth: false,
    body: JSON.stringify(payload),
  });
  if (!r.ok) {
    if (r.status === 404) {
      if (isAuthBypass()) return fallbackAuthResponse({ email: payload.email, role: "user" });
      throw new Error("Login failed");
    }
    const err = await r.json().catch(() => ({}));
    throw new Error(typeof err.detail === "string" ? err.detail : "Invalid email or password");
  }
  return (await r.json()) as AuthResponse;
}

export async function adminLogin(payload: { username: string; password: string }) {
  const r = await apiClient("/api/v1/auth/admin/login", {
    method: "POST",
    auth: false,
    body: JSON.stringify(payload),
  });
  if (!r.ok) {
    if (r.status === 404 && isAuthBypass()) {
      return fallbackAuthResponse({
        email: payload.username.includes("@") ? payload.username : `${payload.username}@citationpulse.local`,
        name: payload.username || "Admin",
        role: "admin",
      });
    }
    const err = await r.json().catch(() => ({}));
    throw new Error(typeof err.detail === "string" ? err.detail : "Admin login failed");
  }
  return (await r.json()) as AuthResponse;
}

export async function logout() {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("cp_access_token") : null;
  if (token) {
    await apiClient("/api/v1/auth/logout", {
      method: "POST",
      getToken: async () => token,
    }).catch(() => undefined);
  }
}

export async function fetchMe(token: string) {
  if (isAuthBypass()) {
    return normalizeAuthUser(isDevOnlyBypass() ? DEV_BYPASS_USER : PUBLIC_GUEST_USER);
  }
  const r = await apiClient("/api/v1/auth/me", {
    getToken: async () => token,
    clearSessionOn401: false,
  });
  if (r.status === 401) throw new Error("Session expired");
  if (!r.ok) throw new Error("Could not verify session");
  return normalizeAuthUser((await r.json()) as AuthUser);
}
