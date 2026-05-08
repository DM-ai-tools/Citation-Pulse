import { cn } from "@/lib/utils";

export function Spinner({ className, size = "md" }: { className?: string; size?: "sm" | "md" }) {
  const s = size === "sm" ? "h-4 w-4 border-2" : "h-5 w-5 border-2";
  return (
    <span
      className={cn(
        "inline-block animate-spin rounded-full border-brand-primary border-t-transparent",
        s,
        className,
      )}
      aria-hidden
    />
  );
}
