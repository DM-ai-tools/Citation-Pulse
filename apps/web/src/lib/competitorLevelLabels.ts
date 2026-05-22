/** User-facing labels for competitor level keys (API values stay unchanged). */

export const COMPETITOR_LEVEL_LABELS = {
  same_level: "Same tier",
  one_level_above: "Competitors ahead",
  user_provided: "Competitor",
} as const;

export function competitorLevelLabel(level: string | null | undefined): string {
  if (!level) return "";
  if (level in COMPETITOR_LEVEL_LABELS) {
    return COMPETITOR_LEVEL_LABELS[level as keyof typeof COMPETITOR_LEVEL_LABELS];
  }
  return level.replace(/_/g, " ");
}

export function formatMissingTierKey(tier: string): string {
  if (tier === "one_level_above") return "competitors ahead";
  if (tier === "same_level") return "same tier";
  return tier.replace(/_/g, " ");
}

/** e.g. "2 same-tier + 2 competitors ahead" */
export function competitorSetTargetCopy(same = 2, ahead = 2): string {
  return `${same} same-tier + ${ahead} competitors ahead`;
}
