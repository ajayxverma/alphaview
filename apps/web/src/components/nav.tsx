"use client";

import clsx from "clsx";
import { Activity, LayoutDashboard, LogOut, Plug } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

const LINKS = [
  { href: "/dashboard", label: "Discovery", icon: LayoutDashboard },
  { href: "/integrations", label: "Integrations", icon: Plug },
];

export function Nav() {
  const pathname = usePathname();
  const router = useRouter();

  async function logout() {
    await fetch("/api/auth/logout", { method: "POST" });
    router.replace("/login");
    router.refresh();
  }

  return (
    <header className="border-b border-slate-800 bg-slate-950/80 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center gap-6 px-6 py-3">
        <Link href="/dashboard" className="flex items-center gap-2 text-lg font-semibold text-white">
          <Activity className="h-5 w-5 text-brand" />
          alpha<span className="-ml-2 text-brand">view</span>
        </Link>
        <nav className="flex gap-1">
          {LINKS.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              className={clsx(
                "flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm",
                pathname.startsWith(href) ? "bg-slate-800 text-white" : "text-slate-400 hover:text-white",
              )}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          ))}
        </nav>
        <button onClick={logout} className="btn-ghost ml-auto">
          <LogOut className="h-4 w-4" /> Sign out
        </button>
      </div>
    </header>
  );
}
