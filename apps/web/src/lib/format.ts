export function clampScore(n: number) {
  return Math.max(0, Math.min(100, Math.round(n)));
}
