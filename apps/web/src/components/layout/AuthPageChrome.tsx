import Link from "next/link";
import { MarketingHeader } from "./MarketingHeader";
import { MarketingTopBar } from "./MarketingTopBar";

/** Marketing site header for login / signup (no sign-in or sign-out control on the right). */
export function AuthPageChrome({
  children,
  showAdminLoginLink = true,
}: {
  children: React.ReactNode;
  showAdminLoginLink?: boolean;
}) {
  return (
    <div className="flex min-h-screen flex-col bg-tr-page">
      <MarketingTopBar />
      <MarketingHeader authAction="empty" showNav={false} />
      <main className="flex flex-1 flex-col">
        <div className="flex flex-1 flex-col">{children}</div>
        {showAdminLoginLink ? (
          <p className="pb-8 text-center text-sm text-slate-500">
            <Link
              href="/admin/login"
              className="font-medium text-tr-navy/70 transition hover:text-tr-navy hover:underline"
            >
              Admin login
            </Link>
          </p>
        ) : null}
      </main>
    </div>
  );
}
