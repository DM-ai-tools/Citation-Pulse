import { cn } from "@/lib/utils";

export function CitationPulseMark({
  stamp,
  tagline,
  size = "md",
  className,
}: {
  /** Uppercase stamp under the wordmark (e.g. report mode). */
  stamp?: string;
  /** Small caps line under CitationPulse (marketing header). */
  tagline?: string;
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const wordMap = {
    sm: "text-[15px]",
    md: "text-[17px]",
    lg: "text-xl",
  } as const;
  const stampMap = {
    sm: "text-[9px]",
    md: "text-[10px]",
    lg: "text-[11px]",
  } as const;
  return (
    <div className={cn("flex flex-col leading-tight", className)}>
      <span className={cn("font-display font-extrabold tracking-tight text-tr-navy", wordMap[size])}>
        Citation<span className="text-brand-primary">Pulse</span>
      </span>
      {tagline && (
        <span
          className={cn(
            "mt-0.5 block font-semibold uppercase tracking-[1.2px] text-tr-mute",
            stampMap[size],
          )}
        >
          {tagline}
        </span>
      )}
      {stamp && (
        <span
          className={cn(
            "mt-0.5 font-semibold uppercase tracking-[0.18em] text-slate-400",
            stampMap[size],
          )}
        >
          {stamp}
        </span>
      )}
    </div>
  );
}
