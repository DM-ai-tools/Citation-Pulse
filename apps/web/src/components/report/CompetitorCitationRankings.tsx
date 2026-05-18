"use client";

import { useMemo, useState } from "react";
import { ExternalLink } from "lucide-react";
import { engineTitle } from "@/lib/engineDisplay";
import { cn } from "@/lib/utils";
import type { CompetitorCitationVisibility, RankedCompetitorVisibility } from "@/types/competitorVisibility";

function domainHref(domain: string) {
  const d = domain.replace(/^https?:\/\//i, "").split("/")[0] ?? domain;
  return `https://${d}`;
}

function CompetitorRankCard({
  row,
  totalEngines,
}: {
  row: RankedCompetitorVisibility;
  totalEngines: number;
}) {
  const [open, setOpen] = useState(false);
  const host = row.domain.replace(/^www\./i, "");

  return (
    <li className="rounded-xl border border-tr-line bg-[#FCFFFD] px-4 py-3.5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="font-display text-[14.5px] font-bold text-tr-navy">
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
        </div>
        <div className="flex flex-col items-end gap-1 text-right">
          <span className="rounded-full bg-brand-primary/10 px-2.5 py-0.5 font-display text-[11px] font-extrabold text-brand-primary">
            {row.visibility_score}% visibility
          </span>
          <span className="text-[11px] text-tr-mute">
            {row.engine_count}/{totalEngines} engines · {row.citation_count} citation
            {row.citation_count === 1 ? "" : "s"}
          </span>
        </div>
      </div>

      <p className="mt-2 text-[12px] text-tr-mute">
        {row.matched_in_discovery ? (
          <span className="font-semibold text-tr-teal">In AI landscape</span>
        ) : (
          <span className="text-tr-landingOrange">Cited by engines only</span>
        )}
        {row.cited_by_engines ? (
          <span>
            {" "}
            · Engines: {row.engines.map((e) => engineTitle(e)).join(", ")}
          </span>
        ) : (
          <span> · Not cited in this scan&apos;s engine runs</span>
        )}
      </p>

      {(row.discovery_citations.length > 0 || row.engine_citations.length > 0) && (
        <button
          type="button"
          className="mt-2 text-[11px] font-semibold text-brand-primary underline"
          onClick={() => setOpen((v) => !v)}
        >
          {open ? "Hide citations" : "Show discovery + engine citations"}
        </button>
      )}

      {open ? (
        <div className="mt-3 space-y-3 border-t border-tr-line pt-3">
          {row.engine_citations.length > 0 ? (
            <div>
              <p className="font-display text-[10px] font-extrabold uppercase tracking-wide text-tr-mute">
                Live engine citations
              </p>
              <ul className="mt-1.5 space-y-1">
                {row.engine_citations.map((c, i) => (
                  <li key={`${c.url}-${i}`} className="flex items-start gap-2 text-[12px]">
                    <span className="shrink-0 rounded bg-tr-pale px-1.5 py-0.5 text-[10px] font-bold text-tr-navy">
                      {engineTitle(c.engine)}
                    </span>
                    <a
                      href={c.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="min-w-0 flex-1 truncate text-brand-primary hover:underline"
                    >
                      {c.url}
                    </a>
                    <ExternalLink className="h-3 w-3 shrink-0 text-tr-mute" />
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {row.discovery_citations.length > 0 ? (
            <div>
              <p className="font-display text-[10px] font-extrabold uppercase tracking-wide text-tr-mute">
                Discovery evidence
              </p>
              <ul className="mt-1.5 space-y-1.5">
                {row.discovery_citations.map((c, i) => (
                  <li key={`${c.url}-${i}`} className="text-[12px] text-tr-mute">
                    <a
                      href={c.url.startsWith("http") ? c.url : domainHref(c.url)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-semibold text-brand-primary hover:underline"
                    >
                      {c.type.replace(/_/g, " ")}
                    </a>
                    {c.relevance_score != null ? (
                      <span className="ml-1 text-[10px] text-tr-teal">
                        {Math.round(c.relevance_score * 100)}%
                      </span>
                    ) : null}
                    {c.evidence ? <span> — {c.evidence}</span> : null}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}
    </li>
  );
}

export function CompetitorCitationRankings({
  data,
  className,
}: {
  data: CompetitorCitationVisibility | null | undefined;
  className?: string;
}) {
  const ranked = useMemo(
    () => (data?.ranked_competitors ?? []).filter((r) => r.matched_in_discovery || r.cited_by_engines),
    [data],
  );

  if (!data || ranked.length === 0) {
    return null;
  }

  const discoveryLinked = data.both_matched_count;

  return (
    <section
      className={cn(
        "overflow-hidden rounded-[18px] border border-tr-line bg-white shadow-[0_8px_30px_rgba(10,37,64,0.06)]",
        className,
      )}
    >
      <div className="border-b border-tr-line px-[22px] py-[18px]">
        <h3 className="font-display text-sm font-extrabold uppercase tracking-wide text-tr-navy">
          Competitor visibility rankings
        </h3>
        <p className="mt-1 text-[12px] text-tr-mute">
          Connects your AI competitor landscape to citations returned by ChatGPT, Claude, Gemini, and Perplexity
          {data.prompt_text ? (
            <>
              {" "}
              for &ldquo;<span className="font-medium text-tr-navy">{data.prompt_text}</span>&rdquo;
            </>
          ) : null}
          . {discoveryLinked} competitor{discoveryLinked === 1 ? "" : "s"} cited across engines and discovery.
        </p>
      </div>
      <ul className="space-y-3 px-[22px] py-5">
        {ranked.map((row) => (
          <CompetitorRankCard key={row.domain} row={row} totalEngines={data.engines.length || 4} />
        ))}
      </ul>
    </section>
  );
}
