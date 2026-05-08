import { pct } from "@/lib/format";
import type { ReportData } from "@/types/report";

export function Breakdown({ breakdown }: { breakdown: ReportData["breakdown"] }) {
  if (!breakdown) return null;
  const rows = [
    { label: "Brand", v: breakdown.brand_share },
    { label: "Competitor", v: breakdown.competitor_share },
    { label: "Third party", v: breakdown.third_party_share },
    { label: "Neutral", v: breakdown.neutral_share },
  ];
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {rows.map((r) => (
        <div key={r.label} className="rounded-xl border border-slate-100 bg-white p-4 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{r.label}</p>
          <p className="mt-1 text-2xl font-bold text-ink-900">{pct(r.v, 1)}</p>
          <div className="mt-2 h-2 rounded-full bg-slate-100">
            <div
              className="h-2 rounded-full bg-brand-primary"
              style={{ width: `${Math.min(100, r.v * 100)}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
