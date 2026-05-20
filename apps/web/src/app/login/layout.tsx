import { AuthPageChrome } from "@/components/layout/AuthPageChrome";

export default function LoginLayout({ children }: { children: React.ReactNode }) {
  return <AuthPageChrome>{children}</AuthPageChrome>;
}
