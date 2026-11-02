"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Radar, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { LocationPicker, geoLabel } from "@/components/location-picker";
import { OpportunityCard } from "@/components/opportunity-card";
import { StatusPill } from "@/components/ui";
import { ApiError, api, post } from "@/lib/api";
import type { Opportunity, Place, Run } from "@/lib/types";
import type { ResearchOptions } from "@/lib/types";
import { ResearchControls, QUICK_BUDGET } from "@/components/research-controls";

const ACTIVE = new Set(["queued", "crawling", "analyzing", "enriching", "synthesizing"]);

export default function DashboardPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<string[]>([
    "reddit", "hackernews", "stackexchange", "github", "devto", "mastodon",
  ]);
  const [place, setPlace] = useState<Place | null>(null);
  const [radiusKm, setRadiusKm] = useState(50);
  const [pendingDelete, setPendingDelete] = useState<Run | null>(null);
  const [research,setResearch] = useState<ResearchOptions>({mode:"quick",budget:QUICK_BUDGET,language:"en"});

  const sources = useQuery({ queryKey: ["sources"], queryFn: () => api<{ id: string; name: string }[]>("sources") });
  const runs = useQuery({
    queryKey: ["runs"],
    queryFn: () => api<Run[]>("discovery"),
    refetchInterval: (q) => (q.state.data?.some((r) => ACTIVE.has(r.status)) ? 4000 : false),
  });
  const top = useQuery({ queryKey: ["opportunities"], queryFn: () => api<Opportunity[]>("opportunities?min_score=0") });

  const start = useMutation({
    mutationFn: () =>
      post<Run>("discovery", {
        query,
        sources: research.mode === "deep" ? selected.filter(source => source === "web") : selected,
        location: place ? { ...place, radius_km: radiusKm } : null,
        research,
      }),
    onSuccess: (run) => {
      qc.invalidateQueries({ queryKey: ["runs"] });
      router.push(`/runs/${run.id}`);
    },
  });

  const removeRun = useMutation({
    mutationFn: (id: string) => api<void>(`discovery/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      setPendingDelete(null);
      qc.invalidateQueries({ queryKey: ["runs"] });
      qc.invalidateQueries({ queryKey: ["opportunities"] });
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
          <button className="btn justify-center" disabled={start.isPending || (research.mode === "deep" ? !selected.includes("web") && !research.seed_urls?.length : selected.length === 0)}>
            <Radar className="h-4 w-4" />
            {start.isPending ? "Starting..." : "Run discovery"}
          </button>
        </form>
        <div className="mt-3">
          <ResearchControls value={research} onChange={options=>{
            setResearch(options);
            if(options.mode==="deep") setSelected(current=>current.includes("web")?current:[...current,"web"]);
          }}/>
        </div>
        <div className="mt-3">
          <LocationPicker place={place} radiusKm={radiusKm} onPlaceChange={setPlace} onRadiusChange={setRadiusKm} />
        </div>
        <div className="mt-3 flex flex-wrap gap-3">
          {sources.data?.map((s) => (
            <label key={s.id} className="flex items-center gap-2 text-sm text-slate-300">
              <input type="checkbox" checked={selected.includes(s.id)} onChange={() => toggle(s.id)}
                disabled={research.mode === "deep" && s.id !== "web"}
                title={research.mode === "deep" && s.id !== "web" ? "Community searches remain in Quick mode; Deep can reuse existing Quick evidence" : undefined}/>
              {s.name}
            </label>
          ))}
        </div>
        {selected.includes("web") && (
          <p className="mt-2 text-xs text-slate-400">
            Web search connection: <Link href="/integrations" className="underline">SerpApi or DataForSEO</Link>.
            Up to 15 URLs per run; search-provider charges apply.
          </p>
        )}
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
              <div key={r.id} className="group flex items-center gap-2 pr-3 hover:bg-slate-800/50">
                <Link href={`/runs/${r.id}`} className="flex min-w-0 flex-1 items-center justify-between gap-3 p-4">
                  <div className="min-w-0">
                    <div className="truncate text-sm text-white">{r.query}</div>
                    <div className="text-xs text-slate-500">
                      {new Date(r.created_at).toLocaleString()} - {r.signal_count} signals - {geoLabel(r.geo)}
                    </div>
                  </div>
                  <StatusPill status={r.status} />
                </Link>
                <button
                  className="rounded p-1.5 text-slate-500 opacity-60 hover:bg-slate-700 hover:text-rose-400 group-hover:opacity-100 disabled:opacity-30"
                  title="Delete run"
                  aria-label={`Delete run ${r.query}`}
                  disabled={removeRun.isPending}
                  onClick={() => {
                    removeRun.reset();
                    setPendingDelete(r);
                  }}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        </section>
      </div>

      <ConfirmDialog
        open={pendingDelete !== null}
        tone="danger"
        title="Delete this run?"
        description={
          pendingDelete && (
            <>
              <span className="font-medium text-slate-200">&ldquo;{pendingDelete.query}&rdquo;</span> and all of its
              opportunities will be permanently deleted.
              {ACTIVE.has(pendingDelete.status) && (
                <span className="mt-2 block text-amber-300">This run is still in progress and will be stopped.</span>
              )}
            </>
          )
        }
        confirmLabel={removeRun.isPending ? "Deleting..." : "Delete run"}
        loading={removeRun.isPending}
        error={removeRun.error?.message}
        onConfirm={() => pendingDelete && removeRun.mutate(pendingDelete.id)}
        onCancel={() => setPendingDelete(null)}
      />
    </div>
  );
}
