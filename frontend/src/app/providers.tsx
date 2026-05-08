"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ClerkProvider } from "@clerk/nextjs";
import { useState } from "react";

function clerkEnabled() {
  const k = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY || "";
  return k.length >= 32 && !k.includes("placeholder");
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(() => new QueryClient());
  if (clerkEnabled()) {
    return (
      <ClerkProvider>
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
      </ClerkProvider>
    );
  }
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
