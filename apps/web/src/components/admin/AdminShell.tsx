"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { FileText, LayoutDashboard, LogOut, Users } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/contexts/AuthContext";
import { clearAuthSession } from "@/lib/authSession";
import { logout } from "@/services/auth";

const nav = [
  { href: "/admin/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/admin/users", label: "Users", icon: Users },
  { href: "/admin/reports", label: "Reports", icon: FileText },
];

export function AdminShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { signOut, user } = useAuth();

  async function onLogout() {
    await logout().catch(() => undefined);
    signOut();
    clearAuthSession();
    router.push("/admin/login");
  }

  return (
    <div className="flex min-h-screen bg-slate-50">
      <aside className="hidden w-64 flex-col border-r border-tr-line bg-white lg:flex">
        <div className="border-b border-tr-line px-5 py-5">
          <p className="font-display text-lg font-bold text-tr-navy">
            Citation<span className="text-brand-primary">Pulse</span>
          </p>
          <p className="text-xs font-semibold uppercase tracking-wide text-tr-teal">Admin</p>
        </div>
        <nav className="flex-1 space-y-1 p-3">
          {nav.map(({ href, label, icon: Icon }) => {
            const active = pathname === href || pathname.startsWith(`${href}/`);
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  "flex items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm font-semibold transition",
                  active
                    ? "bg-tr-navy text-white"
                    : "text-tr-navy hover:bg-tr-pale/60 hover:text-brand-primary",
                )}
              >
                <Icon className="h-4 w-4 shrink-0" />
                {label}
              </Link>
            );
          })}
        </nav>
        <div className="border-t border-tr-line p-4">
          <p className="truncate text-xs text-tr-mute">{user?.email}</p>
          <button
            type="button"
            onClick={() => void onLogout()}
            className="mt-3 flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold text-tr-navy hover:bg-slate-100"
          >
            <LogOut className="h-4 w-4" />
            Logout
          </button>
        </div>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="border-b border-tr-line bg-white px-6 py-4 lg:hidden">
          <p className="font-display font-bold text-tr-navy">Admin · {pathname.split("/").pop()}</p>
        </header>
        <main className="flex-1 p-6 lg:p-8">{children}</main>
      </div>
    </div>
  );
}
