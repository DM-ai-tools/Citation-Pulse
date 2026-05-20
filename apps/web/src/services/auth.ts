import { apiClient } from "@/services/apiClient";
import type { AuthUser } from "@/lib/authSession";

export type AuthResponse = {
  access_token: string;
  token_type: string;
  expires_at: string;
  user: AuthUser;
};

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
      throw new Error(
        "Sign up API not found. Ensure the API is running and API_PROXY_TARGET in apps/web/.env.local matches the API port (see .dev-api-port in the repo root).",
      );
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
      throw new Error(
        "Login API not found. Ensure the API is running and API_PROXY_TARGET matches the API port.",
      );
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
  const r = await apiClient("/api/v1/auth/me", { getToken: async () => token });
  if (!r.ok) throw new Error("Session expired");
  return (await r.json()) as AuthUser;
}
