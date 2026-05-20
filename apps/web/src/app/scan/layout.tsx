import { RequireAuth } from "@/components/auth/RequireAuth";

export default function ScanLayout({ children }: { children: React.ReactNode }) {
  return <RequireAuth>{children}</RequireAuth>;
}
