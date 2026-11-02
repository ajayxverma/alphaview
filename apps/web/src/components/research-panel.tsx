"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, Search } from "lucide-react";
import { useState } from "react";
import { api, post } from "@/lib/api";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { ADDITIONAL_BUDGET, BudgetFields } from "@/components/research-controls";

interface Claim {id:string;text:string;quotation:string;url:string;passage_id:string;status:string;question_id:string;kind:string}

interface ResearchOverview {
  available: boolean;
  mode: string;
  phase: string;
  planner: string;
  retrieval: string;
  documents: number;
  stop_reason: string | null;
  complete: boolean;
  round: number;
  candidates: number;
  deadline: string | null;
  budget: Record<string,number> | null;
  usage: Record<string,number|string>;
  coverage: Record<string,{domains:string[];adequate:boolean}>;
  reports: {version:number;report:{claims:Claim[];complete:boolean;stop_reason:string;limitations:string[];potential_conflicts?:{description:string;claim_ids:string[]}[]}}[];
  unresolved: string[];
  limitations: string[];
  attempts: { source: string; query: string; outcome: string; detail: string; signal_count: number; requested_url?: string | null; final_url?: string | null }[];
}

interface EvidenceSearch {
  retrieval: string;
  ranking: string;
  results: { id: string; document_id: string; text: string; title: string; final_url: string; source: string;
    document_type: string; published_at: string | null; date_uncertainty: string }[];
}

export function ResearchPanel({ runId, active }: { runId: string; active: boolean }) {
  const [term, setTerm] = useState("");
  const [source, setSource] = useState("");
  const [type, setType] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [submitted, setSubmitted] = useState("");
  const [action,setAction]=useState<"cancel"|"continue"|null>(null);
  const [budget,setBudget]=useState(ADDITIONAL_BUDGET);
  const [version,setVersion]=useState(0);
  const qc=useQueryClient();
  const overview = useQuery({queryKey: ["research", runId], queryFn: () => api<ResearchOverview>(`discovery/${runId}/research`),
    refetchInterval: active ? 4000 : false});
  const evidence = useQuery({queryKey: ["evidence-search", runId, submitted],
    queryFn: () => api<EvidenceSearch>(`discovery/${runId}/evidence?${submitted}`), enabled: Boolean(submitted)});
  const control=useMutation({mutationFn:()=>post(`discovery/${runId}/${action}`,action==="continue"?{additional_budget:budget}:undefined),
    onSuccess:()=>{setAction(null);qc.invalidateQueries({queryKey:["research",runId]});qc.invalidateQueries({queryKey:["run",runId]});}});
  const selectedReport=overview.data?.reports?.find(item=>item.version===version)??overview.data?.reports?.[0];

  return (
    <section className="card space-y-4">
      <h2 className="text-sm font-semibold text-white">Research evidence</h2>
      {overview.error && <p className="text-sm text-rose-400">{overview.error.message}</p>}
      {overview.data && (
        <>
          <div className="flex flex-wrap gap-x-5 gap-y-2 text-sm text-slate-400">
            <span>Mode: {overview.data.mode}</span><span>Phase: {overview.data.phase}</span>
            <span>{overview.data.documents} evidence documents</span><span>Retrieval: lexical-only</span>
            {overview.data.mode==="deep" && <span>Round {overview.data.round}</span>}
          </div>
          {overview.data.mode==="deep" && <>
            <div className="flex flex-wrap gap-3 text-xs text-slate-400">
              {["pages","queries","paid_calls","requests"].map(key=><span key={key}>{key === "paid_calls" ? "paid-call reservations" : key.replaceAll("_"," ")}: {overview.data?.usage[key]??0} / {overview.data?.budget?.[key]??"-"}</span>)}
              <span>{overview.data.candidates} candidate records</span>
              {overview.data.deadline && <span>Request authorization ends: {new Date(overview.data.deadline).toLocaleTimeString()}</span>}
            </div>
            <button className="btn-ghost" onClick={()=>{control.reset();setAction(active?"cancel":"continue");}}>{active?"Cancel research":"Continue with additional budget"}</button>
            {Object.keys(overview.data.coverage??{}).length>0 && <dl className="grid gap-2 sm:grid-cols-2 text-xs">
              {Object.entries(overview.data.coverage).map(([question,coverage])=><div key={question} className="text-slate-400">
                <dt className="font-medium text-white">{question}</dt><dd>{coverage.domains.length} independent domains · {coverage.adequate?"coverage threshold met":"more evidence needed"}</dd>
              </div>)}
            </dl>}
          </>}
          {overview.data.stop_reason && <p className="text-sm text-slate-400">Stop reason: {overview.data.stop_reason.replaceAll("_", " ")}</p>}
          <details className="text-sm text-slate-400">
            <summary className="cursor-pointer">Completeness and limitations</summary>
            <ul className="mt-2 list-disc space-y-1 pl-5">
              {overview.data.limitations.map(item => <li key={item}>{item}</li>)}
              {overview.data.unresolved.length > 0 && <li>Unverified research questions: {overview.data.unresolved.join(", ")}</li>}
            </ul>
          </details>
          {overview.data.attempts.length > 0 && (
            <details>
              <summary className="cursor-pointer text-sm text-white">Recent source outcomes ({overview.data.attempts.length})</summary>
              <ul className="mt-2 max-h-72 divide-y divide-slate-800 overflow-auto">
                {overview.data.attempts.map((attempt, index) => (
                  <li key={index} className="space-y-1 py-2 text-xs">
                    <p className="flex flex-wrap gap-2">
                      <strong className="text-slate-300">{attempt.source}</strong>
                      <span className={attempt.outcome === "fetched" ? "text-emerald-400" : "text-amber-300"}>{attempt.outcome.replaceAll("_", " ")}</span>
                      <span className="text-slate-500">{attempt.signal_count} signals</span>
                    </p>
                    <p className="break-words text-slate-400">{attempt.query}</p>
                    {attempt.requested_url && <p className="break-all text-slate-500">{attempt.requested_url}</p>}
                    <p className="text-slate-500">{attempt.detail}</p>
                  </li>
                ))}
              </ul>
            </details>
          )}
        </>
      )}
      {selectedReport && <div className="space-y-3 border-t border-slate-800 pt-3">
        <label className="flex items-center gap-2 text-sm text-white">Report version
          <select className="input w-24" value={selectedReport.version} onChange={event=>setVersion(Number(event.target.value))}>
            {overview.data?.reports.map(item=><option key={item.version} value={item.version}>{item.version}</option>)}
          </select>
        </label>
        <p className="text-xs text-amber-300">{selectedReport.report.complete?"Coverage threshold met; source claims still require judgement.":"Incomplete research; unresolved questions or a stop limit remain."}</p>
        <ul className="space-y-1 text-xs text-slate-400">{selectedReport.report.limitations.map(item=><li key={item}>{item}</li>)}</ul>
        {selectedReport.report.claims.map(claim=><article key={claim.id} className="space-y-2 border-b border-slate-800 py-3">
          <p className="text-xs text-slate-500">{claim.question_id} · {claim.kind} · {claim.status} source attribution</p>
          <p className="break-words text-sm text-slate-200">{claim.text}</p>
          <blockquote className="border-l-2 border-slate-700 pl-3 text-sm text-slate-400">{claim.quotation}</blockquote>
          <a className="text-xs text-brand underline" href={claim.url} target="_blank" rel="noopener noreferrer">Open supporting source</a>
          <p className="break-all text-xs text-slate-500">Claim {claim.id} · Passage {claim.passage_id}</p>
        </article>)}
        {selectedReport.report.potential_conflicts?.map((conflict,index)=><p key={index} className="text-xs text-amber-300">Needs review: {conflict.description}</p>)}
      </div>}
      <ConfirmDialog open={action!==null} tone={action==="cancel"?"danger":"default"}
        title={action==="cancel"?"Cancel research without deleting evidence?":"Authorize additional research budget"}
        description={action==="cancel"?"The current bounded operation may finish. Collected evidence and existing reports are retained.":
          <div className="space-y-3"><p>Completed work is reused. New searches may incur provider charges.</p><BudgetFields value={budget} onChange={setBudget}/></div>}
        onCancel={()=>setAction(null)} onConfirm={()=>control.mutate()} confirmLabel={action==="cancel"?"Cancel research":"Continue research"}
        loading={control.isPending} error={control.error?.message}/>
      <form className="space-y-3 border-t border-slate-800 pt-4" onSubmit={event => {
        event.preventDefault();
        const params = new URLSearchParams({q: term});
        if (source) params.set("source", source);
        if (type) params.set("document_type", type);
        if (from) params.set("date_from", `${from}T00:00:00Z`);
        if (to) params.set("date_to", `${to}T23:59:59Z`);
        setSubmitted(params.toString());
      }}>
        <div className="flex gap-2">
          <input aria-label="Search evidence" className="input min-w-0" value={term} onChange={event => setTerm(event.target.value)}
            required maxLength={300} placeholder="Search stored passages" />
          <button className="btn" disabled={evidence.isFetching}><Search className="h-4 w-4" /> Search</button>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <label className="text-xs text-slate-400">Source
            <input className="input mt-1" value={source} onChange={event => setSource(event.target.value)} placeholder="Any source" maxLength={60} />
          </label>
          <label className="text-xs text-slate-400">Document type
            <select className="input mt-1" value={type} onChange={event => setType(event.target.value)}>
              <option value="">Any type</option>
              {["discussion", "article", "product", "pricing", "documentation", "reference"].map(value => <option key={value}>{value}</option>)}
            </select>
          </label>
          <label className="text-xs text-slate-400">Published from<input type="date" className="input mt-1" value={from} onChange={event => setFrom(event.target.value)} /></label>
          <label className="text-xs text-slate-400">Published to<input type="date" className="input mt-1" value={to} onChange={event => setTo(event.target.value)} /></label>
        </div>
      </form>
      {evidence.error && <p className="text-sm text-rose-400">{evidence.error.message}</p>}
      {evidence.data && (
        <div className="space-y-3">
          <p className="text-xs text-slate-500">{evidence.data.ranking}</p>
          {evidence.data.results.length === 0 && <p className="text-sm text-slate-400">No matching stored passages.</p>}
          {evidence.data.results.map(result => (
            <article key={result.id} className="space-y-2 border-b border-slate-800 pb-3">
              <a href={result.final_url} target="_blank" rel="noopener noreferrer" className="flex items-start gap-2 text-sm text-slate-200 hover:text-brand">
                {result.title}<ExternalLink className="h-3 w-3 shrink-0" />
              </a>
              <p className="break-words whitespace-pre-wrap text-sm text-slate-400">{result.text}</p>
              <p className="break-words text-xs text-slate-500">{result.source} · {result.document_type} · {result.published_at ? new Date(result.published_at).toLocaleDateString() : "Publication date unknown"}</p>
              <p className="break-all text-xs text-slate-500">Passage ID: {result.id}</p>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}