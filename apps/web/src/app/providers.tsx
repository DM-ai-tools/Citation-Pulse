"use client";

import dynamic from "next/dynamic";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { AuthProvider } from "@/contexts/AuthContext";

function clerkEnabled() {
  const k = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY || "";
  return k.length >= 32 && !k.includes("placeholder");
}

const ClerkProviders = dynamic(() => import("@/components/providers/ClerkProviders"), {
  ssr: false,
});

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

  const core = (
    <QueryClientProvider client={client}>
      <AuthProvider>{children}</AuthProvider>
    </QueryClientProvider>
  );

  if (!clerkEnabled()) {
    return core;
  }

  return <ClerkProviders>{core}</ClerkProviders>;
}
