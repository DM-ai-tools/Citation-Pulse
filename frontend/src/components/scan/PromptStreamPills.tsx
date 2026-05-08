"use client";

import { cn } from "@/lib/utils";
import { engineStreamLabel } from "@/lib/engineDisplay";
import type { MatrixCell } from "@/types/scan";
import type { ScanSnapshot } from "@/types/scan";

function cellFor(cells: MatrixCell[], promptId: string, engine: string) {
  return cells.find((c) => c.promptId === promptId && c.engine === engine);
}

function promptShort(text: string, max = 32) {
  const t = text.trim();
  return t.length <= max ? t : `${t.slice(0, max)}…`;
}

export function PromptStreamPills({ data }: { data: ScanSnapshot }) {
  const items: { key: string; label: string; status: MatrixCell["status"] }[] = [];
  for (const p of data.prompts) {
    for (const e of data.engines) {
      const c = cellFor(data.matrix.cells, p.id, e);
      const st = c?.status ?? "queued";
      const eng = engineStreamLabel(e);
      items.push({
        key: `${p.id}-${e}`,
        label: `${promptShort(p.text)} · ${eng}`,
        status: st,
      });
    }
  }
  const done = items.filter((i) => i.status === "cited" || i.status === "comp" || i.status === "none").length;
  const run = items.filter((i) => i.status === "running").length;
  const q = items.filter((i) => i.status === "queued").length;
  const nP = data.prompts.length;
  const nE = data.engines.length;

  return (
    <div className="rounded-xl bg-[#F6FCF8] px-5 py-4">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2 text-[12.5px] text-tr-mute">
        <p>
          <span className="font-display text-[13px] font-extrabold uppercase tracking-wide text-tr-navy">
            Prompt Stream{" "}
            <span className="font-medium normal-case tracking-normal text-tr-mute">
              · {nP} prompts × {nE} engines
            </span>
          </span>
        </p>
        <span>
          {done} done · {run} running · {q} queued
        </span>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {items.map((it) => (
          <span
            key={it.key}
            className={cn(
              "inline-flex max-w-[280px] items-center rounded-full px-2.5 py-1 font-display text-xs font-semibold leading-tight",
              it.status === "cited" || it.status === "comp" || it.status === "none"
                ? "bg-[rgba(31,179,107,0.12)] text-[#14653e]"
                : it.status === "running"
                  ? "border border-dashed border-brand-primary bg-brand-primary/[0.18] text-tr-teal animate-landing-pulse"
                  : "border border-tr-line bg-white text-tr-mute",
            )}
          >
            <span className="truncate">
              {it.label}
              {it.status === "cited" || it.status === "comp" || it.status === "none" ? " ✓" : ""}
              {it.status === "running" ? " ⟳" : ""}
            </span>
          </span>
        ))}
      </div>
    </div>
  );
}
