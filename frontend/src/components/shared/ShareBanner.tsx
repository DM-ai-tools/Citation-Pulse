"use client";

import { useState } from "react";
import { Globe, Linkedin, Mail, Twitter } from "lucide-react";
import { toast } from "sonner";

export function ShareBanner({ shareUrl }: { shareUrl: string }) {
  const [copied, setCopied] = useState(false);

  function copy() {
    if (!navigator?.clipboard) return;
    navigator.clipboard
      .writeText(shareUrl)
      .then(() => {
        setCopied(true);
        toast.success("Link copied");
        setTimeout(() => setCopied(false), 2000);
      })
      .catch(() => toast.error("Could not copy"));
  }

  const tweet = `https://twitter.com/intent/tweet?url=${encodeURIComponent(shareUrl)}&text=${encodeURIComponent("Our AI citation report — see how we're cited inside ChatGPT, Claude, Perplexity, and Gemini.")}`;
  const linked = `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(shareUrl)}`;
  const mail = `mailto:?subject=${encodeURIComponent("CitationPulse — AI citation report")}&body=${encodeURIComponent(`Read our AI citation report: ${shareUrl}`)}`;

  return (
    <div className="rounded-xl border border-amber-200/70 bg-amber-50 px-4 py-2.5 text-sm text-amber-900 shadow-sm">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex min-w-0 flex-1 items-center gap-2">
          <Globe className="h-4 w-4 shrink-0 text-amber-600" />
          <span className="text-[11px] font-bold uppercase tracking-wider text-amber-700">
            Public shared report
          </span>
          <span className="hidden text-amber-400 sm:inline">·</span>
          <span className="hidden truncate text-xs text-amber-700 sm:inline">
            anyone with this link can view
          </span>
          <span className="hidden truncate font-mono text-xs text-amber-900 lg:inline">
            {shareUrl}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <button
            type="button"
            onClick={copy}
            className="rounded-md border border-amber-300 bg-white px-2.5 py-1 text-xs font-bold text-amber-800 hover:bg-amber-100"
          >
            {copied ? "Copied" : "Copy link"}
          </button>
          <a
            href={tweet}
            target="_blank"
            rel="noreferrer"
            aria-label="Share on X"
            className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-amber-300 bg-white text-amber-700 hover:bg-amber-100"
          >
            <Twitter className="h-3.5 w-3.5" />
          </a>
          <a
            href={linked}
            target="_blank"
            rel="noreferrer"
            aria-label="Share on LinkedIn"
            className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-amber-300 bg-white text-amber-700 hover:bg-amber-100"
          >
            <Linkedin className="h-3.5 w-3.5" />
          </a>
          <a
            href={mail}
            aria-label="Share by email"
            className="inline-flex items-center gap-1 rounded-md border border-amber-300 bg-white px-2 py-1 text-xs font-bold text-amber-800 hover:bg-amber-100"
          >
            <Mail className="h-3.5 w-3.5" /> Email
          </a>
        </div>
      </div>
    </div>
  );
}
