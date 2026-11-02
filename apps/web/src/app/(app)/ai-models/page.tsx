"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, ExternalLink, ListRestart, RefreshCw, Star, Trash2 } from "lucide-react";
import { useRef, useState } from "react";
import { api, post } from "@/lib/api";
import type { AICredential, AIProvider } from "@/lib/types";

function AddProviderForm({ provider, onDone }: { provider: AIProvider; onDone: () => void }) {
  const qc = useQueryClient();
  const formRef = useRef<HTMLFormElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [model, setModel] = useState(provider.default_model);
  const [available, setAvailable] = useState<string[] | null>(null);

  const pick = (form: FormData, fields: AIProvider["config_fields"]) =>
    Object.fromEntries(fields.map((f) => [f.key, String(form.get(f.key) ?? "")]));

  const loadModels = useMutation({
    mutationFn: () => {
      const form = new FormData(formRef.current!);
      return post<{ models: string[] }>(`ai-providers/${provider.id}/models`, {
        credentials: pick(form, provider.credential_fields),
        config: pick(form, provider.config_fields),
      });
    },
    onSuccess: ({ models }) => {
      setError(null);
      setAvailable(models);
      if (!models.includes(model)) setModel(models[0]);
    },
    onError: (e: Error) => setError(e.message),
  });

  const save = useMutation({
    mutationFn: (form: FormData) =>
      post<AICredential>("ai-credentials", {
        provider: provider.id,
        label: String(form.get("label") ?? provider.name),
        model,
        credentials: pick(form, provider.credential_fields),
        config: pick(form, provider.config_fields),
        make_default: form.get("make_default") === "on",
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["ai-credentials"] });
      onDone();
    },
    onError: (e: Error) => setError(e.message),
  });

  const listId = `models-${provider.id}`;
  return (
    <form
      ref={formRef}
      className="mt-4 space-y-3 border-t border-slate-800 pt-4"
      onSubmit={(e) => {
        e.preventDefault();
        setError(null);
        save.mutate(new FormData(e.currentTarget));
      }}
    >
      <div>
        <label className="label">Label</label>
        <input name="label" className="input" defaultValue={provider.name} required maxLength={120} />
      </div>
      {[...provider.credential_fields, ...provider.config_fields].map((f) => (
        <div key={f.key}>
          <label className="label">
            {f.label}
            {!f.required && <span className="normal-case text-slate-500"> (optional)</span>}
          </label>
          <input
            name={f.key}
            type={f.secret ? "password" : "text"}
            autoComplete="off"
            className="input"
            required={f.required}
            placeholder={f.help ?? ""}
            onChange={() => setAvailable(null)}
          />
        </div>
      ))}
      <div>
        <label className="label">Model</label>
        <div className="flex gap-2">
          {available ? (
            <select className="input" value={model} onChange={(e) => setModel(e.target.value)} required>
              {available.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          ) : (
            <>
              <input
                className="input"
                list={listId}
                value={model}
                onChange={(e) => setModel(e.target.value)}
                placeholder="model or deployment name"
                required
                maxLength={200}
              />
              <datalist id={listId}>
                {provider.models.map((m) => (
                  <option key={m} value={m} />
                ))}
              </datalist>
            </>
          )}
          {provider.can_list_models && (
            <button
              type="button"
              className="btn-ghost shrink-0"
              onClick={() => loadModels.mutate()}
              disabled={loadModels.isPending}
              title="Fetch the models your key can use"
            >
              <ListRestart className="h-4 w-4" />
              {loadModels.isPending ? "Loading..." : "Load models"}
            </button>
          )}
        </div>
        {provider.can_list_models && !available && (
          <p className="mt-1 text-xs text-slate-500">Enter your key, then click Load models to pick from what it can access.</p>
        )}
        {available && <p className="mt-1 text-xs text-emerald-400">{available.length} models available for this key.</p>}
      </div>
      <label className="flex items-center gap-2 text-sm text-slate-300">
        <input type="checkbox" name="make_default" defaultChecked /> Use as default for discovery runs
      </label>
      {error && <p className="text-sm text-rose-400">{error}</p>}
      <div className="flex gap-2">
        <button className="btn" disabled={save.isPending}>
          {save.isPending ? "Testing key..." : "Test & save"}
        </button>
        <button type="button" className="btn-ghost" onClick={onDone}>
          Cancel
        </button>
      </div>
    </form>
  );
}

export default function AIModelsPage() {
  const qc = useQueryClient();
  const [open, setOpen] = useState<string | null>(null);
  const providers = useQuery({ queryKey: ["ai-providers"], queryFn: () => api<AIProvider[]>("ai-providers") });
  const creds = useQuery({ queryKey: ["ai-credentials"], queryFn: () => api<AICredential[]>("ai-credentials") });
  const refresh = () => qc.invalidateQueries({ queryKey: ["ai-credentials"] });

  const makeDefault = useMutation({
    mutationFn: (id: string) => post<AICredential>(`ai-credentials/${id}/default`),
    onSuccess: refresh,
  });
  const test = useMutation({ mutationFn: (id: string) => post<AICredential>(`ai-credentials/${id}/test`), onSuccess: refresh });
  const remove = useMutation({
    mutationFn: (id: string) => api<void>(`ai-credentials/${id}`, { method: "DELETE" }),
    onSuccess: refresh,
  });

  const names = Object.fromEntries((providers.data ?? []).map((p) => [p.id, p.name]));

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-semibold text-white">AI Models</h1>
        <p className="text-sm text-slate-400">
          Bring your own key from any major provider. The <strong className="text-white">default</strong> model writes
          the strategy for every opportunity in your discovery runs. Keys are verified with a tiny test request,
          encrypted at rest and never shown again.
        </p>
      </div>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">Your providers</h2>
        {creds.data?.length === 0 && (
          <p className="text-sm text-slate-500">
            No AI provider added yet - strategies use the built-in heuristic until you add one below.
          </p>
        )}
        {creds.data?.map((c) => (
          <div key={c.id} className="card flex items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 font-medium text-white">
                {c.label}
                {c.is_default && (
                  <span className="rounded-full bg-brand/20 px-2 py-0.5 text-[10px] uppercase text-brand">default</span>
                )}
              </div>
              <div className="text-xs text-slate-500">
                {names[c.provider] ?? c.provider} - {c.model}
                {c.config.api_base && ` - ${c.config.api_base}`}
              </div>
              {c.last_error && <div className="mt-1 text-xs text-rose-400">{c.last_error}</div>}
            </div>
            <div className="flex items-center gap-2">
              <span className={c.status === "active" ? "text-xs text-emerald-400" : "text-xs text-rose-400"}>
                {c.status}
              </span>
              {!c.is_default && (
                <button className="btn-ghost" title="Make default" onClick={() => makeDefault.mutate(c.id)}>
                  <Star className="h-4 w-4" />
                </button>
              )}
              <button className="btn-ghost" title="Test" onClick={() => test.mutate(c.id)} disabled={test.isPending}>
                <RefreshCw className="h-4 w-4" />
              </button>
              <button
                className="btn-ghost"
                title="Remove"
                onClick={() => confirm(`Remove ${c.label}?`) && remove.mutate(c.id)}
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          </div>
        ))}
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">Add a provider</h2>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {providers.data?.map((p) => (
            <div key={p.id} className="card">
              <div className="flex items-start justify-between gap-2">
                <h3 className="font-semibold text-white">{p.name}</h3>
                <a
                  href={p.docs_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1 text-xs text-slate-400 hover:text-brand"
                >
                  Get key <ExternalLink className="h-3 w-3" />
                </a>
              </div>
              {p.models.length > 0 && (
                <p className="mt-1 truncate text-xs text-slate-500">{p.models.slice(0, 3).join(" - ")}</p>
              )}
              {open === p.id ? (
                <AddProviderForm provider={p} onDone={() => setOpen(null)} />
              ) : (
                <button className="btn mt-4" onClick={() => setOpen(p.id)}>
                  <Bot className="h-4 w-4" /> Add
                </button>
              )}
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
