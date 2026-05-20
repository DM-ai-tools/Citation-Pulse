"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { redirectAfterAuth } from "@/lib/authRedirect";
import { markFreshLogin, normalizeAuthUser, setAuthSession } from "@/lib/authSession";
import { AuthField } from "@/components/auth/AuthField";
import { AuthFooterLink, AuthShell } from "@/components/auth/AuthShell";
import { AuthSubmitButton } from "@/components/auth/AuthSubmitButton";
import { useAuth } from "@/contexts/AuthContext";
import { login } from "@/services/auth";

export default function LoginPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { setSession } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const remember = true;
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await login({ email: email.trim().toLowerCase(), password, remember });
      const user = normalizeAuthUser(res.user);
      markFreshLogin();
      setAuthSession(res.access_token, user, remember);
      setSession(res.access_token, user);
      await queryClient.invalidateQueries();
      toast.success("Welcome back");
      router.replace(redirectAfterAuth("/landing"));
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Login failed";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell
      showLogo={false}
      title="Login"
      subtitle="Login with your email and password."
      footer={
        <>
          Haven&apos;t already signed up? <AuthFooterLink href="/signup">Go to sign up</AuthFooterLink>
        </>
      }
    >
      <form onSubmit={onSubmit} className="space-y-5">
        {error ? (
          <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p>
        ) : null}
        <AuthField
          label="Email"
          type="email"
          autoComplete="email"
          required
          placeholder="you@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <AuthField
          label="Password"
          type="password"
          autoComplete="current-password"
          required
          placeholder="Enter password"
          showPasswordToggle
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <AuthSubmitButton disabled={loading}>{loading ? "Signing in…" : "Login"}</AuthSubmitButton>
      </form>
    </AuthShell>
  );
}
