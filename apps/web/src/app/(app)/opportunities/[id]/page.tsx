"use client";

import { useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Metric, Rich, ScoreBar, num, pct, scoreColor } from "@/components/ui";
import { api } from "@/lib/api";
import type { Opportunity } from "@/lib/types";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="card space-y-2">
      <h2 className="text-xs font-semibold uppercase tracking-wide text-brand">{title}</h2>
      <div className="text-sm leading-relaxed text-slate-300">{children}</div>
    </section>
  );
}

function List({ items }: { items: string[] }) {
  return (
    <ul className="list-disc space-y-1 pl-5">
      {items.map((x, i) => (
        <li key={i}>
          <Rich text={x} />
        </li>
      ))}
    </ul>
  );
}

const EXTERNAL_LABELS: Record<string, string> = {
  search_volume: "Search volume / mo",
  cpc: "CPC ($)",
  competition: "Ad competition",
  trend_growth: "Trend growth (12m)",
  serp_results: "SERP results",
  owned_impressions: "Your GSC impressions",
  owned_clicks: "Your GSC clicks",
  owned_site_searches: "Your GA4 site searches",
};

export default function OpportunityPage() {
  const { id } = useParams<{ id: string }>();
  const { data: opp, error } = useQuery({
    queryKey: ["opportunity", id],
    queryFn: () => api<Opportunity>(`opportunities/${id}`),
  });

  if (error) return <p className="text-rose-400">{error.message}</p>;
  if (!opp) return <p className="text-slate-500">Loading...</p>;

  const m = opp.metrics;
  const s = opp.strategy;
  const components = Object.entries(m.components).map(([name, value]) => ({
    name: name.replace(/_/g, " "),
    value,
  }));

  return (
    <div className="space-y-6">
      <Link href={`/runs/${opp.run_id}`} className="text-sm text-slate-400 hover:text-white">
        &larr; Back to run
      </Link>

      <header className="card flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">{s.title}</h1>
          <p className="text-sm text-slate-500">
            Cluster: {opp.cluster_label} - keywords: {opp.keywords.join(", ")}
          </p>
          {s.generated_by === "heuristic" && (
            <p className="mt-1 text-xs text-amber-300">Heuristic synthesis - configure an LLM key for full analysis.</p>
          )}
        </div>
        <div className="w-48 text-right">
          <div className={`text-4xl font-bold ${scoreColor(opp.gap_score)}`}>{opp.gap_score}</div>
          <div className="mb-2 text-xs uppercase text-slate-500">gap score - {pct(opp.confidence)} confidence</div>
          <ScoreBar score={opp.gap_score} />
        </div>
      </header>

      <Section title="Key takeaways">
        <List items={s.key_takeaways} />
      </Section>

      <div className="grid gap-6 lg:grid-cols-3">
        <section className="card grid grid-cols-2 gap-4 lg:col-span-1">
          <Metric label="Mentions" value={num(m.mentions)} />
          <Metric label="Engagement" value={num(m.engagement)} />
          <Metric label="Velocity" value={`${m.velocity}x`} />
          <Metric label="Neg. sentiment" value={pct(m.negative_sentiment)} />
          <Metric label="Demand intent" value={pct(m.demand_intent_ratio)} />
          <Metric label="Complaints" value={pct(m.complaint_ratio)} />
          <Metric label="Supply posts" value={pct(m.supply_ratio)} />
          <Metric label="Unanswered" value={pct(m.unanswered_ratio)} />
          {Object.entries(m.external).map(([k, v]) => (
            <Metric
              key={k}
              label={EXTERNAL_LABELS[k] ?? k}
              value={k === "trend_growth" || k === "competition" ? pct(v) : num(v)}
            />
          ))}
          <div className="col-span-2 text-xs text-slate-500">
            Connectors: {m.connectors_used.length ? m.connectors_used.join(", ") : "none connected"} - Sources:{" "}
            {Object.entries(m.sources)
              .map(([k, v]) => `${k} (${v})`)
              .join(", ")}
          </div>
        </section>

        <section className="card lg:col-span-2">
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-brand">Gap score components</h2>
          <div className="h-56">
            <ResponsiveContainer>
              <BarChart data={components} layout="vertical" margin={{ left: 40 }}>
                <XAxis type="number" stroke="#64748b" fontSize={11} />
                <YAxis type="category" dataKey="name" stroke="#64748b" fontSize={11} width={110} />
                <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #334155" }} />
                <Bar dataKey="value" fill="#7c5cff" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Section title="Thesis"><Rich text={s.thesis} /></Section>
        <Section title="Value proposition"><Rich text={s.value_proposition} /></Section>
        <Section title="Target audience"><Rich text={s.target_audience} /></Section>
        <Section title="Wedge"><Rich text={s.wedge} /></Section>
        <Section title="Execution strategy"><List items={s.execution_strategy} /></Section>
        <Section title="Go-to-market"><List items={s.go_to_market} /></Section>
        <Section title="Moat"><Rich text={s.moat} /></Section>
        <Section title="Risks"><List items={s.risks} /></Section>
        <Section title="Kill criteria"><List items={s.kill_criteria} /></Section>
      </div>

      <Section title="Evidence">
        <ul className="divide-y divide-slate-800">
          {opp.evidence.map((e, i) => (
            <li key={i} className="flex items-center justify-between gap-4 py-2">
              <a
                href={e.url}
                target="_blank"
                rel="noopener noreferrer nofollow"
                className="flex items-center gap-2 text-slate-200 hover:text-brand"
              >
                {e.title || e.url}
                <ExternalLink className="h-3 w-3 shrink-0" />
              </a>
              <span className="shrink-0 text-xs text-slate-500">
                {e.source} - {e.intent} - {e.engagement} eng.
              </span>
            </li>
          ))}
        </ul>
      </Section>
    </div>
  );
}
