import { cn } from "@/lib/utils";

export function Card({
  className,
  children,
  padding = "p-6",
}: {
  className?: string;
  children: React.ReactNode;
  padding?: string;
}) {
  return (
    <div
      className={cn(
        "rounded-2xl border border-slate-100 bg-white shadow-card",
        padding,
        className,
      )}
    >
      {children}
    </div>
  );
}
