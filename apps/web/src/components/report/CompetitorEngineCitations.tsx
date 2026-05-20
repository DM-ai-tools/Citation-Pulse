"use client";

import { useMemo } from "react";
import { ExternalLink } from "lucide-react";
import { Spinner } from "@/components/primitives";

function truncatePrompt(text: string, max = 52): string {
  const t = text.trim();
  if (t.length <= max) return t;
  return `${t.slice(0, max - 1)}…`;
}
import { engineTitle } from "@/lib/engineDisplay";
import { cn } from "@/lib/utils";
import type { CompetitorCitationVisibility, EngineCitationHit, RankedCompetitorVisibility } from "@/types/competitorVisibility";

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

const TARGET_SAME_MIN = 2;
const TARGET_ABOVE_MIN = 2;
const TARGET_SAME_MAX = 3;
const TARGET_ABOVE_MAX = 3;
const DISPLAY_MIN_COMPETITORS = TARGET_SAME_MIN + TARGET_ABOVE_MIN;
const DISPLAY_MAX_COMPETITORS = TARGET_SAME_MAX + TARGET_ABOVE_MAX;

function citedEnginesForRow(row: RankedCompetitorVisibility): string[] {
  const byEngine = row.citations_by_engine ?? {};
  const candidates = row.cited_engines?.length
    ? row.cited_engines
    : row.engines?.length
      ? row.engines
      : Object.keys(byEngine);
  return candidates.filter((eng) => (byEngine[eng]?.length ?? 0) > 0);
}

function isDisplayableCompetitor(row: RankedCompetitorVisibility): boolean {
  if (!row.cited_by_engines) return false;
  if (citedEnginesForRow(row).length > 0) return true;
  const hits = row.engine_citations?.length ?? 0;
  return hits > 0;
}

function mergeCitedCompetitors(viewData: CompetitorCitationVisibility | null): RankedCompetitorVisibility[] {
  if (!viewData) return [];
  const byDomain = new Map<string, RankedCompetitorVisibility>();
  const add = (rows: RankedCompetitorVisibility[] | undefined) => {
    for (const r of rows ?? []) {
      if (!isDisplayableCompetitor(r)) continue;
      const prev = byDomain.get(r.domain);
      if (!prev || (r.visibility_rank ?? 99) < (prev.visibility_rank ?? 99)) {
        byDomain.set(r.domain, r);
      }
    }
  };
  add(viewData.competitors ?? viewData.ranked_competitors);
  add(viewData.all_ranked_competitors);
  add(viewData.other_cited_domains);
  return [...byDomain.values()].sort((a, b) => (a.visibility_rank ?? 99) - (b.visibility_rank ?? 99));
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

function CompetitorRow({ row }: { row: RankedCompetitorVisibility }) {
  const byEngine = row.citations_by_engine ?? {};
  const citedEngines = citedEnginesForRow(row);
  if (citedEngines.length === 0) return null;
  const host = row.domain.replace(/^www\./i, "");
  const tier = tierBadge(row.tier);

  return (
    <article className="overflow-hidden rounded-xl border border-tr-line bg-[#FCFFFD]">
      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-tr-line bg-tr-pale/20 px-4 py-3.5">
        <div className="min-w-0">
          <p className="font-display text-[15px] font-bold text-tr-navy">
            #{row.visibility_rank} · {row.name}
          </p>
          <a
            href={domainHref(row.domain)}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[12px] font-medium text-brand-primary hover:underline"
          >
            {host}
          </a>
          {row.level && row.level !== "user_provided" ? (
            <span className="ml-2 text-[11px] uppercase text-tr-mute">
              {row.level === "one_level_above" ? "One tier above" : "Same level"}
            </span>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          {tier ? (
            <span className="rounded-full bg-tr-pale px-2.5 py-0.5 font-display text-[10px] font-extrabold uppercase text-tr-teal">
              {tier}
            </span>
          ) : null}
          <span className="rounded-full bg-brand-primary/10 px-2.5 py-0.5 font-display text-[11px] font-extrabold text-brand-primary">
            {row.visibility_score}% · cited in {citedEngines.length} engine
            {citedEngines.length === 1 ? "" : "s"}
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
  return match ?? data;
}

/** Competitor-analysis companies only — citations per engine for the scan prompt. */
export function CompetitorEngineCitations({
  data,
  prompts = [],
  selectedPromptId,
  onPromptSelect,
  discoveryPending,
  discoveryFailed,
  discoveryValidatedCount,
  className,
}: {
  data: CompetitorCitationVisibility | null | undefined;
  prompts?: { id: string; text: string }[];
  selectedPromptId?: string | null;
  onPromptSelect?: (promptId: string) => void;
  discoveryPending?: boolean;
  discoveryFailed?: boolean;
  /** Same-level + one-tier-above count from discovery validation (for empty-state copy). */
  discoveryValidatedCount?: number;
  className?: string;
}) {
  const showPromptToggle = prompts.length > 1 && Boolean(onPromptSelect);
  const activePromptId = selectedPromptId ?? prompts[0]?.id ?? null;

  const viewData = useMemo(() => {
    if (!data) return null;
    return resolveVisibilityForPrompt(data, activePromptId);
  }, [data, activePromptId]);

  const competitors = useMemo(() => mergeCitedCompetitors(viewData), [viewData]);

  const sameTier = useMemo(
    () => competitors.filter((r) => r.level === "same_level"),
    [competitors],
  );
  const aboveTier = useMemo(
    () => competitors.filter((r) => r.level === "one_level_above"),
    [competitors],
  );
  const otherCited = useMemo(
    () =>
      competitors.filter(
        (r) => r.level !== "same_level" && r.level !== "one_level_above",
      ),
    [competitors],
  );

  const tierBalance = viewData?.tier_balance;

  const activePromptText =
    prompts.find((p) => p.id === activePromptId)?.text ?? viewData?.prompt_text ?? data?.prompt_text;

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
          Shows cited competitors only (target {TARGET_SAME_MIN}–{TARGET_SAME_MAX} same-tier and{" "}
          {TARGET_ABOVE_MIN}–{TARGET_ABOVE_MAX} one-tier-above). Discovery expands until tier minimums are met.
          Only engines that actually cited each company are shown. Ranked by citation frequency for
          {activePromptText ? (
            <>
              {" "}
              &ldquo;<span className="font-medium text-tr-navy">{activePromptText}</span>&rdquo;
            </>
          ) : (
            " your scan prompt"
          )}
          . Unrelated URLs are not shown.
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

      {discoveryPending ? (
        <div className="flex flex-col items-center gap-3 px-[22px] py-12 text-center">
          <Spinner className="h-8 w-8 text-brand-primary" />
          <p className="text-[13px] font-medium text-tr-navy">Waiting for competitor analysis…</p>
        </div>
      ) : discoveryFailed ? (
        <p className="px-[22px] py-10 text-center text-[13px] leading-relaxed text-tr-mute">
          Competitor analysis could not be saved (validation or OpenRouter response). Check the API log,
          confirm <code className="text-[12px]">OPENROUTER_API_KEY</code> has credits, then run a new scan.
        </p>
      ) : !data || competitors.length === 0 ? (
        <div className="space-y-2 px-[22px] py-10 text-center text-[13px] leading-relaxed text-tr-mute">
          <p>
            No competitors were cited by ChatGPT, Claude, Gemini, or Perplexity for this prompt yet.
            {discoveryValidatedCount && discoveryValidatedCount > 0 ? (
              <>
                {" "}
                Discovery found {discoveryValidatedCount} validated competitor
                {discoveryValidatedCount === 1 ? "" : "s"} (see Competitor landscape above), but they did not
                appear in AI answers for this wording — try a new scan after expansion completes or adjust the
                prompt.
              </>
            ) : (
              " Run a new scan with auto-discover on."
            )}
          </p>
        </div>
      ) : (
        <div className="space-y-4 px-[22px] py-5">
          {tierBalance && !tierBalance.tier_targets_met ? (
            <p className="rounded-lg border border-amber-200/80 bg-amber-50/90 px-3 py-2.5 text-[12px] leading-relaxed text-amber-950">
              Tier balance: {tierBalance.same_tier_cited} same-tier and {tierBalance.one_above_tier_cited}{" "}
              one-tier-above cited (target at least {TARGET_SAME_MIN} + {TARGET_ABOVE_MIN}). Missing:{" "}
              {tierBalance.missing_tiers.length
                ? tierBalance.missing_tiers.map((t) => t.replace(/_/g, " ")).join(", ")
                : "none"}
              .
            </p>
          ) : competitors.length < DISPLAY_MIN_COMPETITORS ? (
            <p className="rounded-lg border border-amber-200/80 bg-amber-50/90 px-3 py-2.5 text-[12px] leading-relaxed text-amber-950">
              Only {competitors.length} cited competitor{competitors.length === 1 ? "" : "s"} for this prompt
              (target {DISPLAY_MIN_COMPETITORS}–{DISPLAY_MAX_COMPETITORS} balanced across tiers).
            </p>
          ) : null}
          {sameTier.length > 0 ? (
            <div className="space-y-3">
              <h4 className="font-display text-[11px] font-extrabold uppercase tracking-wide text-tr-teal">
                Same tier ({sameTier.length})
              </h4>
              {sameTier.map((row) => (
                <CompetitorRow key={row.domain} row={row} />
              ))}
            </div>
          ) : null}
          {aboveTier.length > 0 ? (
            <div className="space-y-3">
              <h4 className="font-display text-[11px] font-extrabold uppercase tracking-wide text-tr-teal">
                One tier above ({aboveTier.length})
              </h4>
              {aboveTier.map((row) => (
                <CompetitorRow key={row.domain} row={row} />
              ))}
            </div>
          ) : null}
          {otherCited.length > 0 ? (
            <div className="space-y-3">
              <h4 className="font-display text-[11px] font-extrabold uppercase tracking-wide text-tr-mute">
                Other cited
              </h4>
              {otherCited.map((row) => (
                <CompetitorRow key={row.domain} row={row} />
              ))}
            </div>
          ) : null}
        </div>
      )}
    </section>
  );
}
