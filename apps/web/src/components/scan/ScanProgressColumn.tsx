"use client";

import Link from "next/link";
import { EngineProgressRow } from "./EngineProgressRow";
import { PromptStreamPills } from "./PromptStreamPills";
import { scanReadyForReport } from "@/lib/matrixStats";
import type { ScanSnapshot } from "@/types/scan";

export function ScanProgressColumn({ data, scanId }: { data: ScanSnapshot; scanId: string }) {
  const nP = data.prompts.length;
  const nE = data.engines.length;
  const total = nP * nE;
  let done = 0;
  for (const eng of data.engines) {
    const pe = data.progress.per_engine[eng];
    const t = pe && pe.total > 0 ? pe.total : nP;
    done += Math.min(pe?.done ?? 0, t);
  }
  const overallDone = Math.min(done, total);
  const pct = total ? Math.round((100 * overallDone) / total) : 0;
  const canOpenReport = scanReadyForReport(
    data.status,
    data.prompts,
    data.engines,
    data.matrix.cells,
  );
  const brand = data.brand?.name ?? data.submitted_url.replace(/^https?:\/\//, "").split("/")[0] ?? "your brand";
  const root = data.submitted_url.replace(/^https?:\/\//, "").split("/")[0];
  const etaSec = Math.min(120, 12 + total * 3);

  return (
    <div className="rounded-[18px] border border-tr-line bg-white p-8 shadow-[0_12px_40px_rgba(10,37,64,0.08)] pb-7 pt-8 sm:px-8">
      <div className="panel-header">
        <h2 className="font-display text-[28px] font-black leading-[1.15] tracking-[-0.7px] text-tr-navy">
          Scanning {brand}
        </h2>
        <span className="scan-under-mark block" aria-hidden />
        <p className="max-w-[560px] text-sm leading-relaxed text-tr-body">
          We&apos;re firing {nP} buyer {nP === 1 ? "question" : "questions"} at {nE} AI engines ({total} calls).
          Citations stream in as each engine resolves, with live progress by engine.
        </p>
      </div>

      <div className="my-6 flex flex-wrap gap-2.5">
        {(
          [
            ["URL", root],
            ["LOCALE", data.locale],
            ["PROMPTS", String(nP)],
            ["ENGINES", String(nE)],
            ["ETA", `~${etaSec} seconds`],
          ] as const
        ).map(([tag, val]) => (
          <div
            key={tag}
            className="inline-flex items-center gap-2 rounded-lg bg-tr-pale px-3 py-2 text-[13px] text-tr-navy"
          >
            <span className="rounded px-1.5 py-0.5 font-display text-[9.5px] font-extrabold uppercase tracking-wide text-tr-teal bg-white">
              {tag}
            </span>
            <b className="font-display font-bold">{val}</b>
          </div>
        ))}
      </div>

      <div className="mb-6 rounded-xl bg-[#F6FCF8] px-5 py-4">
        <div className="mb-2.5 flex items-baseline justify-between text-[13px]">
          <b className="font-display text-sm font-bold text-tr-navy">Overall progress</b>
          <span className="text-tr-body">
            {overallDone} of {total} citation checks complete
          </span>
        </div>
        <div className="h-3 overflow-hidden rounded-full bg-tr-pale">
          <div
            className="h-full rounded-full bg-gradient-to-r from-[#1fb36b] to-[#32d882] transition-[width] duration-300"
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      <div className="mb-6">
        <p className="mb-3 font-display text-[13px] font-bold uppercase tracking-wide text-tr-navy">
          Per-engine progress
        </p>
        <div className="flex flex-col gap-2.5">
          {data.engines.map((eng) => {
            const pe = data.progress.per_engine[eng];
            const rowTotal = pe && pe.total > 0 ? pe.total : nP;
            const rowDone = Math.min(pe?.done ?? 0, rowTotal);
            return <EngineProgressRow key={eng} engine={eng} done={rowDone} total={rowTotal} />;
          })}
        </div>
      </div>

      <PromptStreamPills data={data} />

      {canOpenReport ? (
        <div className="mt-6 flex justify-center">
          <Link
            href={`/report/${scanId}`}
            className="inline-flex items-center justify-center rounded-xl bg-gradient-to-r from-[#1fb36b] to-[#32d882] px-6 py-3 font-display text-sm font-bold text-white shadow-md hover:opacity-95"
          >
            View citation report →
          </Link>
        </div>
      ) : null}

      <p className="mt-6 text-center text-[11.5px] text-tr-mute">
        Your citation matrix is filling in on the right →{" "}
        <Link href={`/report/${scanId}`} className="font-bold text-tr-teal hover:underline">
          open full report
        </Link>{" "}
        after the scan to see each AI answer in detail.
      </p>
    </div>
  );
}

