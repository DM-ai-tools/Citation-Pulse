"use client";

import { Fragment } from "react";
import { cn } from "@/lib/utils";
import { matrixCellScore } from "@/lib/matrixStats";
import type { MatrixCell } from "@/types/scan";

const ENGINE_HEAD: Record<string, string> = {
  chatgpt: "CHATGPT",
  claude: "CLAUDE",
  perplexity: "PERPLEX",
  gemini: "GEMINI",
};

function cellClass(p: number) {
  if (p >= 100) return "bg-[rgba(31,179,107,0.16)] text-[#14512f]";
  if (p >= 60) return "bg-[rgba(31,179,107,0.12)] text-[#14512f]";
  if (p > 0) return "bg-[rgba(248,165,27,0.16)] text-[#b87a14]";
  return "bg-[rgba(231,76,60,0.16)] text-[#b73121]";
}

const headCell =
  "border-b border-tr-line bg-[#F6FCF8] px-1.5 py-2 text-left font-display text-[9px] font-extrabold uppercase leading-tight tracking-wide text-tr-navy sm:px-2 sm:text-[10.5px]";
const headCellEngine = `${headCell} text-center`;
const bodyPrompt =
  "border-b border-tr-line px-1.5 py-2 text-left text-[11px] font-bold leading-snug text-tr-navy sm:px-2 sm:text-[12.5px]";
const bodyPct =
  "border-b border-tr-line px-1 py-2 text-center text-[11px] font-extrabold tabular-nums sm:px-2 sm:text-[12.5px]";

export function PromptEngineScoreMatrix({
  prompts,
  engines,
  cells,
  title = "Prompt × Engine Score Matrix",
}: {
  prompts: { id: string; text: string }[];
  engines: string[];
  cells: MatrixCell[];
  title?: string;
}) {
  const n = engines.length || 1;
  const gridTemplateColumns = `minmax(0, 1.35fr) repeat(${n}, minmax(0, 1fr))`;

  return (
    <div className="overflow-hidden rounded-[18px] border border-tr-line bg-white shadow-[0_8px_30px_rgba(10,37,64,0.06)]">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-tr-line px-[22px] py-[18px]">
        <h3 className="font-display text-sm font-extrabold uppercase tracking-wide text-tr-navy">{title}</h3>
        <p className="text-xs text-tr-mute">% cited</p>
      </div>
      <div className="min-w-0 overflow-hidden px-3 py-4 sm:px-[22px] sm:py-[22px]">
        <div
          className="grid w-full min-w-0 gap-x-0 border border-tr-line text-[10px] sm:gap-x-px sm:text-[12.5px]"
          style={{ gridTemplateColumns }}
        >
          <div className={headCell}>Prompt</div>
          {engines.map((e) => (
            <div key={e} className={headCellEngine}>
              <span className="block break-words">{ENGINE_HEAD[e] ?? e.toUpperCase()}</span>
            </div>
          ))}

          {prompts.map((p) => (
            <Fragment key={p.id}>
              <div className={cn(bodyPrompt, "min-w-0")}>
                <span className="line-clamp-2 break-words">{p.text}</span>
              </div>
              {engines.map((e) => {
                const c = cells.find((x) => x.promptId === p.id && x.engine === e);
                const v = matrixCellScore(c);
                return (
                  <div key={e} className={cn(bodyPct, "min-w-0", cellClass(v))}>
                    {v}%
                  </div>
                );
              })}
            </Fragment>
          ))}
        </div>
      </div>
    </div>
  );
}
