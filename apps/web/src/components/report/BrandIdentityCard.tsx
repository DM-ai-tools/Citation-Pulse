import { CheckCircle2 } from "lucide-react";

export function BrandIdentityCard({
  brandName,
  urlHost,
  region,
  description,
}: {
  brandName: string;
  urlHost: string;
  region?: string;
  description?: string;
}) {
  const initial = (brandName?.[0] ?? "?").toUpperCase();
  const meta = [urlHost, region, description].filter(Boolean).join(" · ");
  return (
    <div className="flex items-center gap-3 rounded-2xl border border-tr-navy/10 bg-tr-navy/[0.04] px-4 py-3 shadow-sm">
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-brand-primary text-base font-bold text-white">
        {initial}
      </span>
      <div className="min-w-0 flex-1">
        <p className="flex items-center gap-1.5 text-sm font-bold text-tr-navy">
          {brandName}
          <CheckCircle2 className="h-4 w-4 text-emerald-500" aria-label="verified" />
          <span className="text-xs font-medium text-emerald-600">verified</span>
        </p>
        {meta && <p className="truncate text-xs text-slate-500">{meta}</p>}
      </div>
    </div>
  );
}
