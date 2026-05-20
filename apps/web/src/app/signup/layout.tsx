import { AuthPageChrome } from "@/components/layout/AuthPageChrome";

export default function SignupLayout({ children }: { children: React.ReactNode }) {
  return <AuthPageChrome>{children}</AuthPageChrome>;
}
