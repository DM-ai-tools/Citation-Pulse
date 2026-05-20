import { AuthPageChrome } from "@/components/layout/AuthPageChrome";

export default function AdminLoginLayout({ children }: { children: React.ReactNode }) {
  return <AuthPageChrome showAdminLoginLink={false}>{children}</AuthPageChrome>;
}
