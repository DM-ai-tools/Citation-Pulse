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

function tierBadge(tier: string) {
  const t = tier.trim();
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

function EngineColumn({ engine, citations }: { engine: string; citations: EngineCitationHit[] }) {
  return (
    <div className="flex min-h-[120px] flex-col rounded-lg border border-tr-line bg-white p-3">
      <h5 className="font-display text-[11px] font-extrabold uppercase tracking-wide text-tr-navy">
        {engineTitle(engine)}
      </h5>
      {citations.length === 0 ? (
        <p className="mt-3 flex flex-1 items-center text-[11px] leading-relaxed text-tr-mute">
          Not cited in this engine&apos;s answer for your prompt.
        </p>
      ) : (
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
      )}
    </div>
  );
}

function CompetitorRow({ row, engines }: { row: RankedCompetitorVisibility; engines: string[] }) {
  const byEngine = row.citations_by_engine ?? {};
  const host = row.domain.replace(/^www\./i, "");

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
          {row.user_provided ? (
            <span className="ml-2 text-[11px] font-semibold uppercase text-tr-teal">You provided</span>
          ) : row.level ? (
            <span className="ml-2 text-[11px] uppercase text-tr-mute">
              {row.level === "one_level_above" ? "One tier above" : "Same level"}
            </span>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          {row.user_provided ? (
            <span className="rounded-full border border-tr-teal/40 bg-tr-pale px-2.5 py-0.5 font-display text-[10px] font-extrabold uppercase text-tr-teal">
              Your competitor
            </span>
          ) : null}
          <span className="rounded-full bg-tr-pale px-2.5 py-0.5 font-display text-[10px] font-extrabold uppercase text-tr-teal">
            {tierBadge(row.tier)}
          </span>
          <span className="rounded-full bg-brand-primary/10 px-2.5 py-0.5 font-display text-[11px] font-extrabold text-brand-primary">
            {row.visibility_score}% · {row.engine_count}/{engines.length} engines
          </span>
        </div>
      </header>

      <div className="grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-4">
        {engines.map((eng) => (
          <EngineColumn
            key={eng}
            engine={eng}
            citations={(byEngine[eng] as EngineCitationHit[] | undefined) ?? []}
          />
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
  className,
}: {
  data: CompetitorCitationVisibility | null | undefined;
  prompts?: { id: string; text: string }[];
  selectedPromptId?: string | null;
  onPromptSelect?: (promptId: string) => void;
  discoveryPending?: boolean;
  discoveryFailed?: boolean;
  className?: string;
}) {
  const showPromptToggle = prompts.length > 1 && Boolean(onPromptSelect);
  const activePromptId = selectedPromptId ?? prompts[0]?.id ?? null;

  const viewData = useMemo(() => {
    if (!data) return null;
    return resolveVisibilityForPrompt(data, activePromptId);
  }, [data, activePromptId]);

  const engines = viewData?.engines ?? data?.engines ?? ["chatgpt", "claude", "gemini", "perplexity"];
  const competitors = useMemo(() => {
    const rows = viewData?.competitors ?? viewData?.ranked_competitors ?? [];
    return [...rows].sort((a, b) => {
      const au = a.user_provided ? 0 : 1;
      const bu = b.user_provided ? 0 : 1;
      if (au !== bu) return au - bu;
      return (a.visibility_rank ?? 99) - (b.visibility_rank ?? 99);
    });
  }, [viewData]);

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
          AI-discovered competitors plus any companies you listed at scan setup — what ChatGPT, Claude, Gemini,
          and Perplexity cited for
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
        {(viewData?.user_provided_competitors?.length ?? 0) > 0 ? (
          <div className="mt-3 rounded-lg border border-tr-teal/30 bg-tr-pale/40 px-3 py-2.5">
            <p className="font-display text-[10px] font-extrabold uppercase tracking-[1px] text-tr-teal">
              You provided
            </p>
            <p className="mt-1 flex flex-wrap gap-2">
              {viewData!.user_provided_competitors!.map((c) => (
                <span
                  key={c.domain}
                  className="inline-flex items-center rounded-md border border-tr-line bg-white px-2 py-1 text-[12px] font-semibold text-tr-navy"
                >
                  {c.name}
                </span>
              ))}
            </p>
          </div>
        ) : null}
        {showPromptToggle ? (
          <div className="mt-4" role="tablist" aria-label="Select prompt for competitor citations">
            <p className="mb-2 font-display text-[10px] font-extrabold uppercase tracking-[1.1px] text-tr-teal">
              Prompt
            </p>
            <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
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
                      "min-w-0 flex-1 rounded-lg border-[1.5px] px-3 py-2.5 text-left font-display text-[12px] font-bold leading-snug transition sm:max-w-[calc(33.333%-0.5rem)] sm:flex-none sm:basis-[calc(33.333%-0.5rem)]",
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
        <p className="px-[22px] py-10 text-center text-[13px] text-tr-mute">
          Citations appear after competitor landscape completes. Run a new scan with auto-discover on.
        </p>
      ) : (
        <div className="space-y-4 px-[22px] py-5">
          {competitors.map((row) => (
            <CompetitorRow key={row.domain} row={row} engines={engines} />
          ))}
        </div>
      )}
    </section>
  );
}
