"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { AuthField } from "@/components/auth/AuthField";
import { AuthShell } from "@/components/auth/AuthShell";
import { AuthSubmitButton } from "@/components/auth/AuthSubmitButton";
import { useAuth } from "@/contexts/AuthContext";
import { setAuthSession } from "@/lib/authSession";
import { adminLogin } from "@/services/auth";

export default function AdminLoginPage() {
  const router = useRouter();
  const { setSession } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await adminLogin({ username, password });
      setAuthSession(res.access_token, res.user, true);
      setSession(res.access_token, res.user);
      toast.success("Admin session started");
      router.push("/admin/dashboard");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Admin login failed";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell
      showLogo={false}
      title="Admin login"
      subtitle="Sign in with your operator username and password."
      footer={
        <Link href="/landing" className="font-semibold text-[#7cb83a] hover:text-[#6fa832] hover:underline">
          ← Back to site
        </Link>
      }
    >
      <form onSubmit={onSubmit} className="space-y-5">
        {error ? (
          <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p>
        ) : null}
        <AuthField
          label="Username"
          type="text"
          autoComplete="username"
          required
          placeholder="Traffic-Radius"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
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
