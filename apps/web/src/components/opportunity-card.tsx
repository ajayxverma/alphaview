import Link from "next/link";
import type { Opportunity } from "@/lib/types";
import { Metric, ScoreBar, num, pct, scoreColor } from "./ui";

export function OpportunityCard({ opp }: { opp: Opportunity }) {
  const m = opp.metrics;
  return (
    <Link href={`/opportunities/${opp.id}`} className="card block space-y-3 transition hover:border-brand">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="font-semibold text-white">{opp.title}</h3>
          <p className="text-xs text-slate-500">{opp.cluster_label}</p>
        </div>
        <div className="text-right">
          <div className={`text-2xl font-bold ${scoreColor(opp.gap_score)}`}>{opp.gap_score}</div>
          <div className="text-[10px] uppercase text-slate-500">gap score</div>
        </div>
      </div>
      <ScoreBar score={opp.gap_score} />
      <div className="grid grid-cols-3 gap-3">
        <Metric label="Mentions" value={num(m.mentions)} />
        <Metric label="Velocity" value={`${m.velocity}x`} />
        <Metric label="Demand intent" value={pct(m.demand_intent_ratio)} />
        <Metric label="Supply" value={pct(m.supply_ratio)} />
        <Metric
          label="Search vol."
          value={m.external.search_volume !== undefined ? num(m.external.search_volume) : "-"}
        />
        <Metric label="Confidence" value={pct(opp.confidence)} />
      </div>
    </Link>
  );
}
