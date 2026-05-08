"use client";

import { useState } from "react";
import { AppSidebar } from "./AppSidebar";
import { AppTopbar } from "./AppTopbar";
import { cn } from "@/lib/utils";

export function AppShell({ children }: { children: React.ReactNode }) {
  const [drawer, setDrawer] = useState(false);
  return (
    <div className="flex min-h-screen bg-slate-50">
      <AppSidebar />
      <div
        className={cn(
          "fixed inset-0 z-40 bg-black/40 lg:hidden",
          drawer ? "block" : "hidden",
        )}
        aria-hidden
        onClick={() => setDrawer(false)}
      />
      <div
        className={cn(
          "fixed inset-y-0 left-0 z-50 w-64 max-w-[85vw] bg-white shadow-xl transition-transform lg:hidden",
          drawer ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <AppSidebar mobile onNavigate={() => setDrawer(false)} />
      </div>
      <div className="flex min-h-screen min-w-0 flex-1 flex-col">
        <AppTopbar onMenu={() => setDrawer(true)} />
        <main className="flex-1 p-4 lg:p-8">{children}</main>
      </div>
    </div>
  );
}
