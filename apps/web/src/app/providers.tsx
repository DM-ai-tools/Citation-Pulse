"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ClerkProvider } from "@clerk/nextjs";
import { useState } from "react";
import { AuthProvider } from "@/contexts/AuthContext";

function clerkEnabled() {
  const k = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY || "";
  return k.length >= 32 && !k.includes("placeholder");
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 0,
            refetchOnMount: true,
            refetchOnWindowFocus: true,
          },
        },
      }),
  );
  if (clerkEnabled()) {
    return (
      <ClerkProvider>
        <QueryClientProvider client={client}>
          <AuthProvider>{children}</AuthProvider>
        </QueryClientProvider>
      </ClerkProvider>
    );
  }
  return (
    <QueryClientProvider client={client}>
      <AuthProvider>{children}</AuthProvider>
    </QueryClientProvider>
  );
}
