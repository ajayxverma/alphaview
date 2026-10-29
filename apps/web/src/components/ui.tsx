import clsx from "clsx";
import { Fragment } from "react";
import type { RunStatus } from "@/lib/types";

/** Renders **bold** segments from LLM output without injecting HTML. */
export function Rich({ text }: { text: string }) {
  const parts = text.split(/\*\*(.+?)\*\*/g);
  return (
    <>
      {parts.map((part, i) =>
        i % 2 === 1 ? (
          <strong key={i} className="font-semibold text-white">{part}</strong>
        ) : (
          <Fragment key={i}>{part}</Fragment>
        ),
      )}
    </>
  );
}

export function scoreColor(score: number) {
  if (score >= 70) return "text-emerald-400";
  if (score >= 45) return "text-amber-300";
  return "text-slate-400";
}

export function ScoreBar({ score }: { score: number }) {
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-800">
      <div
        className={clsx(
          "h-full rounded-full",
          score >= 70 ? "bg-emerald-400" : score >= 45 ? "bg-amber-300" : "bg-slate-500",
        )}
        style={{ width: `${Math.min(100, Math.max(0, score))}%` }}
      />
    </div>
  );
}

const STATUS_STYLES: Record<RunStatus, string> = {
  queued: "bg-slate-700 text-slate-200",
  crawling: "bg-sky-900 text-sky-200",
  analyzing: "bg-indigo-900 text-indigo-200",
  enriching: "bg-violet-900 text-violet-200",
  synthesizing: "bg-fuchsia-900 text-fuchsia-200",
  completed: "bg-emerald-900 text-emerald-200",
  failed: "bg-rose-900 text-rose-200",
};

export function StatusPill({ status }: { status: RunStatus }) {
  return (
    <span className={clsx("rounded-full px-2 py-0.5 text-xs font-medium", STATUS_STYLES[status])}>
      {status}
    </span>
  );
}

export function Metric({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-wide text-slate-500">{label}</div>
      <div className="text-sm font-semibold text-white">{value}</div>
    </div>
  );
}

export const pct = (v: number) => `${Math.round(v * 100)}%`;
export const num = (v: number) => Intl.NumberFormat("en", { notation: "compact" }).format(v);
