"use client";

import { useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Metric, Rich, ScoreBar, num, pct, scoreColor } from "@/components/ui";
import { ScoreInfo } from "@/components/score-info";
import { InvestigateButton } from "@/components/research-controls";
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

const SOURCE_SITES: Record<string, { name: string; url?: string }> = {
  reddit: { name: "Reddit", url: "https://www.reddit.com" },
  hackernews: { name: "Hacker News", url: "https://news.ycombinator.com" },
  stackexchange: { name: "Stack Exchange", url: "https://stackexchange.com" },
  github: { name: "GitHub Issues", url: "https://github.com" },
  devto: { name: "DEV Community", url: "https://dev.to" },
  mastodon: { name: "Mastodon (mastodon.social)", url: "https://mastodon.social" },
  web: { name: "Web & Blogs" },
};

function evidenceDomain(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return "";
  }
}

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
          {s.generated_by === "heuristic" ? (
            <p className="mt-1 text-xs text-amber-300">
              Heuristic synthesis. {s.fallback_reason ?? "AI synthesis was unavailable when this report was generated."}{" "}
              {s.model && <span>Attempted model: {s.model}. </span>}
              <Link href="/ai-models" className="underline hover:text-amber-200">
                Check AI Models
              </Link>{" "}
              and start a new discovery run to generate a fresh report.
            </p>
          ) : (
            s.model && <p className="mt-1 text-xs text-slate-500">Synthesized by {s.model}</p>
          )}
        </div>
        <div className="w-48 text-right">
          <div className="flex items-center justify-end gap-2">
            <div className={`text-4xl font-bold ${scoreColor(opp.gap_score)}`}>{opp.gap_score}</div>
            <ScoreInfo score={opp.gap_score} confidence={opp.confidence} metrics={m} />
          </div>
          <div className="mb-2 text-xs uppercase text-slate-500">gap score - {pct(opp.confidence)} confidence</div>
          <ScoreBar score={opp.gap_score} />
        </div>
      </header>

      <Section title="Key takeaways">
        <List items={s.key_takeaways} />
      </Section>
      <InvestigateButton opportunityId={opp.id}/>

      <Section title="Sources gathered">
        <ul className="divide-y divide-slate-800">
          {Object.entries(m.sources).map(([source, count]) => {
            const site = SOURCE_SITES[source];
            return (
              <li key={source} className="flex flex-wrap items-center justify-between gap-2 py-2">
                {site?.url ? (
                  <a href={site.url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 hover:text-brand">
                    {site.name} <ExternalLink className="h-3 w-3" />
                  </a>
                ) : <span>{site?.name ?? source}</span>}
                <span className="text-sm text-slate-400"><strong className="text-white">{num(count)}</strong> signals</span>
              </li>
            );
          })}
        </ul>
        {m.connectors_used.length > 0 && (
          <p className="text-xs text-slate-400">Analytics data: {m.connectors_used.join(", ")}</p>
        )}
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
            <li key={i} className="space-y-2 py-3">
              <a
                href={e.url}
                target="_blank"
                rel="noopener noreferrer nofollow"
                className="flex items-start gap-2 break-words text-slate-200 hover:text-brand"
              >
                {e.title || e.url}
                <ExternalLink className="h-3 w-3 shrink-0" />
              </a>
              {e.excerpt && <p className="break-words text-sm text-slate-400">{e.excerpt}</p>}
              <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-slate-500">
                <span>{SOURCE_SITES[e.source]?.name ?? e.source}</span>
                <span>{evidenceDomain(e.url)}</span>
                {e.source === "web" && <span>Editorial evidence (half demand weight)</span>}
                <span>{e.intent}</span>
                <span>{e.engagement} engagement</span>
                {e.published_at && <time dateTime={e.published_at}>{new Date(e.published_at).toLocaleDateString()}</time>}
              </div>
            </li>
          ))}
        </ul>
      </Section>
    </div>
  );
}
