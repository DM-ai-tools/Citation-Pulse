import { cn } from "@/lib/utils";
import type { CellStatus } from "@/types/scan";

const map: Record<CellStatus, { className: string; label: string }> = {
  cited: { className: "bg-emerald-50 text-emerald-900 border-emerald-200", label: "Cited" },
  comp: { className: "bg-amber-50 text-amber-900 border-amber-200", label: "Competitor" },
  none: { className: "bg-red-50 text-red-800 border-red-200", label: "Gap" },
  error: { className: "bg-slate-100 text-slate-900 border-slate-300", label: "Run failed" },
  running: { className: "bg-slate-100 text-slate-800 border-slate-200", label: "Running" },
  queued: { className: "bg-slate-50 text-slate-600 border-slate-200", label: "Queued" },
};

export function StatusPill({ status }: { status: CellStatus }) {
  const m = map[status] || map.none;
  return (
    <span className={cn("inline-flex rounded-full border px-2 py-0.5 text-[11px] font-semibold", m.className)}>
      {m.label}
    </span>
  );
}
