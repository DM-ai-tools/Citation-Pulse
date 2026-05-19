"use client";

import { Spinner } from "@/components/primitives";
import { cn } from "@/lib/utils";
import { CompetitorRoster, type CompetitorRosterItem } from "@/components/report/CompetitorRoster";
import type {
  CompetitorCitation,
  CompetitorDiscoveryResult,
  OneLevelAboveCompetitor,
  SameLevelCompetitor,
} from "@/types/competitors";

function domainHref(domain: string) {
  const d = domain.replace(/^https?:\/\//i, "").split("/")[0] ?? domain;
  return `https://${d}`;
}

function tierBadge(tier: string) {
  const t = tier.trim();
  return /^tier\s/i.test(t) ? t : `Tier ${t}`;
}

function CitationList({ citations }: { citations: CompetitorCitation[] }) {
  if (!citations.length) return null;
  const sorted = [...citations].sort(
    (a, b) => (b.relevance_score ?? 0.5) - (a.relevance_score ?? 0.5),
  );
  return (
    <ul className="mt-2 space-y-1.5">
      {sorted.map((c, i) => (
        <li key={`${c.url}-${i}`} className="text-[12px] leading-relaxed text-tr-mute">
          <a
            href={c.url.startsWith("http") ? c.url : domainHref(c.url)}
            target="_blank"
            rel="noopener noreferrer"
            className="font-semibold text-brand-primary hover:underline"
          >
            {c.type.replace(/_/g, " ")}
          </a>
          {c.relevance_score != null ? (
            <span className="ml-1.5 rounded bg-tr-pale px-1.5 py-0.5 text-[10px] font-semibold text-tr-teal">
              {Math.round(c.relevance_score * 100)}% relevant
            </span>
          ) : null}
          {c.evidence ? <span> — {c.evidence}</span> : null}
        </li>
      ))}
    </ul>
  );
}

function CardHeader({
  title,
  domain,
  badge,
  sub,
}: {
  title: string;
  domain: string;
  badge: string;
  sub?: string;
}) {
  const href = domainHref(domain);
  const host = domain.replace(/^https?:\/\//i, "").split("/")[0] ?? domain;
  return (
    <div className="flex flex-wrap items-start justify-between gap-2">
      <div className="min-w-0">
        <p className="font-display text-[14.5px] font-bold text-tr-navy">{title}</p>
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="text-[12px] font-medium text-brand-primary hover:underline"
        >
          {host}
        </a>
      </div>
      <div className="flex flex-col items-end gap-1">
        <span className="inline-flex rounded-full bg-tr-pale px-2.5 py-0.5 font-display text-[10px] font-extrabold uppercase tracking-wide text-tr-teal">
          {badge}
        </span>
        {sub ? <span className="max-w-[14rem] text-right text-[11px] text-tr-mute">{sub}</span> : null}
      </div>
    </div>
  );
}

function SameLevelCard({ row }: { row: SameLevelCompetitor }) {
  const strength = row.citation_strength_score ?? row.similarity_score;
  return (
    <li className="rounded-xl border border-tr-line bg-[#FCFFFD] px-4 py-3.5">
      <CardHeader
        title={row.rank != null ? `#${row.rank} · ${row.name}` : row.name}
        domain={row.domain}
        badge={tierBadge(row.tier)}
        sub={`Citation strength ${Math.round(strength * 100)}% · similarity ${Math.round(row.similarity_score * 100)}%`}
      />
      {row.rank_reason ? (
        <p className="mt-1.5 text-[11px] font-medium text-tr-teal">{row.rank_reason}</p>
      ) : null}
      <p className="mt-2 text-[12.5px] leading-relaxed text-tr-mute">{row.reasoning}</p>
      <CitationList citations={row.citations} />
    </li>
  );
}

function AboveLevelCard({ row }: { row: OneLevelAboveCompetitor }) {
  const strength = row.citation_strength_score ?? 0.65;
  return (
    <li className="rounded-xl border border-tr-line bg-[#FCFFFD] px-4 py-3.5">
      <CardHeader
        title={row.rank != null ? `#${row.rank} · ${row.name}` : row.name}
        domain={row.domain}
        badge={tierBadge(row.tier)}
        sub={`Citation strength ${Math.round(strength * 100)}% · ${row.authority_advantage}`}
      />
      {row.rank_reason ? (
        <p className="mt-1.5 text-[11px] font-medium text-tr-teal">{row.rank_reason}</p>
      ) : null}
      <p className="mt-2 text-[12.5px] leading-relaxed text-tr-mute">{row.reasoning}</p>
      <CitationList citations={row.citations} />
    </li>
  );
}

function TargetAnalysis({ target }: { target: CompetitorDiscoveryResult["target_company"] }) {
  const services = target.detected_services?.filter(Boolean) ?? [];
  const locations = target.detected_locations?.filter(Boolean) ?? [];
  return (
    <div className="rounded-xl border border-brand-primary/25 bg-tr-pale/30 px-4 py-4">
      <CardHeader title={target.name} domain={target.domain} badge={tierBadge(target.company_tier)} />
      <p className="mt-2 text-[12.5px] leading-relaxed text-tr-mute">{target.tier_reasoning}</p>
      {(target.detected_niche || services.length || locations.length) ? (
        <dl className="mt-3 grid gap-2 text-[12px] sm:grid-cols-2">
          {target.detected_niche ? (
            <div>
              <dt className="font-display text-[10px] font-extrabold uppercase tracking-wide text-tr-mute">Niche</dt>
              <dd className="mt-0.5 text-tr-navy">{target.detected_niche}</dd>
            </div>
          ) : null}
          {services.length ? (
            <div>
              <dt className="font-display text-[10px] font-extrabold uppercase tracking-wide text-tr-mute">Services</dt>
              <dd className="mt-0.5 text-tr-navy">{services.join(", ")}</dd>
            </div>
          ) : null}
          {locations.length ? (
            <div>
              <dt className="font-display text-[10px] font-extrabold uppercase tracking-wide text-tr-mute">Locations</dt>
              <dd className="mt-0.5 text-tr-navy">{locations.join(", ")}</dd>
            </div>
          ) : null}
        </dl>
      ) : null}
    </div>
  );
}

export function CompetitorDiscovery({
  discovery,
  userProvided = [],
  analysisCompetitors = [],
  className,
  id,
  scanStatus,
  pending = false,
}: {
  discovery: CompetitorDiscoveryResult | null | undefined;
  userProvided?: CompetitorRosterItem[];
  analysisCompetitors?: CompetitorRosterItem[];
  className?: string;
  id?: string;
  scanStatus?: string;
  /** Background tiered discovery still running (report polls until data arrives). */
  pending?: boolean;
}) {
  const data = discovery ?? null;
  const same = data?.same_level_competitors ?? [];
  const above = data?.one_level_above_competitors ?? [];

  return (
    <section
      id={id}
      data-testid="competitor-discovery"
      className={cn(
        "overflow-hidden rounded-[18px] border border-tr-line bg-white shadow-[0_8px_30px_rgba(10,37,64,0.06)]",
        className,
      )}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-tr-line px-[22px] py-[18px]">
        <h3 className="font-display text-sm font-extrabold uppercase tracking-wide text-tr-navy">
          AI competitor landscape
        </h3>
        <p className="text-xs text-tr-mute">tiered · up to 8 same level + 8 one above</p>
      </div>

      {!data ? (
        pending ? (
          <div className="flex flex-col items-center gap-3 px-[22px] py-12 text-center" role="status" aria-live="polite">
            <Spinner className="h-8 w-8 text-brand-primary" />
            <p className="text-[13px] font-medium text-tr-navy">Building AI competitor landscape…</p>
            <p className="max-w-md text-[12px] leading-relaxed text-tr-mute">
              Analyzing same-level peers and one tier above. Engine citation checks start after this step.
            </p>
          </div>
        ) : (
          <p className="px-[22px] py-10 text-center text-[13px] leading-relaxed text-tr-mute">
            {scanStatus === "completed" ? (
              <>
                Competitor discovery did not run for this scan (OpenRouter may be unset, or auto-discover was off). Add{" "}
                <code className="text-[12px]">OPENROUTER_API_KEY</code> and start a new scan with auto-discover enabled.
              </>
            ) : (
              <>
                Competitor analysis runs first, then AI engines check citations against that landscape.
              </>
            )}
          </p>
        )
      ) : (
        <div className="space-y-6 px-[22px] py-6">
          {(userProvided.length > 0 || analysisCompetitors.length > 0) ? (
            <div className="rounded-xl border border-tr-line bg-[#FAFCFB] px-4 py-4">
              <h4 className="font-display text-[11px] font-extrabold uppercase tracking-wide text-tr-mute">
                Competitor roster
              </h4>
              <p className="mt-1 text-[12px] text-tr-mute">
                AI-discovered peers and companies you listed — scroll to see all.
              </p>
              <div className="mt-3 max-h-[480px] overflow-y-auto overflow-x-hidden pr-1 scroll-smooth">
                <CompetitorRoster
                  analysis={analysisCompetitors}
                  userProvided={userProvided}
                  variant="report"
                />
              </div>
            </div>
          ) : null}
          <div>
            <h4 className="font-display text-[11px] font-extrabold uppercase tracking-wide text-tr-mute">
              Target company analysis
            </h4>
            <div className="mt-3">
              <TargetAnalysis target={data.target_company} />
            </div>
          </div>

          {data.validation_summary ? (
            <div className="rounded-xl border border-tr-line bg-[#FAFCFB] px-4 py-3">
              <h4 className="font-display text-[11px] font-extrabold uppercase tracking-wide text-tr-mute">
                Validation summary
              </h4>
              <p className="mt-2 text-[12px] text-tr-mute">
                {data.validation_summary.same_level_validated} same-level ·{" "}
                {data.validation_summary.one_level_above_validated} one tier above · citations{" "}
                {data.validation_summary.citations_verified ? "verified" : "incomplete"}
              </p>
              {data.validation_summary.notes ? (
                <p className="mt-1 text-[11px] text-amber-800">{data.validation_summary.notes}</p>
              ) : null}
            </div>
          ) : null}

          {same.length > 0 ? (
            <div>
              <h4 className="font-display text-[11px] font-extrabold uppercase tracking-wide text-tr-mute">
                Same-level competitors · ranked by evidence ({same.length})
              </h4>
              <ul className="mt-3 space-y-3">
                {same.map((row) => (
                  <SameLevelCard key={row.domain} row={row} />
                ))}
              </ul>
            </div>
          ) : null}

          {above.length > 0 ? (
            <div>
              <h4 className="font-display text-[11px] font-extrabold uppercase tracking-wide text-tr-mute">
                One level above · ranked by evidence ({above.length})
              </h4>
              <ul className="mt-3 space-y-3">
                {above.map((row) => (
                  <AboveLevelCard key={row.domain} row={row} />
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      )}
    </section>
  );
}
