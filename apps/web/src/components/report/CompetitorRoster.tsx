"use client";

import { cn } from "@/lib/utils";

export type CompetitorRosterItem = {
  domain: string;
  name: string;
  level: string;
  tier?: string;
  rank?: number | null;
  source: "analysis" | "user";
};

function levelLabel(level: string): string {
  if (level === "user_provided") return "Competitor";
  if (level === "one_level_above") return "One tier above";
  if (level === "same_level") return "Same level";
  return level.replace(/_/g, " ");
}

function CompetitorChip({ item }: { item: CompetitorRosterItem }) {
  const host = item.domain.replace(/^www\./i, "");
  const href = item.domain.startsWith("http") ? item.domain : `https://${host}`;

  return (
    <li className="flex shrink-0 flex-col rounded-lg border border-tr-line bg-white px-3 py-2.5 min-w-[200px] max-w-[240px]">
      <div className="flex items-start justify-between gap-2">
        <p className="font-display text-[13px] font-bold leading-snug text-tr-navy line-clamp-2">
          {item.name}
        </p>
        {item.rank != null ? (
          <span className="shrink-0 font-display text-[10px] font-extrabold text-tr-mute">#{item.rank}</span>
        ) : null}
      </div>
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="mt-0.5 text-[11px] font-medium text-brand-primary hover:underline"
      >
        {host}
      </a>
      <div className="mt-2 flex flex-wrap gap-1.5">
        <span className="rounded-full bg-tr-pale px-2 py-0.5 font-display text-[9px] font-extrabold uppercase tracking-wide text-tr-mute">
          {levelLabel(item.level)}
        </span>
        {item.tier && !/^you provided$/i.test(item.tier) ? (
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[9px] font-semibold text-slate-600">
            {item.tier}
          </span>
        ) : null}
      </div>
    </li>
  );
}

/** Scrollable roster of competitors from analysis (includes scan form entries). */
export function CompetitorRoster({
  analysis,
  userProvided,
  className,
  variant = "report",
}: {
  analysis: CompetitorRosterItem[];
  userProvided: CompetitorRosterItem[];
  className?: string;
  variant?: "report" | "dashboard";
}) {
  const analysisDeduped = analysis.filter(
    (a) => !userProvided.some((u) => u.domain.replace(/^www\./i, "") === a.domain.replace(/^www\./i, "")),
  );
  const combined = [...userProvided, ...analysisDeduped];
  const total = combined.length;

  if (total === 0) {
    return (
      <p className={cn("text-[13px] text-tr-mute", className)}>
        No competitors from analysis or your scan form yet.
      </p>
    );
  }

  return (
    <div className={cn("space-y-4", className)}>
      <div>
        <p className="font-display text-[10px] font-extrabold uppercase tracking-[1.1px] text-tr-mute">
          Competitors ({total})
        </p>
        <ul
          className={cn(
            "mt-2 flex gap-3 overflow-x-auto overflow-y-hidden pb-2 scroll-smooth",
            variant === "dashboard" && "max-h-[200px] flex-wrap overflow-y-auto",
          )}
        >
          {combined.map((item) => (
            <CompetitorChip key={`${item.source}-${item.domain}`} item={item} />
          ))}
        </ul>
      </div>
    </div>
  );
}
