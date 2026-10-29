"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { detailMessage } from "@/lib/api";

function safeNext(value: string | null): string {
  return value && value.startsWith("/") && !value.startsWith("//") ? value : "/dashboard";
}

function AuthForm({ mode }: { mode: "login" | "register" }) {
  const router = useRouter();
  const params = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    const form = Object.fromEntries(new FormData(e.currentTarget));
    const res = await fetch(`/api/auth/${mode}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(form),
    });
    setLoading(false);
    if (!res.ok) {
      setError(detailMessage(await res.json().catch(() => null)));
      return;
    }
    router.replace(safeNext(params.get("next")));
    router.refresh();
  }

  const isLogin = mode === "login";
  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <form onSubmit={onSubmit} className="card w-full max-w-sm space-y-4">
        <div>
          <h1 className="text-2xl font-semibold text-white">
            alpha<span className="text-brand">view</span>
          </h1>
          <p className="mt-1 text-sm text-slate-400">
            {isLogin ? "Sign in to your market-intelligence workspace." : "Create your workspace."}
          </p>
        </div>
        {!isLogin && (
          <div>
            <label className="label" htmlFor="name">Name</label>
            <input id="name" name="name" required maxLength={120} className="input" />
          </div>
        )}
        <div>
          <label className="label" htmlFor="email">Email</label>
          <input id="email" name="email" type="email" required autoComplete="email" className="input" />
        </div>
        <div>
          <label className="label" htmlFor="password">Password</label>
          <input
            id="password"
            name="password"
            type="password"
            required
            minLength={isLogin ? 1 : 10}
            autoComplete={isLogin ? "current-password" : "new-password"}
            className="input"
          />
        </div>
        {error && <p className="text-sm text-rose-400">{error}</p>}
        <button className="btn w-full justify-center" disabled={loading}>
          {loading ? "Please wait..." : isLogin ? "Sign in" : "Create account"}
        </button>
        <p className="text-center text-sm text-slate-400">
          {isLogin ? "No account? " : "Already registered? "}
          <Link className="text-brand hover:underline" href={isLogin ? "/register" : "/login"}>
            {isLogin ? "Create one" : "Sign in"}
          </Link>
        </p>
      </form>
    </main>
  );
}

export function AuthPage({ mode }: { mode: "login" | "register" }) {
  return (
    <Suspense>
      <AuthForm mode={mode} />
    </Suspense>
  );
}
