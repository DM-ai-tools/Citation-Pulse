export function pct(n: number, digits = 0) {
  return `${(n * 100).toFixed(digits)}%`;
}

export function clampScore(n: number) {
  return Math.max(0, Math.min(100, Math.round(n)));
}
