"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Radar } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { OpportunityCard } from "@/components/opportunity-card";
import { StatusPill } from "@/components/ui";
import { ApiError, api, post } from "@/lib/api";
import type { Opportunity, Run } from "@/lib/types";

const ACTIVE = new Set(["queued", "crawling", "analyzing", "enriching", "synthesizing"]);

export default function DashboardPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<string[]>(["reddit", "hackernews", "stackexchange"]);

  const sources = useQuery({ queryKey: ["sources"], queryFn: () => api<{ id: string; name: string }[]>("sources") });
  const runs = useQuery({
    queryKey: ["runs"],
    queryFn: () => api<Run[]>("discovery"),
    refetchInterval: (q) => (q.state.data?.some((r) => ACTIVE.has(r.status)) ? 4000 : false),
  });
  const top = useQuery({ queryKey: ["opportunities"], queryFn: () => api<Opportunity[]>("opportunities?min_score=0") });

  const start = useMutation({
    mutationFn: () => post<Run>("discovery", { query, sources: selected }),
    onSuccess: (run) => {
      qc.invalidateQueries({ queryKey: ["runs"] });
      router.push(`/runs/${run.id}`);
    },
  });

  const toggle = (id: string) =>
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));

  return (
    <div className="space-y-8">
      <section className="card">
        <h1 className="text-xl font-semibold text-white">Scout a market</h1>
        <p className="mt-1 text-sm text-slate-400">
          Enter a niche, persona or problem space. alphaview crawls demand signals, clusters pain points, enriches
          them with your connected analytics tools and scores the supply gap.
        </p>
        <form
          className="mt-4 flex flex-col gap-3 md:flex-row"
          onSubmit={(e) => {
            e.preventDefault();
            start.mutate();
          }}
        >
          <input
            className="input md:flex-1"
            placeholder='e.g. "small accounting firms", "podcast editing", "pet insurance"'
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            minLength={2}
            maxLength={300}
            required
          />
          <button className="btn justify-center" disabled={start.isPending || selected.length === 0}>
            <Radar className="h-4 w-4" />
            {start.isPending ? "Starting..." : "Run discovery"}
          </button>
        </form>
        <div className="mt-3 flex flex-wrap gap-3">
          {sources.data?.map((s) => (
            <label key={s.id} className="flex items-center gap-2 text-sm text-slate-300">
              <input type="checkbox" checked={selected.includes(s.id)} onChange={() => toggle(s.id)} />
              {s.name}
            </label>
          ))}
        </div>
        {start.error && <p className="mt-2 text-sm text-rose-400">{(start.error as ApiError).message}</p>}
      </section>

      <div className="grid gap-8 lg:grid-cols-3">
        <section className="space-y-3 lg:col-span-2">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">Top opportunities</h2>
          {top.data?.length === 0 && (
            <p className="text-sm text-slate-500">No opportunities yet. Run your first discovery above.</p>
          )}
          <div className="grid gap-4 md:grid-cols-2">
            {top.data?.slice(0, 8).map((o) => <OpportunityCard key={o.id} opp={o} />)}
          </div>
        </section>

        <section className="space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">Recent runs</h2>
          <div className="card divide-y divide-slate-800 p-0">
            {runs.data?.length === 0 && <p className="p-4 text-sm text-slate-500">No runs yet.</p>}
            {runs.data?.map((r) => (
              <Link key={r.id} href={`/runs/${r.id}`} className="flex items-center justify-between p-4 hover:bg-slate-800/50">
                <div>
                  <div className="text-sm text-white">{r.query}</div>
                  <div className="text-xs text-slate-500">
                    {new Date(r.created_at).toLocaleString()} - {r.signal_count} signals
                  </div>
                </div>
                <StatusPill status={r.status} />
              </Link>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
