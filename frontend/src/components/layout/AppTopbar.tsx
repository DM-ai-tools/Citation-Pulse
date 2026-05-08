"use client";

import Link from "next/link";
import { Menu } from "lucide-react";
import { Button } from "@/components/primitives";

export function AppTopbar({ onMenu }: { onMenu: () => void }) {
  return (
    <header className="flex h-14 items-center justify-between border-b border-slate-200 bg-white px-4 lg:px-6">
      <div className="flex items-center gap-2">
        <Button type="button" variant="ghost" size="sm" className="lg:hidden" onClick={onMenu} aria-label="Menu">
          <Menu className="h-5 w-5" />
        </Button>
        <span className="text-sm font-medium text-slate-600">Workspace</span>
      </div>
      <Link href="/" className="text-sm text-brand-primary hover:underline">
        Marketing site
      </Link>
    </header>
  );
}
