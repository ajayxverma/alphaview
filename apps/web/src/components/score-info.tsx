"use client";

import { Info, X } from "lucide-react";
import { useId } from "react";
import type { OpportunityMetrics } from "@/lib/types";

const COMPONENTS: Record<string, { label: string; description: string }> = {
  demand_volume: { label: "Demand volume", description: "Log-scaled mentions, engagement, search volume and owned-site impressions." },
  demand_velocity: { label: "Demand velocity", description: "Recent versus older mentions, adjusted by trend growth when available. Bounded from 0.25 to 6." },
  pain_intensity: { label: "Pain intensity", description: "Negative sentiment, demand intent and unanswered questions. Web articles receive half the community demand weight." },
  supply_density: { label: "Supply density", description: "Solution posts, ad competition and search-result counts. These are supply proxies, not a verified competitor census." },
  supply_quality: { label: "Supply quality", description: "Estimated incumbent strength. More complaints reduce this term and widen the gap." },
};

export function ScoreInfo({ score, confidence, metrics }: { score: number; confidence: number; metrics: OpportunityMetrics }) {
  const id = useId();
  return (
    <>
      <button type="button" popoverTarget={id} aria-label="Score information" title="What does this score mean?"
        className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded border border-slate-700 text-slate-400 hover:text-white">
        <Info className="h-4 w-4" />
      </button>
      <div id={id} popover="auto" role="dialog" aria-labelledby={`${id}-title`}
        className="m-auto max-h-[85dvh] w-[calc(100%-2rem)] max-w-xl overflow-auto rounded-lg border border-slate-700 bg-slate-900 p-5 text-left text-slate-200 shadow-xl">
        <div className="flex items-center justify-between gap-3">
          <h2 id={`${id}-title`} className="text-base font-semibold text-white">Understanding the gap score</h2>
          <button type="button" popoverTarget={id} popoverTargetAction="hide" aria-label="Close score information"
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded hover:bg-slate-800">
            <X className="h-4 w-4" />
          </button>
        </div>
        <p className="mt-3 text-sm text-slate-300">
          This opportunity scores <strong className="text-white">{score}/100</strong>. Higher scores indicate stronger
          observed demand relative to estimated supply. This is a heuristic ranking, not a success probability.
        </p>
        <dl className="mt-4 grid grid-cols-[5rem_1fr] gap-x-3 gap-y-2 text-sm">
          <dt className="text-emerald-400">70-100</dt><dd>Strong observed asymmetry; validate willingness to pay and competitors.</dd>
          <dt className="text-amber-300">45-&lt;70</dt><dd>Worth investigating; evidence is mixed or supply is stronger.</dd>
          <dt className="text-slate-400">0-&lt;45</dt><dd>Weaker observed demand or more competing solutions.</dd>
        </dl>
        <h3 className="mt-5 text-sm font-semibold text-white">Score components</h3>
        <dl className="mt-2 divide-y divide-slate-800">
          {Object.entries(COMPONENTS).map(([key, item]) => (
            <div key={key} className="py-2">
              <dt className="flex justify-between gap-3 text-sm font-medium">
                {item.label}<span>{metrics.components[key]?.toFixed(3) ?? "Not available"}</span>
              </dt>
              <dd className="mt-1 text-xs text-slate-400">{item.description}</dd>
            </div>
          ))}
        </dl>
        <p className="mt-3 text-xs text-slate-400">
          Raw gap = demand volume × demand velocity × pain intensity ÷ (supply density × supply quality).
          The result is compressed onto a 0-100 scale. Missing analytics metrics are omitted, not measured as zero.
        </p>
        <h3 className="mt-5 text-sm font-semibold text-white">Confidence: {Math.round(confidence * 100)}%</h3>
        <p className="mt-2 text-xs text-slate-400">
          60% comes from sample size (up to 60 mentions), and 40% from analytics connector coverage (up to two providers).
          This report has {metrics.mentions} mentions and {metrics.connectors_used.length} contributing analytics providers.
          Coverage is not statistical certainty; sampling bias, duplicated claims, geography and source access can limit reliability.
        </p>
      </div>
    </>
  );
}