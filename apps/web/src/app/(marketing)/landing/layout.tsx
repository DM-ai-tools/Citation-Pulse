import { RequireAuth } from "@/components/auth/RequireAuth";

export default function LandingLayout({ children }: { children: React.ReactNode }) {
  return <RequireAuth>{children}</RequireAuth>;
}
