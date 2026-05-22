"use client";

import { useMemo } from "react";
import { ExternalLink } from "lucide-react";
import { Spinner } from "@/components/primitives";
import { competitorLevelLabel } from "@/lib/competitorLevelLabels";
import { engineTitle } from "@/lib/engineDisplay";
import { mergeVisibilityWithMatrix, visibilityFromMatrixCells } from "@/lib/matrixCompetitorCitations";
import type { MatrixRosterEntry } from "@/lib/matrixCompetitorCitations";
import { cn } from "@/lib/utils";
import type { CompetitorCitationVisibility, EngineCitationHit, RankedCompetitorVisibility } from "@/types/competitorVisibility";
import type { MatrixCell } from "@/types/scan";

function truncatePrompt(text: string, max = 52): string {
  const t = text.trim();
  if (t.length <= max) return t;
  return `${t.slice(0, max - 1)}…`;
}

function domainHref(domain: string) {
  const d = domain.replace(/^https?:\/\//i, "").split("/")[0] ?? domain;
  return `https://${d}`;
}

function tierBadge(tier: string): string | null {
  const t = tier.trim();
  if (!t || /^you provided$/i.test(t)) return null;
  return /^tier\s/i.test(t) ? t : `Tier ${t}`;
}

function urlLabel(url: string) {
  try {
    const u = new URL(url);
    return u.pathname === "/" || u.pathname === "" ? u.host.replace(/^www\./, "") : u.pathname.slice(0, 56);
  } catch {
    return url.slice(0, 56);
  }
}

function normalizeDomain(domain: string): string {
  return domain.replace(/^https?:\/\//i, "").replace(/^www\./i, "").split("/")[0]?.toLowerCase() ?? domain;
}

function citedEnginesForRow(row: RankedCompetitorVisibility): string[] {
  const byEngine = row.citations_by_engine ?? {};
  const candidates = row.cited_engines?.length
    ? row.cited_engines
    : row.engines?.length
      ? row.engines
      : Object.keys(byEngine);
  return candidates.filter((eng) => (byEngine[eng]?.length ?? 0) > 0);
}

function isUserProvidedRow(
  row: RankedCompetitorVisibility,
  userDomains: Set<string>,
): boolean {
  if (row.user_provided) return true;
  return userDomains.has(normalizeDomain(row.domain));
}

type DisplayTier = "multi_ai" | "single_ai" | "roster" | "empty";

type CompetitorsDisplayResult = {
  rows: RankedCompetitorVisibility[];
  tier: DisplayTier;
  isPartial: boolean;
  partialNote: string | null;
};

function isValidVisibilityRow(row: unknown): row is RankedCompetitorVisibility {
  if (!row || typeof row !== "object") return false;
  const r = row as RankedCompetitorVisibility;
  const domain = typeof r.domain === "string" ? r.domain.trim() : "";
  return domain.length > 0;
}

/** Merge all API pools for this prompt; dedupe by domain, keep richest citation row. */
function collectVisibilityPool(viewData: CompetitorCitationVisibility): RankedCompetitorVisibility[] {
  const sources = [
    ...(viewData.all_ranked_competitors ?? []),
    ...(viewData.ranked_competitors ?? []),
    ...(viewData.competitors ?? []),
    ...(viewData.other_cited_domains ?? []),
    ...(viewData.discovery_only ?? []),
  ];
  const byDomain = new Map<string, RankedCompetitorVisibility>();
  for (const raw of sources) {
    if (!isValidVisibilityRow(raw)) continue;
    const row = raw;
    const key = normalizeDomain(row.domain);
    if (!key) continue;
    const prev = byDomain.get(key);
    const rowEngines = citedEnginesForRow(row).length;
    const prevEngines = prev ? citedEnginesForRow(prev).length : 0;
    if (!prev || rowEngines > prevEngines) {
      byDomain.set(key, row);
    }
  }
  return [...byDomain.values()];
}

function engineCountForSort(row: RankedCompetitorVisibility): number {
  return citedEnginesForRow(row).length;
}

/**
 * Priority: (1) multi-AI citations, (2) single-AI, (3) any valid roster/API row.
 * Never returns empty while the API sent usable competitor rows.
 */
function competitorsForDisplay(
  viewData: CompetitorCitationVisibility | null,
  userDomains: Set<string>,
  limit = 12,
): CompetitorsDisplayResult {
  if (!viewData) {
    return { rows: [], tier: "empty", isPartial: false, partialNote: null };
  }

  const pool = collectVisibilityPool(viewData);
  if (pool.length === 0) {
    return { rows: [], tier: "empty", isPartial: false, partialNote: null };
  }

  const sorted = [...pool].sort((a, b) => {
    const ecB = engineCountForSort(b);
    const ecA = engineCountForSort(a);
    if (ecB !== ecA) return ecB - ecA;
    const userA = isUserProvidedRow(a, userDomains) ? 1 : 0;
    const userB = isUserProvidedRow(b, userDomains) ? 1 : 0;
    if (userB !== userA) return userB - userA;
    return (a.visibility_rank ?? 99) - (b.visibility_rank ?? 99);
  });

  const multi = sorted.filter((r) => engineCountForSort(r) >= 2);
  const single = sorted.filter((r) => engineCountForSort(r) === 1);
  const uncited = sorted.filter((r) => engineCountForSort(r) === 0);

  let rows: RankedCompetitorVisibility[];
  let tier: DisplayTier;
  let isPartial = false;
  let partialNote: string | null = null;

  if (multi.length > 0) {
    rows = multi;
    tier = "multi_ai";
    const hasUserCited = multi.some((r) => isUserProvidedRow(r, userDomains));
    if (userDomains.size > 0 && !hasUserCited) {
      isPartial = true;
      partialNote =
        "Your listed competitors were not cited on this prompt. Showing other domains AI engines cited instead.";
    }
  } else if (single.length > 0) {
    rows = single;
    tier = "single_ai";
    isPartial = true;
    partialNote =
      "No competitor was cited by multiple AI engines for this prompt. Showing domains cited by at least one engine.";
  } else {
    rows = uncited.slice(0, limit);
    tier = "roster";
    isPartial = true;
    partialNote =
      "No direct AI citations matched this prompt. Showing competitor domains from your scan and discovery data.";
  }

  return {
    rows: rows.slice(0, limit),
    tier,
    isPartial,
    partialNote,
  };
}

function EngineColumn({ engine, citations }: { engine: string; citations: EngineCitationHit[] }) {
  if (citations.length === 0) return null;
  return (
    <div className="flex min-h-[120px] flex-col rounded-lg border border-tr-line bg-white p-3">
      <h5 className="font-display text-[11px] font-extrabold uppercase tracking-wide text-tr-navy">
        {engineTitle(engine)}
      </h5>
      <ul className="mt-2 space-y-2">
        {citations.map((c, i) => (
          <li key={`${c.url}-${i}`} className="text-[11px] leading-snug">
            <a
              href={c.url}
              target="_blank"
              rel="noopener noreferrer"
              className="group flex items-start gap-1 font-medium text-brand-primary hover:underline"
            >
              <span className="min-w-0 flex-1 break-all">{urlLabel(c.url)}</span>
              <ExternalLink className="mt-0.5 h-3 w-3 shrink-0 opacity-60" />
            </a>
            {c.position != null ? (
              <span className="mt-0.5 block text-[10px] text-tr-mute">Position #{c.position}</span>
            ) : null}
            {c.snippet ? (
              <span className="mt-0.5 block line-clamp-2 text-[10px] text-tr-mute">{c.snippet}</span>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}

function UncitedCompetitorRow({ row }: { row: RankedCompetitorVisibility }) {
  const host = row.domain.replace(/^www\./i, "");
  return (
    <article className="overflow-hidden rounded-xl border border-dashed border-tr-line bg-[#FCFFFD] px-4 py-3.5">
      <p className="font-display text-[15px] font-bold text-tr-navy">{row.name || host}</p>
      <a
        href={domainHref(row.domain)}
        target="_blank"
        rel="noopener noreferrer"
        className="text-[12px] font-medium text-brand-primary hover:underline"
      >
        {host}
      </a>
      <p className="mt-2 text-[12px] leading-relaxed text-tr-mute">
        Listed as a competitor for this scan — not cited directly in AI answers for this prompt.
      </p>
    </article>
  );
}

function CompetitorRow({ row }: { row: RankedCompetitorVisibility }) {
  const byEngine = row.citations_by_engine ?? {};
  const citedEngines = citedEnginesForRow(row);
  if (citedEngines.length === 0) return <UncitedCompetitorRow row={row} />;
  const host = row.domain.replace(/^www\./i, "");

  return (
    <article className="overflow-hidden rounded-xl border border-tr-line bg-[#FCFFFD]">
      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-tr-line bg-tr-pale/20 px-4 py-3.5">
        <div className="min-w-0">
          <p className="font-display text-[15px] font-bold text-tr-navy">
            {row.name}
          </p>
          <a
            href={domainHref(row.domain)}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[12px] font-medium text-brand-primary hover:underline"
          >
            {host}
          </a>
          <span className="ml-2 text-[11px] uppercase text-tr-mute">
            {competitorLevelLabel(row.level) || "Your competitor"}
          </span>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          {tierBadge(row.tier ?? "") ? (
            <span className="rounded-full bg-tr-pale px-2.5 py-0.5 font-display text-[10px] font-extrabold uppercase text-tr-teal">
              {tierBadge(row.tier ?? "")}
            </span>
          ) : null}
          <span className="rounded-full bg-brand-primary/10 px-2.5 py-0.5 font-display text-[11px] font-extrabold text-brand-primary">
            Cited in {citedEngines.length} engine{citedEngines.length === 1 ? "" : "s"}
          </span>
        </div>
      </header>

      <div
        className={cn(
          "grid gap-3 p-4",
          citedEngines.length <= 2
            ? "sm:grid-cols-2"
            : citedEngines.length === 3
              ? "sm:grid-cols-2 lg:grid-cols-3"
              : "sm:grid-cols-2 lg:grid-cols-4",
        )}
      >
        {citedEngines.map((eng) => (
          <EngineColumn key={eng} engine={eng} citations={byEngine[eng] ?? []} />
        ))}
      </div>
    </article>
  );
}

function resolveVisibilityForPrompt(
  data: CompetitorCitationVisibility,
  promptId: string | null,
): CompetitorCitationVisibility {
  if (!promptId) return data;
  const match = data.by_prompt?.find((p) => p.prompt_id === promptId);
  if (!match) return data;
  if (collectVisibilityPool(match).length > 0) return match;
  // Per-prompt block empty — use aggregate pools so the section still shows data.
  if (collectVisibilityPool(data).length > 0) return data;
  return match;
}

/** Citations per AI engine for competitors the user listed when starting the scan. */
export function CompetitorEngineCitations({
  data,
  prompts = [],
  selectedPromptId,
  onPromptSelect,
  discoveryPending,
  discoveryFailed,
  userProvidedDomains = [],
  matrixCells = [],
  engines = [],
  roster = [],
  isLoading,
  fetchFailed,
  className,
}: {
  data: CompetitorCitationVisibility | null | undefined;
  /** Same matrix.cells as the citation heatmap — keeps this section in sync. */
  matrixCells?: MatrixCell[];
  engines?: string[];
  roster?: MatrixRosterEntry[];
  prompts?: { id: string; text: string }[];
  selectedPromptId?: string | null;
  onPromptSelect?: (promptId: string) => void;
  discoveryPending?: boolean;
  discoveryFailed?: boolean;
  /** Domains from the scan form / user_provided_competitors roster. */
  userProvidedDomains?: string[];
  /** Explicit loading flag from the parent query — when false, stops the spinner even if data is null. */
  isLoading?: boolean;
  /** Dedicated citations endpoint failed and no visibility was merged from the report. */
  fetchFailed?: boolean;
  className?: string;
}) {
  const showPromptToggle = prompts.length > 1 && Boolean(onPromptSelect);
  const activePromptId = selectedPromptId ?? prompts[0]?.id ?? null;

  const userDomains = useMemo(
    () => new Set(userProvidedDomains.map(normalizeDomain).filter(Boolean)),
    [userProvidedDomains],
  );

  const viewData = useMemo(() => {
    const apiSlice = data ? resolveVisibilityForPrompt(data, activePromptId) : null;
    const matrixSlice = visibilityFromMatrixCells(
      matrixCells,
      prompts,
      engines,
      activePromptId,
      roster,
    );
    return mergeVisibilityWithMatrix(apiSlice, matrixSlice);
  }, [data, activePromptId, matrixCells, prompts, engines, roster]);

  const displayResult = useMemo(
    () => competitorsForDisplay(viewData, userDomains),
    [viewData, userDomains],
  );
  const competitors = displayResult.rows;
  const hasSyncedData = competitors.length > 0;
  const showSpinner = isLoading === true && !hasSyncedData;
  const fetchSettled = isLoading === false || hasSyncedData;

  const activePromptText =
    prompts.find((p) => p.id === activePromptId)?.text ?? viewData?.prompt_text ?? data?.prompt_text;

  const hasUserList = userDomains.size > 0;
  const sectionHeading =
    displayResult.tier === "multi_ai" && !displayResult.isPartial
      ? `Competitors cited (${competitors.length})`
      : displayResult.tier === "roster"
        ? `Competitor roster (${competitors.length})`
        : `Competitor citations (${competitors.length})`;

  return (
    <section
      className={cn(
        "overflow-hidden rounded-[18px] border border-tr-line bg-white shadow-[0_8px_30px_rgba(10,37,64,0.06)]",
        className,
      )}
    >
      <div className="border-b border-tr-line px-[22px] py-[18px]">
        <h3 className="font-display text-sm font-extrabold uppercase tracking-wide text-tr-navy">
          Competitor citations by AI engine
        </h3>
        <p className="mt-1 text-[12px] leading-relaxed text-tr-mute">
          URLs cited by ChatGPT, Claude, Gemini, or Perplexity that relate to{" "}
          {hasUserList ? "the competitors you entered" : "your listed competitors"} for
          {activePromptText ? (
            <>
              {" "}
              &ldquo;<span className="font-medium text-tr-navy">{activePromptText}</span>&rdquo;
            </>
          ) : (
            " this prompt"
          )}
          . Only engines that actually cited each company are shown.
        </p>
        {showPromptToggle ? (
          <div className="mt-4" role="tablist" aria-label="Select prompt for competitor citations">
            <p className="mb-2 font-display text-[10px] font-extrabold uppercase tracking-[1.1px] text-tr-teal">
              Prompt
            </p>
            <div className="flex flex-wrap gap-2">
              {prompts.map((p, i) => {
                const active = p.id === activePromptId;
                return (
                  <button
                    key={p.id}
                    type="button"
                    role="tab"
                    aria-selected={active}
                    onClick={() => onPromptSelect?.(p.id)}
                    className={cn(
                      "min-w-[min(100%,12rem)] flex-1 rounded-lg border-[1.5px] px-3 py-2.5 text-left font-display text-[12px] font-bold leading-snug transition sm:min-w-[10rem] sm:max-w-[calc(50%-0.25rem)] lg:max-w-[calc(25%-0.375rem)]",
                      active
                        ? "border-tr-navy bg-tr-navy text-white shadow-sm"
                        : "border-tr-line bg-[#F8FCFA] text-tr-navy hover:border-brand-primary hover:text-brand-primary",
                    )}
                  >
                    <span className="mr-1.5 opacity-80">{i + 1}.</span>
                    <span className="line-clamp-2 break-words">{truncatePrompt(p.text, 56)}</span>
                  </button>
                );
              })}
            </div>
          </div>
        ) : null}
      </div>

      {showSpinner ? (
        <div className="flex flex-col items-center gap-3 px-[22px] py-12 text-center">
          <Spinner className="h-8 w-8 text-brand-primary" />
          <p className="text-[13px] font-medium text-tr-navy">Loading competitor citation data…</p>
        </div>
      ) : competitors.length > 0 ? (
        <div className="space-y-4 px-[22px] py-5">
          <h4 className="font-display text-[11px] font-extrabold uppercase tracking-wide text-tr-teal">
            {sectionHeading}
          </h4>
          {displayResult.isPartial && displayResult.partialNote ? (
            <p className="-mt-2 rounded-lg border border-amber-200/80 bg-amber-50/80 px-3 py-2 text-[12px] leading-relaxed text-amber-950">
              {displayResult.partialNote}
            </p>
          ) : null}
          {competitors.map((row) => (
            <CompetitorRow key={row.domain} row={row} />
          ))}
        </div>
      ) : fetchSettled || !discoveryPending ? (
        <div className="space-y-2 px-[22px] py-10 text-center text-[13px] leading-relaxed text-tr-mute">
          <p>
            {fetchFailed
              ? "Could not load competitor citation data. Refresh the page or try again shortly."
              : "No competitor citation data available."}
          </p>
          {!hasUserList ? (
            <p className="text-[12px]">
              Add competitor domains when you start a scan to track their AI citations here.
            </p>
          ) : discoveryFailed ? (
            <p className="text-[12px]">
              Engine runs may have failed — check API credits and run a new scan.
            </p>
          ) : (
            <p className="text-[12px]">Try another prompt tab or re-run the scan once engines finish.</p>
          )}
        </div>
      ) : (
        <div className="flex flex-col items-center gap-3 px-[22px] py-12 text-center">
          <Spinner className="h-8 w-8 text-brand-primary" />
          <p className="text-[13px] font-medium text-tr-navy">Loading competitor citation data…</p>
        </div>
      )}
    </section>
  );
}
