"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const links = [{ href: "/dashboard", label: "Dashboard" }];

export function AppSidebar({ mobile = false, onNavigate }: { mobile?: boolean; onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <aside
      className={cn(
        "flex flex-col gap-1 border-r border-slate-200 bg-white p-4",
        mobile ? "w-full" : "hidden w-56 shrink-0 lg:flex",
      )}
    >
      <Link href="/" className="mb-4 font-display text-lg font-bold text-ink-900" onClick={onNavigate}>
        Citation<span className="text-brand-primary">Pulse</span>
      </Link>
      {links.map((l) => (
        <Link
          key={l.href}
          href={l.href}
          onClick={onNavigate}
          className={cn(
            "rounded-lg px-3 py-2 text-sm font-medium",
            pathname === l.href ? "bg-ink-900 text-white" : "text-ink-800 hover:bg-slate-100",
          )}
        >
          {l.label}
        </Link>
      ))}
    </aside>
  );
}
