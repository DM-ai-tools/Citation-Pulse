"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, type ReactNode } from "react";
import { Skeleton } from "@/components/primitives";
import { useAuth } from "@/contexts/AuthContext";
import { hasStoredSession, isFreshLogin } from "@/lib/authSession";

/** Client-side guard for protected pages. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const sentToLogin = useRef(false);

  const allowed = Boolean(user || hasStoredSession());

  useEffect(() => {
    if (loading || allowed || isFreshLogin()) return;
    if (sentToLogin.current) return;
    sentToLogin.current = true;
    const next = encodeURIComponent(pathname);
    router.replace(`/login?next=${next}`);
  }, [loading, allowed, pathname, router]);

  if (loading) {
    return (
      <div className="mx-auto max-w-lg space-y-4 p-8">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (!allowed) return null;

  return <>{children}</>;
}
