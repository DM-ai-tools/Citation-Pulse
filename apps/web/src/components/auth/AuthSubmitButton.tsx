import { cn } from "@/lib/utils";

export function AuthSubmitButton({
  className,
  children,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="submit"
      className={cn(
        "auth-submit-btn w-full rounded-xl py-3.5 text-base font-bold text-white transition disabled:cursor-not-allowed disabled:opacity-60",
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}
