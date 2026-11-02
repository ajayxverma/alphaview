"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { Check, MapPin, Trash2 } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { geoLabel } from "@/components/location-picker";
import { OpportunityCard } from "@/components/opportunity-card";
import { ResearchPanel } from "@/components/research-panel";
import { StatusPill } from "@/components/ui";
import { api } from "@/lib/api";
import type { RunDetail, RunStatus } from "@/lib/types";

const STAGES: RunStatus[] = ["crawling", "analyzing", "enriching", "synthesizing", "completed"];
const LABELS: Record<string, string> = {
  crawling: "Crawl signals",
  analyzing: "Cluster pain points",
  enriching: "Enrich with analytics",
  synthesizing: "Score & synthesize",
  completed: "Done",
};

export default function RunPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const qc = useQueryClient();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const { data: run, error } = useQuery({
    queryKey: ["run", id],
    queryFn: () => api<RunDetail>(`discovery/${id}`),
    refetchInterval: (q) => {
      const s = q.state.data?.status;
      return s === "completed" || s === "failed" || s === "cancelled" ? false : 3000;
    },
  });
  const remove = useMutation({
    mutationFn: () => api<void>(`discovery/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      qc.removeQueries({ queryKey: ["run", id] });
      qc.invalidateQueries({ queryKey: ["runs"] });
      qc.invalidateQueries({ queryKey: ["opportunities"] });
      router.replace("/dashboard");
    },
  });

  if (error) return <p className="text-rose-400">{error.message}</p>;
  if (!run) return <p className="text-slate-500">Loading...</p>;

  const current = STAGES.indexOf(run.status);
  const inProgress = run.status !== "completed" && run.status !== "failed" && run.status !== "cancelled";

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">{run.query}</h1>
          <p className="text-sm text-slate-500">
            {run.sources.join(", ")} - <strong className="text-slate-300">{run.signal_count}</strong> signals
          </p>
          <p className="mt-1 flex items-center gap-1 text-sm text-slate-400" title={run.geo?.label}>
            <MapPin className="h-3.5 w-3.5" /> {geoLabel(run.geo)}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <StatusPill status={run.status} />
          <button
            className="btn-ghost hover:text-rose-400"
            onClick={() => {
              remove.reset();
              setConfirmOpen(true);
            }}
          >
            <Trash2 className="h-4 w-4" /> Delete
          </button>
        </div>
      </div>

      <ConfirmDialog
        open={confirmOpen}
        tone="danger"
        title="Delete this run?"
        description={
          <>
            <span className="font-medium text-slate-200">&ldquo;{run.query}&rdquo;</span> and all of its opportunities
            will be permanently deleted.
            {inProgress && (
              <span className="mt-2 block text-amber-300">This run is still in progress and will be stopped.</span>
            )}
          </>
        }
        confirmLabel={remove.isPending ? "Deleting..." : "Delete run"}
        loading={remove.isPending}
        error={remove.error?.message}
        onConfirm={() => remove.mutate()}
        onCancel={() => setConfirmOpen(false)}
      />

      <ResearchPanel runId={id} active={inProgress} />

      <ol className={run.research_config?.mode === "deep" ? "hidden" : "card flex flex-wrap gap-6"}>
        {STAGES.map((stage, i) => {
          const done = run.status === "completed" || (current > i && run.status !== "failed");
          const active = current === i && run.status !== "completed";
          return (
            <li key={stage} className="flex items-center gap-2 text-sm">
              <span
                className={clsx(
                  "flex h-6 w-6 items-center justify-center rounded-full border text-xs",
                  done && "border-emerald-500 bg-emerald-500/20 text-emerald-300",
                  active && "animate-pulse border-brand text-brand",
                  !done && !active && "border-slate-700 text-slate-500",
                )}
              >
                {done ? <Check className="h-3 w-3" /> : i + 1}
              </span>
              <span className={done || active ? "text-white" : "text-slate-500"}>{LABELS[stage]}</span>
            </li>
          );
        })}
      </ol>

      {run.error && (
        <p className={clsx("text-sm", run.status === "failed" ? "text-rose-400" : "text-slate-400")}>{run.error}</p>
      )}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {run.opportunities.map((o) => (
          <OpportunityCard key={o.id} opp={o} />
        ))}
      </div>
    </div>
  );
}
