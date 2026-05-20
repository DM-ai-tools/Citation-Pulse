import { AdminShell } from "@/components/admin/AdminShell";
import { RequireAdmin } from "@/components/auth/RequireAdmin";

export default function AdminPanelLayout({ children }: { children: React.ReactNode }) {
  return (
    <RequireAdmin>
      <AdminShell>{children}</AdminShell>
    </RequireAdmin>
  );
}