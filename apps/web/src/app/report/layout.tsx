import { RequireAuth } from "@/components/auth/RequireAuth";

export default function ReportLayout({ children }: { children: React.ReactNode }) {
  return <RequireAuth>{children}</RequireAuth>;
}
