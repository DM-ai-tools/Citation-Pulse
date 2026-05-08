import { cn } from "@/lib/utils";
import { engineTitle } from "@/lib/engineDisplay";

export function EngineBadge({ engine, className }: { engine: string; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex rounded-md border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs font-semibold text-tr-navy",
        className,
      )}
    >
      {engineTitle(engine)}
    </span>
  );
}
