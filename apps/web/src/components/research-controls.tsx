"use client";

import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Search } from "lucide-react";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { post } from "@/lib/api";
import type { ResearchBudget, ResearchOptions } from "@/lib/types";

export const QUICK_BUDGET: ResearchBudget = {seconds:180,pages:15,queries:6,paid_calls:6,rounds:1,requests:120};
export const DEEP_BUDGET: ResearchBudget = {seconds:600,pages:15,queries:12,paid_calls:12,rounds:3,requests:120};
export const ADDITIONAL_BUDGET: ResearchBudget = {seconds:300,pages:5,queries:6,paid_calls:6,rounds:1,requests:40};

export function BudgetFields({value,onChange}:{value:ResearchBudget;onChange:(budget:ResearchBudget)=>void}) {
  const fields: [keyof ResearchBudget,string,number,number][] = [
    ["seconds","Time limit (seconds)",30,1800],["pages","Page/read limit",1,100],["queries","Query limit",1,30],
    ["paid_calls","Paid search-call limit",0,30],["rounds","Round limit",1,5],["requests","Network request limit",1,2000],
  ];
  return <div className="grid gap-3 sm:grid-cols-2">{fields.map(([key,label,min,max])=>(
    <label key={key} className="text-xs text-slate-400">{label}<input type="number" min={min} max={max} step={1}
      className="input mt-1" value={value[key]} onChange={event=>onChange({...value,[key]:Number(event.target.value)})}/></label>
  ))}</div>;
}

export function ResearchControls({value,onChange}:{value:ResearchOptions;onChange:(options:ResearchOptions)=>void}) {
  return <div className="space-y-3">
    <fieldset className="flex gap-4 text-sm text-slate-300"><legend className="sr-only">Research mode</legend>
      {(["quick","deep"] as const).map(mode=><label key={mode} className="flex items-center gap-2">
        <input type="radio" name="research-mode" checked={value.mode===mode} onChange={()=>onChange({...value,mode,budget:mode==="deep"?DEEP_BUDGET:QUICK_BUDGET})}/>
        {mode==="deep"?"Deep research":"Quick discovery"}</label>)}
    </fieldset>
    {value.mode==="deep" && <details open className="space-y-3"><summary className="cursor-pointer text-sm text-slate-400">Research scope and limits</summary>
      <p className="text-xs text-amber-300">Deep uses your search-provider quota. Limits are ceilings, not completion promises. Seed-only research can use zero paid calls.</p>
      <p className="text-xs text-slate-400">Deep reads discovered webpages and seed URLs. Community searches remain in Quick mode; Investigate further reuses their collected evidence.</p>
      <BudgetFields value={value.budget} onChange={budget=>onChange({...value,budget})}/>
      <div className="grid gap-3 sm:grid-cols-3">
        <label className="text-xs text-slate-400">Language code<input className="input mt-1" value={value.language??"en"} maxLength={2} onChange={event=>onChange({...value,language:event.target.value})}/></label>
        <label className="text-xs text-slate-400">From date<input type="date" className="input mt-1" value={value.date_from??""} onChange={event=>onChange({...value,date_from:event.target.value||null})}/></label>
        <label className="text-xs text-slate-400">To date<input type="date" className="input mt-1" value={value.date_to??""} onChange={event=>onChange({...value,date_to:event.target.value||null})}/></label>
      </div>
      {(["preferred_domains","excluded_domains","seed_urls"] as const).map(key=><label key={key} className="block text-xs text-slate-400">
        {key==="seed_urls"?"HTTPS seed URLs (one per line)":key==="preferred_domains"?"Preferred domains (one per line)":"Excluded domains (one per line)"}
        <textarea className="input mt-1" rows={2} value={(value[key]??[]).join("\n")} onChange={event=>onChange({...value,[key]:event.target.value.split("\n").map(item=>item.trim()).filter(Boolean)})}/>
      </label>)}
    </details>}
  </div>;
}

export function InvestigateButton({opportunityId}:{opportunityId:string}) {
  const [open,setOpen]=useState(false);
  const [budget,setBudget]=useState(ADDITIONAL_BUDGET);
  const router=useRouter();
  const investigate=useMutation({mutationFn:()=>post<{run_id:string}>(`opportunities/${opportunityId}/investigate`,{additional_budget:budget}),
    onSuccess:response=>router.push(`/runs/${response.run_id}`)});
  return <><button className="btn-ghost" onClick={()=>{investigate.reset();setOpen(true);}}><Search className="h-4 w-4"/>Investigate further</button>
    <ConfirmDialog open={open} title="Authorize deeper research" description={<div className="space-y-3"><p>Existing evidence and reports are retained. Additional searches may incur provider charges.</p><BudgetFields value={budget} onChange={setBudget}/></div>}
      loading={investigate.isPending} error={investigate.error?.message} confirmLabel="Start research" onConfirm={()=>investigate.mutate()} onCancel={()=>setOpen(false)}/>
  </>;
}