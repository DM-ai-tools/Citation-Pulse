import { cn } from "@/lib/utils";

const TR_LOGO_URL =
  "https://trafficradius.com.au/wp-content/uploads/2024/06/Traffic-Radius-Logo.png";

export function TrafficRadiusLogo({
  className,
  /** Use official Traffic Radius PNG from marketing site (matches HTML mock). */
  variant = "remote",
}: {
  className?: string;
  variant?: "remote" | "mark";
}) {
  if (variant === "remote") {
    return (
      // eslint-disable-next-line @next/next/no-img-element -- remote marketing asset; no Image optimization required
      <img
        src={TR_LOGO_URL}
        alt="Traffic Radius"
        width={200}
        height={46}
        className={cn("h-[46px] w-auto object-contain", className)}
      />
    );
  }

  return (
    <div className={cn("flex items-center gap-2", className)} aria-label="Traffic Radius">
      <svg viewBox="0 0 36 28" className="h-7 w-9 shrink-0" role="img" aria-hidden="true">
        <rect x="2" y="18" width="4" height="8" rx="1" fill="#16A34A" />
        <rect x="9" y="12" width="4" height="14" rx="1" fill="#16A34A" />
        <rect x="16" y="6" width="4" height="20" rx="1" fill="#16A34A" />
        <path d="M24 12 L34 6 L31 12 L34 12 L26 22 L29 16 L24 16 Z" fill="#F97316" />
      </svg>
      <div className="flex min-w-0 flex-col leading-none">
        <span className="font-display text-[15px] font-bold tracking-tight text-tr-navy">Traffic Radius</span>
        <span className="mt-0.5 text-[8px] font-medium italic tracking-tight text-slate-500">
          Growing Your Business The Smart Way!
        </span>
      </div>
    </div>
  );
}
