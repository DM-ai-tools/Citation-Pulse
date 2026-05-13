"use client";

import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { engineTitle } from "@/lib/engineDisplay";
import type { MatrixCell } from "@/types/scan";

const ENGINE_SUB: Record<string, string> = {
  chatgpt: "OpenAI",
  claude: "Anthropic",
  perplexity: "Sonar",
  gemini: "Google AI",
};

function cellFor(cells: MatrixCell[], promptId: string, engine: string): MatrixCell | undefined {
  return cells.find((c) => c.promptId === promptId && c.engine === engine);
}

function ReportMatrixCell({ cell, mode }: { cell: MatrixCell | undefined; mode: "live" | "final" }) {
  const st = cell?.status ?? "queued";
  const box = "flex min-h-[52px] w-full min-w-0 max-w-full flex-col items-center justify-center rounded-lg px-0.5 py-1 text-center sm:min-h-14 sm:px-1";
  if (st === "running") {
    return (
      <div className={cn(box, "border-2 border-dashed border-brand-primary bg-tr-pale")}>
        <Loader2 className="h-4 w-4 shrink-0 animate-spin text-brand-primary" />
      </div>
    );
  }
  if (st === "queued") {
    return (
      <div className={cn(box, "border border-tr-line bg-white")}>
        <span className="h-2 w-2 shrink-0 rounded-full bg-tr-line" />
      </div>
    );
  }
  if (st === "cited") {
    const pos = cell?.position;
    const top = pos === 1;
    return (
      <div
        className={cn(
          box,
          "cursor-pointer font-display text-[9px] font-extrabold transition hover:scale-[1.02] sm:text-[11.5px] sm:hover:scale-[1.04]",
          top ? "bg-[#1FB36B] text-white" : "bg-[#8EE5B7] text-[#14512f]",
        )}
      >
        <span className="leading-tight">cited</span>
        {mode === "final" && pos != null && (
          <small className="mt-0.5 text-[8px] font-semibold uppercase leading-tight opacity-85 sm:text-[9.5px]">
            pos {pos}
          </small>
        )}
      </div>
    );
  }
  if (st === "comp") {
    return (
      <div
        className={cn(
          box,
          "cursor-pointer bg-tr-landingOrange font-display text-[9px] font-extrabold text-white transition hover:scale-[1.02] sm:text-[11.5px] sm:hover:scale-[1.04]",
        )}
      >
        <span className="leading-tight">comp</span>
        <small className="mt-0.5 line-clamp-2 text-[8px] font-semibold uppercase leading-tight opacity-95 sm:text-[9.5px]">
          competitor
        </small>
      </div>
    );
  }
  if (st === "error") {
    const hint = cell?.errorMessage?.trim();
    return (
      <div
        className={cn(
          box,
          "cursor-default border border-slate-400 bg-slate-600 font-display text-[9px] font-extrabold text-white",
        )}
        title={hint || "Engine run failed"}
      >
        <span className="leading-tight">error</span>
        <small className="mt-0.5 line-clamp-2 text-[8px] font-semibold uppercase leading-tight opacity-95 sm:text-[9.5px]">
          run failed
        </small>
      </div>
    );
  }
  return (
    <div
      className={cn(
        box,
        "cursor-pointer bg-[#E74C3C] font-display text-[9px] font-extrabold text-white transition hover:scale-[1.02] sm:text-[11.5px] sm:hover:scale-[1.04]",
      )}
    >
      <span className="leading-tight">none</span>
      <small className="mt-0.5 line-clamp-2 text-[8px] font-semibold uppercase leading-tight opacity-95 sm:text-[9.5px]">
        not cited
      </small>
    </div>
  );
}

function LegacyMatrixTile({ cell, mode }: { cell: MatrixCell | undefined; mode: "live" | "final" }) {
  const st = cell?.status ?? "queued";
  const tile =
    "flex min-h-[52px] w-full min-w-0 max-w-full flex-col items-center justify-center rounded-lg p-1 text-center sm:min-h-[60px] sm:p-2";
  if (st === "running") {
    return (
      <div className={cn(tile, "border-2 border-dashed border-[#7CD6A8] bg-[#ECFAF2]")}>
        <Loader2 className="h-4 w-4 shrink-0 animate-spin text-brand-primary" />
      </div>
    );
  }
  if (st === "queued") {
    return <div className={cn(tile, "border border-slate-200 bg-slate-100")} />;
  }
  if (st === "cited") {
    const pos = cell?.position;
    const top = pos === 1;
    return (
      <div className={cn(tile, top ? "bg-emerald-500" : "bg-emerald-400", "text-white")}>
        <span className="text-[8px] font-bold uppercase tracking-wide sm:text-[10px]">cited</span>
        {mode === "final" && pos != null && (
          <span className="mt-0.5 text-[8px] font-bold uppercase leading-tight tracking-wider sm:text-[9px]">
            pos {pos}
          </span>
        )}
      </div>
    );
  }
  if (st === "comp") {
    return (
      <div className={cn(tile, "bg-amber-500 text-white")}>
        <span className="text-[8px] font-bold uppercase tracking-wide sm:text-[10px]">comp</span>
        <span className="mt-0.5 line-clamp-2 text-[8px] font-semibold uppercase leading-tight opacity-95 sm:text-[9px]">
          competitor
        </span>
      </div>
    );
  }
  if (st === "error") {
    const hint = cell?.errorMessage?.trim();
    return (
      <div className={cn(tile, "border border-slate-500 bg-slate-600 text-white")} title={hint || "Engine run failed"}>
        <span className="text-[8px] font-bold uppercase tracking-wide sm:text-[10px]">error</span>
        <span className="mt-0.5 line-clamp-2 text-[8px] font-semibold uppercase leading-tight sm:text-[9px]">
          run failed
        </span>
      </div>
    );
  }
  return (
    <div className={cn(tile, "bg-red-500 text-white")}>
      <span className="text-[8px] font-bold uppercase tracking-wide sm:text-[10px]">none</span>
      <span className="mt-0.5 line-clamp-2 text-[8px] font-semibold uppercase leading-tight sm:text-[9px]">
        not cited
      </span>
    </div>
  );
}

export function CitationHeatmap({
  prompts,
  engines,
  cells,
  mode,
  visual = "tiles",
  title,
  layerLabel,
  layout = "default",
}: {
  prompts: { id: string; text: string }[];
  engines: string[];
  cells: MatrixCell[];
  mode: "live" | "final";
  visual?: "tiles" | "compact";
  title?: string;
  layerLabel?: string | null;
  /** `report` matches full-report HTML mock (grid, card chrome). */
  layout?: "default" | "report";
}) {
  /** Fluid columns: prompt column shares space with engines; minmax(0,1fr) allows shrink without horizontal scroll. */
  const colTemplate =
    engines.length > 0
      ? `minmax(72px, 1.25fr) repeat(${engines.length}, minmax(0, 1fr))`
      : "minmax(0, 1fr)";

  const engineColPct = engines.length > 0 ? (100 - 30) / engines.length : 0;

  const headerTitle =
    title !== undefined ? (
      <div
        className={cn(
          "flex flex-wrap items-center justify-between gap-2 border-b border-tr-line",
          layout === "report" ? "px-[22px] py-[18px]" : "border-slate-100 px-5 py-3",
        )}
      >
        <h3
          className={cn(
            "font-display font-extrabold uppercase tracking-wide text-tr-navy",
            layout === "report" ? "text-sm" : "text-[11px] tracking-[0.2em]",
          )}
        >
          {title}
          {layerLabel ? (
            <span className="text-tr-mute"> — &quot;{layerLabel.toUpperCase()}&quot;</span>
          ) : null}
        </h3>
        <p className={cn("text-xs", layout === "report" ? "text-tr-mute" : "text-slate-500")}>
          {prompts.length} prompts · {engines.length} engine layers
        </p>
      </div>
    ) : null;

  if (layout === "report" && visual === "tiles") {
    return (
      <div className="overflow-hidden rounded-[18px] border border-tr-line bg-white shadow-[0_8px_30px_rgba(10,37,64,0.06)]">
        {headerTitle}
        <div className="min-h-[200px] overflow-hidden bg-[#F4FCF7] p-3 sm:min-h-[280px] sm:p-[22px]">
          <div className="w-full min-w-0">
            <div className="mb-2 grid min-w-0 gap-1 px-0.5 sm:gap-2 sm:px-1.5" style={{ gridTemplateColumns: colTemplate }}>
              <div className="min-w-0" />
              {engines.map((e) => (
                <div key={e} className="min-w-0 pb-1.5 text-center sm:pb-2">
                  <p className="font-display text-[9px] font-extrabold uppercase leading-tight tracking-wide text-tr-navy sm:text-[10.5px]">
                    {engineTitle(e)}
                  </p>
                  <p className="mt-0.5 font-display text-[8px] font-semibold leading-tight text-tr-mute sm:text-[9.5px]">
                    {ENGINE_SUB[e] ?? ""}
                  </p>
                </div>
              ))}
            </div>
            {prompts.map((p) => (
              <div
                key={p.id}
                className="mb-1.5 grid min-w-0 gap-1 sm:gap-2"
                style={{ gridTemplateColumns: colTemplate }}
              >
                <div className="flex min-w-0 items-center rounded-lg border border-tr-line bg-white px-2 py-2 text-[11px] font-semibold leading-snug text-tr-navy sm:px-3.5 sm:py-3 sm:text-[13px]">
                  <span className="line-clamp-3 break-words">{p.text}</span>
                </div>
                {engines.map((e) => (
                  <div key={e} className="min-w-0">
                    <ReportMatrixCell cell={cellFor(cells, p.id, e)} mode={mode} />
                  </div>
                ))}
              </div>
            ))}
            <div className="mt-4 flex flex-wrap items-center gap-x-3.5 gap-y-2 rounded-[10px] border border-tr-line bg-white px-4 py-3 text-[11.5px] text-tr-body">
              <span className="inline-flex items-center gap-1.5">
                <span className="h-3.5 w-3.5 rounded bg-[#1FB36B]" /> Brand cited (top)
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="h-3.5 w-3.5 rounded bg-[#8EE5B7]" /> Brand cited (lower)
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="h-3.5 w-3.5 rounded bg-tr-landingOrange" /> Competitor cited only
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="h-3.5 w-3.5 rounded bg-[#E74C3C]" /> Brand &amp; comp absent
              </span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-card">
      {headerTitle}
      <div className="overflow-hidden">
        <table className="w-full table-fixed border-collapse text-sm">
          <colgroup>
            {engines.length > 0 ? (
              <>
                <col style={{ width: "30%" }} />
                {engines.map((e) => (
                  <col key={e} style={{ width: `${engineColPct}%` }} />
                ))}
              </>
            ) : (
              <col style={{ width: "100%" }} />
            )}
          </colgroup>
          <thead>
            <tr className="border-b border-slate-100 bg-white">
              <th className="min-w-0 bg-white px-2 py-2 text-left text-[9px] font-bold uppercase tracking-wider text-slate-400 sm:px-4 sm:py-3 sm:text-[10px]" />
              {engines.map((e) => (
                <th key={e} className="min-w-0 px-0.5 py-2 text-center align-bottom sm:px-2 sm:py-3">
                  <p className="text-[8px] font-bold uppercase leading-tight tracking-wide text-tr-navy sm:text-[10px] sm:tracking-[0.18em]">
                    {engineTitle(e)}
                  </p>
                  <p className="mt-0.5 text-[7px] font-semibold uppercase leading-tight text-slate-400 sm:text-[9px] sm:tracking-[0.2em]">
                    {ENGINE_SUB[e] ?? ""}
                  </p>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {prompts.map((p) => (
              <tr key={p.id} className="border-b border-slate-50 last:border-0">
                <td className="min-w-0 bg-white px-2 py-2 align-middle text-[11px] font-medium leading-snug text-tr-navy sm:px-4 sm:text-sm">
                  <span className="line-clamp-3 break-words">{p.text}</span>
                </td>
                {engines.map((e) => {
                  const c = cellFor(cells, p.id, e);
                  return (
                    <td key={e} className="min-w-0 px-0.5 py-1.5 align-middle sm:px-2 sm:py-2">
                      {visual === "tiles" ? (
                        <LegacyMatrixTile cell={c} mode={mode} />
                      ) : (
                        <div className="text-center text-[9px] font-semibold text-slate-600 sm:text-[10px]">
                          {c?.status ?? "—"}
                        </div>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {visual === "tiles" && (
        <div className="flex flex-wrap gap-x-5 gap-y-2 border-t border-slate-100 bg-slate-50/70 px-5 py-3 text-[11px] font-medium text-slate-600">
          <span className="flex items-center gap-1.5">
            <span className="h-3 w-3 rounded bg-emerald-500" /> Brand cited (top)
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-3 w-3 rounded bg-emerald-400" /> Brand cited (lower)
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-3 w-3 rounded bg-amber-500" /> Competitor cited only
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-3 w-3 rounded bg-red-500" /> Brand &amp; comp absent
          </span>
        </div>
      )}
    </div>
  );
}
