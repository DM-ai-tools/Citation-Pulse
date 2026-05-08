import { cn } from "@/lib/utils";

export function Pill({
  children,
  tone = "neutral",
  className,
}: {
  children: React.ReactNode;
  tone?: "neutral" | "brand" | "warn";
  className?: string;
}) {
  const tones = {
    neutral: "bg-slate-100 text-ink-800",
    brand: "bg-brand-primary/10 text-brand-primaryDark border border-brand-primary/30",
    warn: "bg-amber-50 text-amber-900 border border-amber-200",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
