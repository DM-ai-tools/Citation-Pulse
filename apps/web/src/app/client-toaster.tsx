"use client";

import { useEffect, useState } from "react";
import { Toaster } from "sonner";

/** Mount after hydration so prerender / 404 never SSR-render Sonner internals. */
export function ClientToaster() {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  if (!mounted) return null;
  return <Toaster richColors position="top-center" />;
}
