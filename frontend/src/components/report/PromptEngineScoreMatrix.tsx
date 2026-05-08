"use client";

import { cn } from "@/lib/utils";
import type { MatrixCell } from "@/types/scan";

const ENGINE_HEAD: Record<string, string> = {
  chatgpt: "CHATGPT",
  claude: "CLAUDE",
  perplexity: "PERPLEX",
  gemini: "GEMINI",
};

function pctForCell(c: MatrixCell | undefined): number {
  if (!c) return 0;
  if (c.status === "cited") return 100;
  if (c.status === "comp") return 0;
  if (c.status === "running") return 0;
  if (c.status === "queued") return 0;
  return 0;
}

function cellClass(p: number) {
  if (p >= 100) return "bg-[rgba(31,179,107,0.16)] text-[#14512f]";
  if (p >= 60) return "bg-[rgba(31,179,107,0.12)] text-[#14512f]";
  if (p > 0) return "bg-[rgba(248,165,27,0.16)] text-[#b87a14]";
  return "bg-[rgba(231,76,60,0.16)] text-[#b73121]";
}

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
  return (
    <div className="overflow-hidden rounded-[18px] border border-tr-line bg-white shadow-[0_8px_30px_rgba(10,37,64,0.06)]">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-tr-line px-[22px] py-[18px]">
        <h3 className="font-display text-sm font-extrabold uppercase tracking-wide text-tr-navy">{title}</h3>
        <p className="text-xs text-tr-mute">% cited</p>
      </div>
      <div className="overflow-x-auto p-[22px]">
        <table className="mtx w-full min-w-[520px] border-separate border-spacing-0 text-[12.5px]">
          <thead>
            <tr>
              <th className="border-b border-tr-line bg-[#F6FCF8] px-3 py-2.5 text-left font-display text-[10.5px] font-extrabold uppercase tracking-wide text-tr-navy">
                Prompt
              </th>
              {engines.map((e) => (
                <th
                  key={e}
                  className="border-b border-tr-line bg-[#F6FCF8] px-3 py-2.5 text-center font-display text-[10.5px] font-extrabold uppercase tracking-wide text-tr-navy"
                >
                  {ENGINE_HEAD[e] ?? e.toUpperCase()}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {prompts.map((p) => (
              <tr key={p.id}>
                <td className="border-b border-tr-line px-3 py-2.5 text-left font-bold text-tr-navy">
                  <span className="line-clamp-2">{p.text}</span>
                </td>
                {engines.map((e) => {
                  const c = cells.find((x) => x.promptId === p.id && x.engine === e);
                  const v = pctForCell(c);
                  return (
                    <td
                      key={e}
                      className={cn(
                        "border-b border-tr-line px-3 py-2.5 text-center font-extrabold tabular-nums",
                        cellClass(v),
                      )}
                    >
                      {v}%
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
