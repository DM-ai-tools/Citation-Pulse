"use client";

import Link from "next/link";
import { useId, useMemo, useState } from "react";
import {
  Area,
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { engineTitle } from "@/lib/engineDisplay";
import { cn } from "@/lib/utils";

type EntityMeta = { entity_id: string; name: string; role: string };

export type SoVMultiEntityResponse = {
  primary_brand_id: string;
  range_days: number;
  engines: string[];
  entities: {
    entity_id: string;
    name: string;
    role: string;
    shares_by_engine: Record<string, number>;
  }[];
  totals?: {
    brand_citations: number;
    competitor_citations: number;
  };
};

export type MultiWeeklyResponse = {
  primary_brand_id: string;
  weeks: number;
  entities: EntityMeta[];
  series: { week_start: string; shares: Record<string, number>; tracked_citations: number }[];
};

const BRAND_TEAL = "#0d9488";
const COMP_COLORS = ["#1e3a5f", "#64748b", "#94a3b8", "#cbd5e1"];

function chipBadgeClass(pct: number) {
  if (pct >= 60) return "bg-emerald-500 text-white";
  if (pct >= 40) return "bg-amber-500 text-white";
  return "bg-rose-500 text-white";
}

/** X labels: W1 … Wn-1, then `now` for the latest week in the window. */
function weekAxisLabel(idx: number, total: number, weekStartIso?: string) {
  if (total <= 1) return weekStartIso ? formatWeekTick(weekStartIso) : "now";
  if (idx === total - 1) return "now";
  if (weekStartIso) return formatWeekTick(weekStartIso);
  return `W${idx + 1}`;
}

function formatWeekTick(iso: string) {
  const d = new Date(`${iso}T12:00:00`);
  if (Number.isNaN(d.getTime())) return iso.slice(5);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

/** Resolve share even if API keys differ in casing from scan ``engines`` (belt-and-suspenders). */
function pickEngineShare(shares: Record<string, number | undefined>, eng: string): number {
  const direct = shares[eng];
  if (typeof direct === "number" && !Number.isNaN(direct)) return direct;
  const low = eng.toLowerCase();
  const hit = Object.keys(shares).find((k) => k.toLowerCase() === low);
  const v = hit ? shares[hit] : undefined;
  return typeof v === "number" && !Number.isNaN(v) ? v : 0;
}

/** Weekly `shares` keys are UUID strings; tolerate casing mismatches vs `entities`. */
function pickWeeklyShare(shares: Record<string, number>, entityId: string): number {
  const v = shares[entityId];
  if (typeof v === "number" && !Number.isNaN(v)) return v;
  const hit = Object.keys(shares).find((k) => k.toLowerCase() === entityId.toLowerCase());
  return hit != null && typeof shares[hit] === "number" ? shares[hit] : 0;
}

function customLegend(
  entities: EntityMeta[],
  chartRows: Record<string, string | number>[],
  primaryId: string | undefined,
) {
  if (!chartRows.length || !entities.length) return null;
  const last = chartRows[chartRows.length - 1];
  return (
    <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 border-t border-slate-100 pt-2 text-[11px] text-slate-600">
      {entities.map((e) => {
        const pct = typeof last[e.entity_id] === "number" ? (last[e.entity_id] as number) : 0;
        const isBrand = e.role === "brand" || e.entity_id === primaryId;
        return (
          <span key={e.entity_id} className="inline-flex items-center gap-1.5 font-medium">
            <span className={isBrand ? "text-teal-600" : "text-slate-500"}>{isBrand ? "—" : "· ·"}</span>
            <span className="text-slate-800">{e.name}</span>
            <span className="tabular-nums text-slate-900">{pct}%</span>
          </span>
        );
      })}
    </div>
  );
}

export function BrandSovDashboard(props: {
  brandName: string;
  multi: SoVMultiEntityResponse;
  weekly: MultiWeeklyResponse;
  /** `page`: breadcrumbs + intro above card. `embedded`: only the white card (for scan report). */
  variant?: "page" | "embedded";
  /**
   * Optional chip badge override (e.g. citation matrix scores).
   * Leave unset on SoV views so chips match the per-engine share bars.
   */
  chipScores?: Record<string, number>;
  /** Engines to show in chips / bars (e.g. scan engines). Defaults to `multi.engines`. */
  enginesOrder?: string[];
  /** Sync engine strip with parent (heatmap layer on report). */
  engineControl?: { value: string | null; onChange: (v: string | null) => void };
}) {
  const { multi, weekly, brandName, variant = "page", chipScores, enginesOrder, engineControl } = props;
  const fillGradId = useId().replace(/:/g, "");
  const [localLayer, setLocalLayer] = useState<string | null>(null);

  const primary = useMemo(
    () => multi.entities.find((e) => e.role === "brand") ?? multi.entities[0],
    [multi.entities],
  );

  const engines = (enginesOrder?.length ? enginesOrder : multi.engines).filter(Boolean);
  const highlight: string | null = engineControl ? engineControl.value : localLayer;
  const setEngine = (eng: string | null) => {
    if (engineControl) engineControl.onChange(eng);
    else setLocalLayer(eng);
  };

  const chartRows = useMemo(() => {
    const ents = weekly.entities ?? [];
    const s = weekly.series ?? [];
    return s.map((row, idx) => {
      const out: Record<string, string | number> = {
        week: weekAxisLabel(idx, s.length, row.week_start),
        _iso: row.week_start,
      };
      for (const e of ents) {
        out[e.entity_id] = Math.round(pickWeeklyShare(row.shares, e.entity_id) * 100);
      }
      return out;
    });
  }, [weekly.entities, weekly.series]);

  const trendShowDots = chartRows.length < 2;

  const lastBrandPct = useMemo(() => {
    const s = weekly.series ?? [];
    if (!s.length || !primary) return 0;
    const last = s[s.length - 1];
    return Math.round(pickWeeklyShare(last.shares, primary.entity_id) * 100);
  }, [weekly.series, primary]);

  const deltaPp = useMemo(() => {
    const s = weekly.series ?? [];
    if (!primary || s.length < 2) return null;
    const a = pickWeeklyShare(s[s.length - 2].shares, primary.entity_id) * 100;
    const b = pickWeeklyShare(s[s.length - 1].shares, primary.entity_id) * 100;
    return Math.round((b - a) * 10) / 10;
  }, [weekly.series, primary]);

  const barData = useMemo(() => {
    if (!primary) return [];
    const shares = primary.shares_by_engine ?? {};
    return engines.map((eng) => ({
      engine: engineTitle(eng),
      engKey: eng,
      sharePct: Math.round(pickEngineShare(shares, eng) * 100),
    }));
  }, [primary, engines]);

  const totals = multi.totals;

  const trendYDomain = useMemo(() => {
    let minV = 100;
    let maxV = 0;
    for (const row of chartRows) {
      for (const e of weekly.entities) {
        const v = row[e.entity_id];
        if (typeof v === "number") {
          minV = Math.min(minV, v);
          maxV = Math.max(maxV, v);
        }
      }
    }
    const hi = Math.min(100, Math.max(50, Math.ceil(maxV / 5) * 5 + 5));
    const lo = minV < 8 ? 0 : 10;
    return [lo, hi] as [number, number];
  }, [chartRows, weekly.entities]);

  const barXMax = useMemo(() => {
    let m = 45;
    for (const r of barData) {
      m = Math.max(m, r.sharePct);
    }
    return Math.min(100, Math.max(50, m + 8));
  }, [barData]);

  const card = (
    <div className="overflow-hidden rounded-2xl border border-slate-200/90 bg-white shadow-[0_8px_40px_rgba(15,23,42,0.06)]">
      <div className="border-b border-slate-200 bg-gradient-to-b from-slate-50 to-white px-6 py-4">
        <div className="flex flex-wrap items-center gap-3">
          <span className="font-display text-[11px] font-extrabold uppercase tracking-[0.14em] text-slate-800">
            Engine layer
          </span>
          <span className="h-0.5 w-7 rounded-full bg-sky-500" aria-hidden />
        </div>
        <p className="mt-1.5 text-[12.5px] leading-snug text-slate-500">
          <span className="text-slate-400">—</span> Click an engine to change the heatmap layer.
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2">
          {engineControl && engineControl.value !== null ? (
            <button
              type="button"
              onClick={() => setEngine(null)}
              className="text-[11px] font-semibold text-sky-700 underline decoration-sky-400 underline-offset-2 hover:text-sky-900"
            >
              All engines in heatmap
            </button>
          ) : null}
          <div className="flex flex-wrap gap-2">
          {engines.map((eng) => {
            const sharePct = Math.round(pickEngineShare(primary?.shares_by_engine ?? {}, eng) * 100);
            const chip =
              chipScores != null && Object.prototype.hasOwnProperty.call(chipScores, eng)
                ? Math.round(chipScores[eng] ?? 0)
                : sharePct;
            const selected = highlight === eng;
            return (
              <button
                key={eng}
                type="button"
                onClick={() => setEngine(eng)}
                className={cn(
                  "inline-flex items-center gap-2 rounded-full border px-3.5 py-2 text-sm font-semibold transition",
                  selected
                    ? "border-slate-900 bg-slate-900 text-white shadow-sm"
                    : "border-slate-200 bg-white text-slate-800 hover:border-slate-300",
                )}
              >
                <span>{engineTitle(eng)}</span>
                <span
                  className={cn(
                    "rounded-full px-2 py-0.5 text-[11px] font-bold tabular-nums",
                    selected ? "bg-white/20 text-white" : chipBadgeClass(chip),
                  )}
                >
                  {chip}
                </span>
              </button>
            );
          })}
          </div>
        </div>
      </div>

      <div className="px-6 pb-2 pt-5">
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 pb-4">
          <h2 className="max-w-xl font-display text-[13px] font-black uppercase leading-snug tracking-[0.06em] text-slate-900">
            Share of voice · {brandName.toUpperCase()} vs. competitors
          </h2>
          <p className="shrink-0 text-right text-[12px] font-medium lowercase text-slate-500">
            last {weekly.weeks} weeks · all engines
          </p>
        </div>

        <div className="mt-5 grid gap-8 lg:grid-cols-2 lg:gap-10">
          <div>
            <h3 className="font-display text-sm font-bold text-slate-900">SoV trend</h3>
            <p className="mt-1 text-[12px] leading-relaxed text-slate-500">
              % of all brand + competitor citations belonging to {brandName}, per week
            </p>
            <div className="mt-4 h-[280px] w-full min-w-0">
              {chartRows.length === 0 ? (
                <p className="text-sm text-slate-500">Not enough weekly data yet.</p>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={chartRows} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id={fillGradId} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={BRAND_TEAL} stopOpacity={0.35} />
                        <stop offset="100%" stopColor={BRAND_TEAL} stopOpacity={0.02} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                    <XAxis dataKey="week" tick={{ fontSize: 11, fill: "#64748b" }} axisLine={{ stroke: "#e2e8f0" }} />
                    <YAxis
                      domain={trendYDomain}
                      tickFormatter={(v) => `${v}%`}
                      width={40}
                      tick={{ fontSize: 11, fill: "#64748b" }}
                      axisLine={false}
                    />
                    <Tooltip
                      content={({ active, payload }) => {
                        if (!active || !payload?.length) return null;
                        const row = payload[0]?.payload as Record<string, string | number> | undefined;
                        const iso = row?._iso;
                        return (
                          <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs shadow-md">
                            <p className="font-semibold text-slate-800">{typeof iso === "string" ? iso : ""}</p>
                            <ul className="mt-1.5 space-y-0.5 text-slate-600">
                              {(() => {
                                const seen = new Set<string>();
                                return payload
                                  .filter((p) => {
                                    const dataKey = String(p.dataKey ?? "");
                                    if (!dataKey || seen.has(dataKey)) return false;
                                    seen.add(dataKey);
                                    return true;
                                  })
                                  .map((p) => {
                                    const dataKey = String(p.dataKey ?? "");
                                    const ent = weekly.entities.find((e) => e.entity_id === dataKey);
                                    const label = ent?.name ?? dataKey;
                                    return (
                                      <li key={dataKey}>
                                        <span className="font-medium text-slate-800">{label}</span>
                                        <span className="ml-1.5 tabular-nums font-semibold text-slate-900">
                                          {p.value}%
                                        </span>
                                      </li>
                                    );
                                  });
                              })()}
                            </ul>
                          </div>
                        );
                      }}
                      cursor={{ stroke: "#94a3b8", strokeWidth: 1, strokeDasharray: "4 4" }}
                    />
                    {primary ? (
                      <Area
                        type="monotone"
                        dataKey={primary.entity_id}
                        stroke="transparent"
                        fill={`url(#${fillGradId})`}
                        fillOpacity={1}
                        isAnimationActive={false}
                        legendType="none"
                      />
                    ) : null}
                    {weekly.entities.map((e, i) => {
                      const stroke = e.role === "brand" ? BRAND_TEAL : COMP_COLORS[(i - 1) % COMP_COLORS.length];
                      const isBrand = e.role === "brand";
                      return (
                        <Line
                          key={e.entity_id}
                          type="monotone"
                          dataKey={e.entity_id}
                          name={e.name}
                          stroke={stroke}
                          strokeWidth={isBrand ? 2.4 : 2}
                          strokeDasharray={isBrand ? undefined : "6 4"}
                          dot={trendShowDots ? { r: isBrand ? 5 : 4, strokeWidth: 0, fill: stroke } : false}
                          activeDot={{ r: 4 }}
                          isAnimationActive={false}
                          connectNulls
                        />
                      );
                    })}
                  </ComposedChart>
                </ResponsiveContainer>
              )}
            </div>
            {customLegend(weekly.entities, chartRows, primary?.entity_id)}
          </div>

          <div>
            <h3 className="font-display text-sm font-bold text-slate-900">By engine · this week</h3>
            <p className="mt-1 text-[12px] leading-relaxed text-slate-500">
              {brandName}&apos;s share within each engine&apos;s answers
            </p>
            <div className="mt-4 h-[280px] w-full min-w-0">
              {barData.length === 0 ? (
                <p className="text-sm text-slate-500">No engine data.</p>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    layout="vertical"
                    data={barData}
                    margin={{ top: 4, right: 28, left: 4, bottom: 4 }}
                    barCategoryGap={10}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
                    <XAxis type="number" domain={[0, barXMax]} tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
                    <YAxis type="category" dataKey="engine" width={108} tick={{ fontSize: 11 }} axisLine={false} />
                    <Tooltip formatter={(v: number) => [`${v}%`, brandName]} />
                    <Bar dataKey="sharePct" radius={[0, 8, 8, 0]} maxBarSize={26} fill={BRAND_TEAL} name="Share" minPointSize={3} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-x-8 gap-y-2 border-t border-slate-200 bg-sky-50 px-6 py-3.5 text-sm">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Overall SoV</span>
          <p className="font-display text-lg font-black tabular-nums text-slate-900">{lastBrandPct}%</p>
        </div>
        <div>
          <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Δ vs last week</span>
          <p
            className={cn(
              "inline-flex items-center gap-1 font-display text-lg font-black tabular-nums",
              deltaPp == null ? "text-slate-400" : deltaPp >= 0 ? "text-[#0d9488]" : "text-rose-600",
            )}
          >
            {deltaPp != null && deltaPp >= 0 ? <span aria-hidden>▲</span> : null}
            {deltaPp == null ? "—" : `${deltaPp >= 0 ? "+" : ""}${deltaPp}pp`}
          </p>
        </div>
        <div>
          <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Brand citations (12w)</span>
          <p className="font-display text-lg font-black tabular-nums text-slate-900">{totals?.brand_citations ?? "—"}</p>
        </div>
        <div>
          <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Competitor citations (12w)
          </span>
          <p className="font-display text-lg font-black tabular-nums text-slate-900">
            {totals?.competitor_citations ?? "—"}
          </p>
        </div>
        <p className="ml-auto max-w-xs text-right text-[11px] leading-snug text-slate-500">
          Third-party citations are excluded from this calculation
        </p>
      </div>
    </div>
  );

  if (variant === "embedded") {
    return card;
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          <Link href="/dashboard" className="text-[#0d9488] hover:underline">
            Dashboard
          </Link>
          <span className="mx-2 text-slate-300">/</span>
          <Link href="/dashboard/sov" className="text-[#0d9488] hover:underline">
            Share of voice
          </Link>
          <span className="mx-2 text-slate-300">/</span>
          <span className="text-slate-600">{brandName}</span>
        </p>
        <h1 className="mt-2 font-display text-2xl font-bold tracking-tight text-slate-900">{brandName}</h1>
        <p className="mt-1 max-w-2xl text-sm text-slate-600">
          Compare your brand&apos;s citation share with linked competitors across AI engines. Third-party domains are
          excluded from the weekly trend denominator so lines sum to 100% among tracked brands.
        </p>
      </div>
      {card}
    </div>
  );
}
