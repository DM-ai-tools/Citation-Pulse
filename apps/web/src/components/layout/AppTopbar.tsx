"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Menu, LogOut } from "lucide-react";
import { Button } from "@/components/primitives";
import { useAuth } from "@/contexts/AuthContext";
import { clearAuthSession } from "@/lib/authSession";
import { logout } from "@/services/auth";

export function AppTopbar({ onMenu }: { onMenu: () => void }) {
  const router = useRouter();
  const { user, signOut } = useAuth();

  async function onLogout() {
    await logout().catch(() => undefined);
    signOut();
    clearAuthSession();
    router.push("/login");
  }

  return (
    <header className="flex h-14 items-center justify-between border-b border-slate-200 bg-white px-4 lg:px-6">
      <div className="flex items-center gap-2">
        <Button type="button" variant="ghost" size="sm" className="lg:hidden" onClick={onMenu} aria-label="Menu">
          <Menu className="h-5 w-5" />
        </Button>
        <span className="text-sm font-medium text-slate-600">Workspace</span>
      </div>
      <div className="flex items-center gap-3">
        {user ? (
          <span className="hidden text-sm text-slate-600 sm:inline">{user.name}</span>
        ) : null}
        <Link href="/landing" className="text-sm text-brand-primary hover:underline">
          Marketing site
        </Link>
        {user ? (
          <Button type="button" variant="ghost" size="sm" onClick={() => void onLogout()} aria-label="Log out">
            <LogOut className="h-4 w-4" />
          </Button>
        ) : (
          <Link href="/login" className="text-sm font-semibold text-brand-primary hover:underline">
            Sign in
          </Link>
        )}
      </div>
    </header>
  );
}
