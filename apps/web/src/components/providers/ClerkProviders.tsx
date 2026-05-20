"use client";

import { ClerkProvider } from "@clerk/nextjs";

/** Loaded only when Clerk is configured — keeps @clerk out of the default bundle. */
export default function ClerkProviders({ children }: { children: React.ReactNode }) {
  return <ClerkProvider>{children}</ClerkProvider>;
}
