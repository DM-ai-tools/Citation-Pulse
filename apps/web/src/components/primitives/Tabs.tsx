"use client";

import { cn } from "@/lib/utils";

export function TabList({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      role="tablist"
      className={cn("flex flex-wrap gap-2 border-b border-slate-200 pb-2", className)}
    >
      {children}
    </div>
  );
}

export function Tab({
  active,
  onClick,
  children,
}: {
  active?: boolean;
  onClick?: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={cn(
        "rounded-lg px-4 py-2 text-sm font-medium transition",
        active
          ? "bg-ink-900 text-white shadow-sm"
          : "border border-slate-200 bg-white text-ink-800 hover:bg-slate-50",
      )}
    >
      {children}
    </button>
  );
}
