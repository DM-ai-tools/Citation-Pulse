/**
 * Build competitor citation visibility from the same matrix.cells the heatmap uses.
 * Keeps "Competitor citations by AI engine" consistent with orange "comp" / competitor cells.
 */

import type {
  CompetitorCitationVisibility,
  EngineCitationHit,
  RankedCompetitorVisibility,
} from "@/types/competitorVisibility";
import type { MatrixCell } from "@/types/scan";

function normalizeDomain(domain: string): string {
  return domain.replace(/^https?:\/\//i, "").replace(/^www\./i, "").split("/")[0]?.toLowerCase() ?? domain;
}

function domainFromUrl(url: string): string {
  try {
    const u = new URL(url.startsWith("http") ? url : `https://${url}`);
    return u.hostname.replace(/^www\./i, "").toLowerCase();
  } catch {
    return normalizeDomain(url);
  }
}

export type MatrixRosterEntry = {
  domain: string;
  name: string;
  userProvided?: boolean;
  level?: string;
  tier?: string;
};

/** Citations from matrix cells for one prompt (heatmap source of truth). */
export function visibilityFromMatrixCells(
  cells: MatrixCell[],
  prompts: { id: string; text: string }[],
  engines: string[],
  promptId: string | null,
  roster: MatrixRosterEntry[],
): CompetitorCitationVisibility | null {
  const pid = promptId ?? prompts[0]?.id ?? null;
  if (!pid) return null;

  const promptText = prompts.find((p) => p.id === pid)?.text ?? "";
  const rosterByDomain = new Map<string, MatrixRosterEntry>();
  for (const r of roster) {
    const key = normalizeDomain(r.domain);
    if (key) rosterByDomain.set(key, r);
  }

  const byDomain = new Map<string, RankedCompetitorVisibility>();

  for (const cell of cells) {
    if (cell.promptId !== pid) continue;
    const eng = cell.engine;
    if (!eng) continue;

    const citeList = cell.citations ?? [];
    const isCompCell = cell.status === "comp";

    for (const c of citeList) {
      const url = (c.url ?? "").trim();
      if (!url) continue;
      const own = (c.ownership ?? "neutral").toLowerCase();
      if (own === "brand") continue;
      // Match heatmap: "comp" cells = competitor-only scenario; include all non-brand URLs in payload.
      if (!isCompCell && own !== "competitor") continue;

      const dom = domainFromUrl(url);
      if (!dom) continue;

      const hit: EngineCitationHit = {
        engine: eng,
        url,
        ownership: own,
        position: c.position ?? null,
        snippet: c.snippet ?? null,
      };

      let row = byDomain.get(dom);
      if (!row) {
        const meta = rosterByDomain.get(dom);
        row = {
          domain: dom,
          name: meta?.name ?? dom,
          tier: meta?.tier ?? "",
          level: meta?.level ?? (meta?.userProvided ? "user_provided" : "engine_cited"),
          visibility_rank: 0,
          visibility_score: 0,
          engine_count: 0,
          citation_count: 0,
          engines: [],
          cited_engines: [],
          best_position: null,
          matched_in_discovery: Boolean(meta),
          user_provided: Boolean(meta?.userProvided),
          cited_by_engines: true,
          reasoning: "Cited in AI answers (same data as citation heatmap).",
          authority_advantage: null,
          discovery_citations: [],
          engine_citations: [],
          citations_by_engine: {},
        };
        byDomain.set(dom, row);
      }

      const byEng = { ...(row.citations_by_engine ?? {}) };
      const list = [...(byEng[eng] ?? [])];
      const dup = list.some((h) => h.url === hit.url);
      if (!dup) list.push(hit);
      byEng[eng] = list;
      row.citations_by_engine = byEng;
      row.engine_citations = [...(row.engine_citations ?? []), hit];
    }
  }

  const ranked = [...byDomain.values()]
    .map((row) => {
      const byEng = row.citations_by_engine ?? {};
      const citedEngines = Object.keys(byEng).filter((e) => (byEng[e]?.length ?? 0) > 0);
      const positions = citedEngines.flatMap((e) =>
        (byEng[e] ?? [])
          .map((h) => h.position)
          .filter((p): p is number => typeof p === "number"),
      );
      return {
        ...row,
        engines: citedEngines,
        cited_engines: citedEngines,
        engine_count: citedEngines.length,
        citation_count: citedEngines.reduce((n, e) => n + (byEng[e]?.length ?? 0), 0),
        best_position: positions.length ? Math.min(...positions) : null,
        cited_by_engines: citedEngines.length > 0,
      };
    })
    .filter((r) => r.cited_by_engines)
    .sort((a, b) => b.engine_count - a.engine_count || a.domain.localeCompare(b.domain));

  ranked.forEach((row, i) => {
    row.visibility_rank = i + 1;
    row.visibility_score = Math.min(100, row.engine_count * 25);
  });

  if (ranked.length === 0) return null;

  return {
    prompt_id: pid,
    prompt_text: promptText,
    engines,
    ranked_competitors: ranked,
    competitors: ranked,
    all_ranked_competitors: ranked,
    discovery_matched_count: ranked.filter((r) => r.matched_in_discovery).length,
    user_provided_count: ranked.filter((r) => r.user_provided).length,
    engine_cited_count: ranked.length,
    both_matched_count: ranked.length,
    discovery_only: [],
    other_cited_domains: [],
    display_ready: true,
  };
}

function mergeRow(
  a: RankedCompetitorVisibility,
  b: RankedCompetitorVisibility,
): RankedCompetitorVisibility {
  const byEng: Record<string, EngineCitationHit[]> = { ...(a.citations_by_engine ?? {}) };
  for (const [eng, hits] of Object.entries(b.citations_by_engine ?? {})) {
    const seen = new Set((byEng[eng] ?? []).map((h) => h.url));
    for (const h of hits) {
      if (!seen.has(h.url)) {
        byEng[eng] = [...(byEng[eng] ?? []), h];
        seen.add(h.url);
      }
    }
  }
  const citedEngines = Object.keys(byEng).filter((e) => (byEng[e]?.length ?? 0) > 0);
  return {
    ...a,
    ...b,
    name: a.name || b.name,
    user_provided: a.user_provided || b.user_provided,
    citations_by_engine: byEng,
    engines: citedEngines,
    cited_engines: citedEngines,
    engine_count: citedEngines.length,
    citation_count: citedEngines.reduce((n, e) => n + (byEng[e]?.length ?? 0), 0),
    cited_by_engines: citedEngines.length > 0,
  };
}

/** Prefer API detail; fill gaps from matrix so counts match the heatmap. */
export function mergeVisibilityWithMatrix(
  api: CompetitorCitationVisibility | null | undefined,
  matrix: CompetitorCitationVisibility | null,
): CompetitorCitationVisibility | null {
  if (!api && !matrix) return null;
  if (!api) return matrix;
  if (!matrix) return api;

  const byDomain = new Map<string, RankedCompetitorVisibility>();
  const ingest = (rows: RankedCompetitorVisibility[]) => {
    for (const row of rows) {
      const key = normalizeDomain(row.domain);
      if (!key) continue;
      const prev = byDomain.get(key);
      byDomain.set(key, prev ? mergeRow(prev, row) : row);
    }
  };

  ingest(matrix.all_ranked_competitors ?? []);
  ingest(matrix.ranked_competitors ?? []);
  ingest(api.all_ranked_competitors ?? []);
  ingest(api.ranked_competitors ?? []);
  ingest(api.competitors ?? []);

  const ranked = [...byDomain.values()].sort(
    (a, b) => (b.engine_count ?? 0) - (a.engine_count ?? 0) || (a.visibility_rank ?? 99) - (b.visibility_rank ?? 99),
  );
  ranked.forEach((r, i) => {
    r.visibility_rank = i + 1;
  });

  return {
    ...api,
    prompt_id: api.prompt_id ?? matrix.prompt_id,
    prompt_text: api.prompt_text || matrix.prompt_text,
    engines: api.engines?.length ? api.engines : matrix.engines,
    ranked_competitors: ranked,
    competitors: ranked,
    all_ranked_competitors: ranked,
    engine_cited_count: ranked.length,
    display_ready: ranked.length > 0,
  };
}
