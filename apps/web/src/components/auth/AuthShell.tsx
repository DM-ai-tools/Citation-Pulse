import Link from "next/link";
import { TrafficRadiusLogo } from "@/components/shared/TrafficRadiusLogo";

export function AuthShell({
  title,
  subtitle,
  children,
  footer,
  showLogo = true,
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  /** Hide card logo when the page already shows Traffic Radius in the site header. */
  showLogo?: boolean;
}) {
  return (
    <div className="auth-grid-bg flex flex-1 items-center justify-center px-4 py-10">
      <div className="w-full max-w-[480px] rounded-2xl border border-slate-200/80 bg-white px-8 py-10 shadow-[0_8px_40px_rgba(15,40,28,0.08)] sm:px-10">
        {showLogo ? (
          <div className="mb-8 flex justify-center">
            <TrafficRadiusLogo variant="remote" className="h-[52px] w-auto sm:h-[56px]" />
          </div>
        ) : null}
        <h1 className="text-center font-display text-[2rem] font-bold leading-tight tracking-tight text-tr-navyDeep">
          {title}
        </h1>
        <p className="mt-2 text-center text-[15px] text-slate-500">{subtitle}</p>
        <div className="mt-8">{children}</div>
        {footer ? <div className="mt-8 text-center text-sm text-slate-600">{footer}</div> : null}
      </div>
    </div>
  );
}

export function AuthFooterLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link href={href} className="font-semibold text-[#7cb83a] hover:text-[#6fa832] hover:underline">
      {children}
    </Link>
  );
}
