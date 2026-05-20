"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { isAuthBypass, isDevOnlyBypass } from "@/lib/authBypass";
import { isDevBypassSignedOut } from "@/lib/authSession";
import { redirectAfterAuth } from "@/lib/authRedirect";
import { markFreshLogin, normalizeAuthUser, setAuthSession } from "@/lib/authSession";
import { AuthField } from "@/components/auth/AuthField";
import { AuthFooterLink, AuthShell } from "@/components/auth/AuthShell";
import { AuthSubmitButton } from "@/components/auth/AuthSubmitButton";
import { useAuth } from "@/contexts/AuthContext";
import { passwordIssues } from "@/lib/passwordStrength";
import { signup } from "@/services/auth";

export default function SignupPage() {
  const router = useRouter();
  const queryClient = useQueryClient();

  useEffect(() => {
    if (isAuthBypass() && (!isDevOnlyBypass() || !isDevBypassSignedOut())) {
      router.replace("/landing");
    }
  }, [router]);
  const { setSession } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (password !== confirm) {
      setError("Passwords do not match");
      return;
    }
    const issues = passwordIssues(password);
    if (issues.length > 0) {
      setError(issues.join(" · "));
      return;
    }
    const emailNorm = email.trim().toLowerCase();
    const name = emailNorm.split("@")[0]?.trim() || "User";
    setLoading(true);
    try {
      const res = await signup({
        name,
        email: emailNorm,
        password,
        confirm_password: confirm,
      });
      const user = normalizeAuthUser(res.user);
      markFreshLogin();
      setAuthSession(res.access_token, user, true);
      setSession(res.access_token, user);
      await queryClient.invalidateQueries();
      toast.success("Account created");
      router.replace(redirectAfterAuth("/landing"));
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Signup failed";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell
      showLogo={false}
      title="Sign up"
      subtitle="Create your account using email and password."
      footer={
        <>
          Already signed up? <AuthFooterLink href="/login">Go to login</AuthFooterLink>
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
          label="Create password"
          type="password"
          autoComplete="new-password"
          required
          placeholder="At least 8 characters"
          showPasswordToggle
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <AuthField
          label="Confirm password"
          type="password"
          autoComplete="new-password"
          required
          placeholder="Re-enter password"
          showPasswordToggle
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
        />
        <AuthSubmitButton disabled={loading}>{loading ? "Creating account…" : "Create account"}</AuthSubmitButton>
      </form>
    </AuthShell>
  );
}
