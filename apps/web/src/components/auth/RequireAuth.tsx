"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { Skeleton } from "@/components/primitives";
import { useAuth } from "@/contexts/AuthContext";

/** Client-side guard for protected pages (pairs with edge middleware). */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (loading) return;
    if (!user) {
      const next = encodeURIComponent(pathname);
      router.replace(`/login?next=${next}`);
    }
  }, [loading, user, pathname, router]);

  if (loading) {
    return (
      <div className="mx-auto max-w-lg space-y-4 p-8">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (!user) return null;

  return <>{children}</>;
}
