import { cn } from "@/lib/utils";
import { clampScore } from "@/lib/format";

export function ScoreDial({
  score,
  className,
  size = 120,
  stroke = 10,
  /** Draw score number inside the ring (report hero). */
  centerScore = false,
  strokeColor = "#1FB36B",
}: {
  score: number | null | undefined;
  className?: string;
  size?: number;
  stroke?: number;
  centerScore?: boolean;
  strokeColor?: string;
}) {
  const v = clampScore(score ?? 0);
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const dash = (v / 100) * c;
  return (
    <div
      className={cn("relative flex items-center justify-center", className)}
      style={{ width: size, height: size }}
    >
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke="rgba(255,255,255,0.15)"
          strokeWidth={stroke}
          fill="none"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke={strokeColor}
          strokeWidth={stroke}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={`${dash} ${c - dash}`}
        />
      </svg>
      {centerScore && (
        <span
          className="pointer-events-none absolute inset-0 flex items-center justify-center font-display text-[30px] font-black tabular-nums text-white"
          style={{ paddingTop: 2 }}
        >
          {v}
        </span>
      )}
    </div>
  );
}

