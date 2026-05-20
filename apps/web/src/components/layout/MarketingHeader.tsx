"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Phone } from "lucide-react";
import { Container } from "./Container";
import { CitationPulseMark } from "@/components/shared/BrandMark";
import { TrafficRadiusLogo } from "@/components/shared/TrafficRadiusLogo";
import { useAuth } from "@/contexts/AuthContext";
import { clearAuthSession } from "@/lib/authSession";
import { logout } from "@/services/auth";

const nav = [
  { href: "/landing#how", label: "How it works" },
  { href: "/landing#engines", label: "AI engines" },
  { href: "/landing#features", label: "What you get" },
];

export function MarketingHeader({
  authAction = "auto",
  showNav = true,
}: {
  authAction?: "auto" | "empty";
  /** Hide center nav links (e.g. login / signup). */
  showNav?: boolean;
}) {
  const router = useRouter();
  const { user, signOut } = useAuth();

  async function onSignOut() {
    await logout().catch(() => undefined);
    signOut();
    clearAuthSession();
    router.push("/login");
  }

  return (
    <header className="sticky top-0 z-[100] border-b border-tr-line bg-[#F4FCF7] shadow-[0_1px_3px_rgba(16,58,38,0.08)]">
      <Container className="flex h-[76px] items-center justify-between gap-4">
        <div className="flex shrink-0 items-center gap-3.5">
          <a href="https://trafficradius.com.au/" target="_blank" rel="noopener noreferrer">
            <TrafficRadiusLogo variant="remote" />
          </a>
          <span className="hidden h-[34px] w-px bg-tr-line sm:block" />
          <CitationPulseMark tagline="AI VISIBILITY · GEO PORTFOLIO" className="hidden min-w-0 sm:block" />
        </div>
        {showNav ? (
          <nav className="hidden flex-1 justify-center gap-8 md:flex lg:gap-[30px]">
            {nav.map((n) => (
              <Link
                key={n.href}
                href={n.href}
                className="text-sm font-semibold text-tr-navy transition hover:text-brand-primary"
              >
                {n.label}
              </Link>
            ))}
          </nav>
        ) : (
          <div className="flex-1" aria-hidden />
        )}
        <div className="flex items-center gap-3 lg:gap-4">
          <a
            href="tel:1300852340"
            className="hidden items-center gap-2 font-display text-[15px] font-bold text-tr-navy lg:flex"
          >
            <span className="flex h-[34px] w-[34px] items-center justify-center rounded-full bg-tr-pale text-tr-teal">
              <Phone className="h-[15px] w-[15px]" strokeWidth={2.5} />
            </span>
            1300 852 340
          </a>
          {authAction === "empty" ? (
            <span className="hidden min-w-[4.5rem] sm:inline" aria-hidden />
          ) : user ? (
            <button
              type="button"
              onClick={() => void onSignOut()}
              className="text-sm font-semibold text-tr-navy transition hover:text-brand-primary"
            >
              Sign out
            </button>
          ) : (
            <Link
              href="/login"
              className="text-sm font-semibold text-tr-navy transition hover:text-brand-primary"
            >
              Sign in
            </Link>
          )}
        </div>
      </Container>
    </header>
  );
}
