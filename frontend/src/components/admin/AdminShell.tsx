import Link from "next/link";
import type { ReactNode } from "react";
import { Logo } from "../Logo";

const links = [["Overview", "/admin"], ["Occupations", "/admin/jobs"], ["Scoring", "/admin/scores"], ["Production scores", "/admin/production-scores"], ["Phase 4A/4B pilot", "/admin/phase4a"], ["Phase 4C validation", "/admin/phase4c"], ["Phase 4D proxies", "/admin/phase4d"], ["Phase 5 corpus", "/admin/phase5"], ["Archetype pilot", "/admin/archetypes"], ["AI taxonomy", "/admin/ai-enrichment"], ["Imports", "/admin/imports"], ["System", "/admin/system"]];

export function AdminShell({ children, title, eyebrow = "Internal data console", action, modelVersion, modelUpdated }: { children: ReactNode; title: string; eyebrow?: string; action?: ReactNode; modelVersion?: string; modelUpdated?: string }) {
  return <div className="admin-page"><header className="admin-header"><Logo /><span>Internal data console</span><details className="admin-mobile-menu"><summary>Console menu</summary><nav>{links.map(([label, href]) => <Link key={href} href={href}>{label}</Link>)}</nav></details><Link className="admin-public-link" href="/">View public site ↗</Link></header><div className="admin-layout"><aside className="admin-sidebar"><strong>DATA CONSOLE</strong><nav>{links.map(([label, href]) => <Link key={href} href={href}>{label}</Link>)}</nav><div className="admin-model"><span>Score source</span><b>{modelVersion ?? "Live API"}</b><small>{modelUpdated ? `Updated ${formatDate(modelUpdated)}` : "PostgreSQL-backed"}</small></div></aside><main className="admin-main"><div className="admin-title"><div><span className="section-kicker">{eyebrow}</span><h1>{title}</h1></div>{action}</div>{children}</main></div></div>;
}

export function Status({ children, tone = "ok" }: { children: ReactNode; tone?: "ok" | "warn" | "error" }) { return <span className={`status ${tone}`}><i></i>{children}</span>; }

function formatDate(value: string) { return new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)); }
