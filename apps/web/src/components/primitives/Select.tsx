import { cn } from "@/lib/utils";

export function Select({
  className,
  children,
  ...props
}: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={cn(
        "w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm text-ink-900 focus:border-brand-primary focus:outline-none focus:ring-2 focus:ring-brand-primary/20",
        className,
      )}
      {...props}
    >
      {children}
    </select>
  );
}
