"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plug, RefreshCw, Search, Trash2 } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { num } from "@/components/ui";
import { api, post } from "@/lib/api";
import type { Connection, Connector, KeywordMetrics } from "@/lib/types";

function ConnectForm({ connector, onDone }: { connector: Connector; onDone: () => void }) {
  const qc = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  const submit = useMutation({
    mutationFn: async (form: FormData) => {
      const pick = (fields: Connector["config_fields"]) =>
        Object.fromEntries(fields.map((f) => [f.key, String(form.get(f.key) ?? "")]));
      const label = String(form.get("label") ?? connector.name);
      const config = pick(connector.config_fields);
      if (connector.auth_type === "oauth2") {
        const { authorization_url } = await post<{ authorization_url: string }>(
          `connections/oauth/${connector.id}/start`,
          { label, config },
        );
        window.location.href = authorization_url;
        return;
      }
      await post<Connection>("connections", {
        provider: connector.id,
        label,
        config,
        credentials: pick(connector.credential_fields),
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["connections"] });
      if (connector.auth_type === "api_key") onDone();
    },
    onError: (e: Error) => setError(e.message),
  });

  return (
    <form
      className="mt-4 space-y-3 border-t border-slate-800 pt-4"
      onSubmit={(e) => {
        e.preventDefault();
        setError(null);
        submit.mutate(new FormData(e.currentTarget));
      }}
    >
      <div>
        <label className="label">Label</label>
        <input name="label" className="input" defaultValue={connector.name} required maxLength={120} />
      </div>
      {[...connector.credential_fields, ...connector.config_fields].map((f) => (
        <div key={f.key}>
          <label className="label">{f.label}</label>
          <input
            name={f.key}
            type={f.secret ? "password" : "text"}
            autoComplete="off"
            className="input"
            required={f.required}
            placeholder={f.help ?? ""}
          />
        </div>
      ))}
      {error && <p className="text-sm text-rose-400">{error}</p>}
      <div className="flex gap-2">
        <button className="btn" disabled={submit.isPending}>
          {submit.isPending ? "Verifying..." : connector.auth_type === "oauth2" ? "Continue with Google" : "Test & save"}
        </button>
        <button type="button" className="btn-ghost" onClick={onDone}>
          Cancel
        </button>
      </div>
    </form>
  );
}

function QueryPanel({ connection }: { connection: Connection }) {
  const [keywords, setKeywords] = useState("");
  const run = useMutation({
    mutationFn: () =>
      post<KeywordMetrics>(`connections/${connection.id}/query`, {
        keywords: keywords.split(",").map((k) => k.trim()).filter(Boolean).slice(0, 20),
      }),
  });
  const columns = run.data ? [...new Set(Object.values(run.data).flatMap((m) => Object.keys(m)))] : [];

  return (
    <div className="mt-3 space-y-2">
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          run.mutate();
        }}
      >
        <input
          className="input"
          placeholder="Comma-separated keywords, e.g. invoice automation, ai bookkeeping"
          value={keywords}
          onChange={(e) => setKeywords(e.target.value)}
          required
        />
        <button className="btn-ghost" disabled={run.isPending}>
          <Search className="h-4 w-4" /> {run.isPending ? "..." : "Query"}
        </button>
      </form>
      {run.error && <p className="text-sm text-rose-400">{run.error.message}</p>}
      {run.data && (
        <table className="w-full text-left text-sm">
          <thead className="text-xs uppercase text-slate-500">
            <tr>
              <th className="py-1">Keyword</th>
              {columns.map((c) => (
                <th key={c} className="py-1">{c.replace(/_/g, " ")}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Object.entries(run.data).map(([kw, m]) => (
              <tr key={kw} className="border-t border-slate-800">
                <td className="py-1 text-white">{kw}</td>
                {columns.map((c) => (
                  <td key={c} className="py-1 font-semibold">{m[c] !== undefined ? num(m[c]) : "-"}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function IntegrationsContent() {
  const params = useSearchParams();
  const qc = useQueryClient();
  const [open, setOpen] = useState<string | null>(null);
  const [queryOpen, setQueryOpen] = useState<string | null>(null);

  const connectors = useQuery({ queryKey: ["connectors"], queryFn: () => api<Connector[]>("connectors") });
  const connections = useQuery({ queryKey: ["connections"], queryFn: () => api<Connection[]>("connections") });
  const refresh = () => qc.invalidateQueries({ queryKey: ["connections"] });

  const test = useMutation({ mutationFn: (id: string) => post<Connection>(`connections/${id}/test`), onSuccess: refresh });
  const remove = useMutation({
    mutationFn: (id: string) => api<void>(`connections/${id}`, { method: "DELETE" }),
    onSuccess: refresh,
  });

  const names = Object.fromEntries((connectors.data ?? []).map((c) => [c.id, c.name]));

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-semibold text-white">Integrations</h1>
        <p className="text-sm text-slate-400">
          Connect analytics and market tools. Every discovery run automatically enriches pain-point clusters with
          hard metrics from all active connections. Credentials are encrypted at rest.
        </p>
      </div>

      {params.get("connected") && (
        <p className="rounded-lg border border-emerald-800 bg-emerald-950 p-3 text-sm text-emerald-300">
          Connected {names[params.get("connected")!] ?? params.get("connected")}.
        </p>
      )}
      {params.get("error") && (
        <p className="rounded-lg border border-rose-800 bg-rose-950 p-3 text-sm text-rose-300">{params.get("error")}</p>
      )}

      <section className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">Your connections</h2>
        {connections.data?.length === 0 && <p className="text-sm text-slate-500">No tools connected yet.</p>}
        {connections.data?.map((c) => (
          <div key={c.id} className="card">
            <div className="flex items-center justify-between gap-4">
              <div>
                <div className="font-medium text-white">{c.label}</div>
                <div className="text-xs text-slate-500">
                  {names[c.provider] ?? c.provider}
                  {Object.entries(c.config).map(([k, v]) => ` - ${k}: ${v}`)}
                </div>
                {c.last_error && <div className="mt-1 text-xs text-rose-400">{c.last_error}</div>}
              </div>
              <div className="flex items-center gap-2">
                <span className={c.status === "active" ? "text-xs text-emerald-400" : "text-xs text-rose-400"}>
                  {c.status}
                </span>
                <button className="btn-ghost" onClick={() => setQueryOpen(queryOpen === c.id ? null : c.id)}>
                  <Search className="h-4 w-4" />
                </button>
                <button className="btn-ghost" onClick={() => test.mutate(c.id)} disabled={test.isPending}>
                  <RefreshCw className="h-4 w-4" />
                </button>
                <button
                  className="btn-ghost"
                  onClick={() => confirm(`Disconnect ${c.label}?`) && remove.mutate(c.id)}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>
            {queryOpen === c.id && <QueryPanel connection={c} />}
          </div>
        ))}
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">Available tools</h2>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {connectors.data?.map((c) => (
            <div key={c.id} className="card">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <h3 className="font-semibold text-white">{c.name}</h3>
                  <p className="mt-1 text-sm text-slate-400">{c.description}</p>
                </div>
                <span className="rounded bg-slate-800 px-2 py-0.5 text-[10px] uppercase text-slate-400">
                  {c.auth_type === "oauth2" ? "OAuth" : "API key"}
                </span>
              </div>
              <div className="mt-3 flex flex-wrap gap-1">
                {c.capabilities.map((cap) => (
                  <span key={cap} className="rounded-full bg-brand/15 px-2 py-0.5 text-[11px] text-brand">
                    {cap.replace(/_/g, " ")}
                  </span>
                ))}
              </div>
              {open === c.id ? (
                <ConnectForm connector={c} onDone={() => setOpen(null)} />
              ) : (
                <button className="btn mt-4" disabled={!c.available} onClick={() => setOpen(c.id)}>
                  <Plug className="h-4 w-4" />
                  {c.available ? "Connect" : "Server OAuth not configured"}
                </button>
              )}
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

export default function IntegrationsPage() {
  return (
    <Suspense>
      <IntegrationsContent />
    </Suspense>
  );
}
