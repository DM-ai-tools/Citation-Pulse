"use client";

import { useMemo, useState } from "react";
import { ExternalLink } from "lucide-react";
import { cn } from "@/lib/utils";
import { engineTitle } from "@/lib/engineDisplay";
import type { CellCitation, MatrixCell } from "@/types/scan";

type Group = {
  engine: string;
  totalCount: number;
  brandCount: number;
  compCount: number;
  neutralCount: number;
  citations: CellCitation[];
};

const OWNERSHIP_BADGE: Record<string, { label: string; cls: string }> = {
  brand: { label: "BRAND", cls: "bg-[#1FB36B] text-white" },
  competitor: { label: "COMPETITOR", cls: "bg-tr-landingOrange text-white" },
  neutral: { label: "NEUTRAL", cls: "bg-tr-pale text-tr-navy" },
};

const CITATION_PREVIEW = 8;

function hostFor(url: string): string {
  try {
    return new URL(url).host.replace(/^www\./, "");
  } catch {
    return url.slice(0, 60);
  }
}

function CitationRow({ c, i }: { c: CellCitation; i: number }) {
  const badge = OWNERSHIP_BADGE[c.ownership] ?? OWNERSHIP_BADGE.neutral!;
  return (
    <li
      key={`${c.url}-${i}`}
      className="flex items-start gap-2 rounded-md px-2 py-1.5 hover:bg-tr-pale/50"
    >
      <span
        className={cn(
          "mt-0.5 shrink-0 rounded px-1.5 py-0.5 text-[9px] font-extrabold uppercase tracking-wider",
          badge.cls,
        )}
      >
        {badge.label}
      </span>
      <a
        href={c.url}
        target="_blank"
        rel="noreferrer noopener"
        className="group min-w-0 flex-1 text-sm text-tr-navy transition hover:text-brand-primary"
      >
        <span className="block truncate font-medium">{hostFor(c.url)}</span>
        <span className="block truncate text-[11px] text-tr-mute group-hover:underline">{c.url}</span>
      </a>
      <ExternalLink className="mt-0.5 h-3.5 w-3.5 shrink-0 text-tr-mute" />
    </li>
  );
}

function CitationGroupSection({ g, useEngineGrid }: { g: Group; useEngineGrid: boolean }) {
  const [expanded, setExpanded] = useState(false);
  const total = g.citations.length;
  const rest = Math.max(0, total - CITATION_PREVIEW);
  const visible = expanded || rest === 0 ? g.citations : g.citations.slice(0, CITATION_PREVIEW);

  return (
    <section
      key={g.engine}
      className={cn(
        useEngineGrid
          ? "min-w-0 w-full max-w-full rounded-xl border border-tr-line bg-tr-pale/25 p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.65)]"
          : "px-[22px] py-4",
      )}
    >
      <header className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
        <h4 className="font-display text-sm font-bold text-tr-navy">{engineTitle(g.engine)}</h4>
        <p className="text-[11px] uppercase tracking-wide text-tr-mute">
          {g.totalCount} total
          {g.brandCount > 0 && <span className="ml-2 text-[#14653e]">· {g.brandCount} brand</span>}
          {g.compCount > 0 && (
            <span className="ml-2 text-tr-landingOrange">· {g.compCount} competitor</span>
          )}
          {g.neutralCount > 0 && <span className="ml-2">· {g.neutralCount} neutral</span>}
        </p>
      </header>
      <ul className="space-y-1.5">
        {visible.map((c, i) => (
          <CitationRow key={c.url} c={c} i={i} />
        ))}
      </ul>
      {rest > 0 ? (
        <button
          type="button"
          className="mt-2.5 rounded-lg px-2 py-1.5 text-left text-[11px] font-semibold text-brand-primary underline decoration-brand-primary/40 underline-offset-2 hover:bg-tr-pale/60 hover:decoration-brand-primary"
          onClick={() => setExpanded((v) => !v)}
        >
          {expanded
            ? "Show fewer citations"
            : `Show ${rest} more citation${rest === 1 ? "" : "s"} (${total} total)`}
        </button>
      ) : null}
    </section>
  );
}

/**
 * Surfaces every URL the AI engines actually cited, grouped by engine.
 *
 * Designed for the case where the brand isn't being cited yet (score=0): the
 * heatmap is mostly empty, but the user still wants to see *what is being
 * cited* — typically competitors and directories — so they can plan content.
 */
export function CitationsList({
  cells,
  engineFilter,
  engines,
  title = "Citations Found",
}: {
  cells: MatrixCell[];
  engineFilter?: string | null;
  /** When set (e.g. scan engines), citation groups follow this order so the 2×2 grid matches the heatmap. */
  engines?: string[];
  title?: string;
}) {
  const groups = useMemo<Group[]>(() => {
    const filtered = engineFilter ? cells.filter((c) => c.engine === engineFilter) : cells;
    const byEngine = new Map<string, Group>();
    for (const cell of filtered) {
      const list = cell.citations ?? [];
      const g =
        byEngine.get(cell.engine) ??
        ({
          engine: cell.engine,
          totalCount: 0,
          brandCount: 0,
          compCount: 0,
          neutralCount: 0,
          citations: [],
        } satisfies Group);
      g.totalCount += cell.citationsCount ?? list.length;
      for (const c of list) {
        if (c.ownership === "brand") g.brandCount++;
        else if (c.ownership === "competitor") g.compCount++;
        else g.neutralCount++;
        g.citations.push(c);
      }
      byEngine.set(cell.engine, g);
    }
    // Dedupe by URL within each engine, keep best ownership rank.
    const rank: Record<string, number> = { brand: 0, competitor: 1, neutral: 2 };
    const deduped = [...byEngine.values()].map((g) => {
      const seen = new Map<string, CellCitation>();
      for (const c of g.citations) {
        const prev = seen.get(c.url);
        if (!prev || (rank[c.ownership] ?? 9) < (rank[prev.ownership] ?? 9)) {
          seen.set(c.url, c);
        }
      }
      g.citations = [...seen.values()];
      return g;
    });
    if (!engines?.length) return deduped;
    const order = new Map(engines.map((e, i) => [e, i]));
    return [...deduped].sort((a, b) => (order.get(a.engine) ?? 999) - (order.get(b.engine) ?? 999));
  }, [cells, engineFilter, engines]);

  const totalUrls = groups.reduce((acc, g) => acc + g.citations.length, 0);
  /** Two equal-width columns (2×2 for four engines) when showing every engine; flex parents need `min-w-0` upstream. */
  const useEngineGrid = !engineFilter && groups.length > 1;

  if (totalUrls === 0) {
    return (
      <div className="w-full min-w-0 max-w-none self-stretch overflow-hidden rounded-[18px] border border-tr-line bg-white shadow-[0_8px_30px_rgba(10,37,64,0.06)]">
        <div className="flex items-center justify-between border-b border-tr-line px-[22px] py-[18px]">
          <h3 className="font-display text-sm font-extrabold uppercase tracking-wide text-tr-navy">
            {title}
          </h3>
        </div>
        <p className="px-[22px] py-6 text-sm text-tr-mute">
          No citations were returned by the AI engines for this scan.
        </p>
      </div>
    );
  }

  return (
    <div className="w-full min-w-0 max-w-none self-stretch overflow-hidden rounded-[18px] border border-tr-line bg-white shadow-[0_8px_30px_rgba(10,37,64,0.06)]">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-tr-line px-[22px] py-[18px]">
        <h3 className="font-display text-sm font-extrabold uppercase tracking-wide text-tr-navy">
          {title}
        </h3>
        <p className="text-xs text-tr-mute">
          <strong className="text-tr-navy tabular-nums">{totalUrls}</strong> URLs across{" "}
          <strong className="text-tr-navy">{groups.length}</strong> engine
          {groups.length === 1 ? "" : "s"}
        </p>
      </div>

      <div
        className={cn(
          useEngineGrid
            ? "grid w-full min-w-0 max-w-none grid-cols-2 grid-flow-row items-stretch gap-x-4 gap-y-3 p-[18px] max-[440px]:grid-cols-1 sm:p-5"
            : "divide-y divide-tr-line",
        )}
      >
        {groups.map((g) => (
          <CitationGroupSection key={g.engine} g={g} useEngineGrid={useEngineGrid} />
        ))}
      </div>
    </div>
  );
}
