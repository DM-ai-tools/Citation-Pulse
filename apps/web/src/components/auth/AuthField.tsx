"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

export function AuthField({
  label,
  type = "text",
  className,
  inputClassName,
  showPasswordToggle,
  autoComplete,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  showPasswordToggle?: boolean;
  inputClassName?: string;
}) {
  const [visible, setVisible] = useState(false);
  const [hydrated, setHydrated] = useState(false);
  const inputType = showPasswordToggle ? (visible ? "text" : "password") : type;

  useEffect(() => {
    setHydrated(true);
  }, []);

  const inputClass = cn(
    "w-full rounded-xl border border-slate-200 bg-white px-4 py-3 pr-16 text-sm text-tr-navyDeep placeholder:text-slate-400 focus:border-[#94D148] focus:outline-none focus:ring-2 focus:ring-[#94D148]/25",
    inputClassName,
  );

  return (
    <div className={cn("space-y-2", className)}>
      <label className="block text-sm font-bold text-tr-navyDeep">{label}</label>
      <div className="relative" suppressHydrationWarning>
        {hydrated ? (
          <>
            <input
              type={inputType}
              className={inputClass}
              autoComplete={
                autoComplete ?? (showPasswordToggle ? "current-password" : type === "email" ? "email" : undefined)
              }
              data-lpignore={showPasswordToggle ? "true" : undefined}
              data-1p-ignore={showPasswordToggle ? "true" : undefined}
              data-bwignore={showPasswordToggle ? "true" : undefined}
              suppressHydrationWarning
              {...props}
            />
            {showPasswordToggle ? (
              <button
                type="button"
                onClick={() => setVisible((v) => !v)}
                className="absolute right-4 top-1/2 -translate-y-1/2 text-sm font-bold text-tr-navyDeep hover:text-[#6fa832]"
              >
                {visible ? "Hide" : "Show"}
              </button>
            ) : null}
          </>
        ) : (
          <div className={cn(inputClass, "text-transparent")} aria-hidden>
            &nbsp;
          </div>
        )}
      </div>
    </div>
  );
}
