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
  if (level === "user_provided") return "You provided";
  if (level === "one_level_above") return "One tier above";
  if (level === "same_level") return "Same level";
  return level.replace(/_/g, " ");
}

function CompetitorChip({ item }: { item: CompetitorRosterItem }) {
  const host = item.domain.replace(/^www\./i, "");
  const href = item.domain.startsWith("http") ? item.domain : `https://${host}`;
  const isUser = item.source === "user" || item.level === "user_provided";

  return (
    <li
      className={cn(
        "flex shrink-0 flex-col rounded-lg border px-3 py-2.5 min-w-[200px] max-w-[240px]",
        isUser ? "border-tr-teal/40 bg-tr-pale/50" : "border-tr-line bg-white",
      )}
    >
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
        <span
          className={cn(
            "rounded-full px-2 py-0.5 font-display text-[9px] font-extrabold uppercase tracking-wide",
            isUser ? "bg-tr-teal/15 text-tr-teal" : "bg-tr-pale text-tr-mute",
          )}
        >
          {levelLabel(item.level)}
        </span>
        {item.tier ? (
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[9px] font-semibold text-slate-600">
            {item.tier}
          </span>
        ) : null}
      </div>
    </li>
  );
}

/** Scrollable roster of AI-discovered + user-provided competitors only. */
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
  const total = analysisDeduped.length + userProvided.length;

  if (total === 0) {
    return (
      <p className={cn("text-[13px] text-tr-mute", className)}>
        No competitors from analysis or your scan form yet.
      </p>
    );
  }

  return (
    <div className={cn("space-y-4", className)}>
      {userProvided.length > 0 ? (
        <div>
          <p className="font-display text-[10px] font-extrabold uppercase tracking-[1.1px] text-tr-teal">
            You provided ({userProvided.length})
          </p>
          <ul
            className={cn(
              "mt-2 flex gap-3 overflow-x-auto overflow-y-hidden pb-2 scroll-smooth",
              variant === "dashboard" && "max-h-[140px] flex-wrap overflow-y-auto",
            )}
          >
            {userProvided.map((item) => (
              <CompetitorChip key={`user-${item.domain}`} item={item} />
            ))}
          </ul>
        </div>
      ) : null}
      {analysisDeduped.length > 0 ? (
        <div>
          <p className="font-display text-[10px] font-extrabold uppercase tracking-[1.1px] text-tr-mute">
            From AI analysis ({analysisDeduped.length})
          </p>
          <ul
            className={cn(
              "mt-2 flex gap-3 overflow-x-auto overflow-y-hidden pb-2 scroll-smooth",
              variant === "dashboard" && "max-h-[200px] flex-wrap overflow-y-auto",
            )}
          >
            {analysisDeduped.map((item) => (
              <CompetitorChip key={`ai-${item.domain}`} item={item} />
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
