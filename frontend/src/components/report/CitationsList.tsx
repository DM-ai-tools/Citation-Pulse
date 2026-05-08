"use client";

import { useMemo } from "react";
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

function hostFor(url: string): string {
  try {
    return new URL(url).host.replace(/^www\./, "");
  } catch {
    return url.slice(0, 60);
  }
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
  title = "Citations Found",
}: {
  cells: MatrixCell[];
  engineFilter?: string | null;
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
    return [...byEngine.values()].map((g) => {
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
  }, [cells, engineFilter]);

  const totalUrls = groups.reduce((acc, g) => acc + g.citations.length, 0);

  if (totalUrls === 0) {
    return (
      <div className="overflow-hidden rounded-[18px] border border-tr-line bg-white shadow-[0_8px_30px_rgba(10,37,64,0.06)]">
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
    <div className="overflow-hidden rounded-[18px] border border-tr-line bg-white shadow-[0_8px_30px_rgba(10,37,64,0.06)]">
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

      <div className="divide-y divide-tr-line">
        {groups.map((g) => (
          <section key={g.engine} className="px-[22px] py-4">
            <header className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
              <h4 className="font-display text-sm font-bold text-tr-navy">{engineTitle(g.engine)}</h4>
              <p className="text-[11px] uppercase tracking-wide text-tr-mute">
                {g.totalCount} total
                {g.brandCount > 0 && (
                  <span className="ml-2 text-[#14653e]">· {g.brandCount} brand</span>
                )}
                {g.compCount > 0 && (
                  <span className="ml-2 text-tr-landingOrange">· {g.compCount} competitor</span>
                )}
                {g.neutralCount > 0 && <span className="ml-2">· {g.neutralCount} neutral</span>}
              </p>
            </header>
            <ul className="space-y-1.5">
              {g.citations.slice(0, 8).map((c, i) => {
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
                      <span className="block truncate text-[11px] text-tr-mute group-hover:underline">
                        {c.url}
                      </span>
                    </a>
                    <ExternalLink className="mt-0.5 h-3.5 w-3.5 shrink-0 text-tr-mute" />
                  </li>
                );
              })}
            </ul>
            {g.citations.length > 8 && (
              <p className="mt-2 text-[11px] text-tr-mute">
                +{g.citations.length - 8} more citations
              </p>
            )}
          </section>
        ))}
      </div>
    </div>
  );
}
