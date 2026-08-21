"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import type { Occupation } from "@/types/occupation";

const views = ["Most exposed", "Most AI-resistant", "Highest replacement risk", "Lowest replacement risk"] as const;

export function RankingsExplorer({ occupations }: { occupations: Occupation[] }) {
  const [view, setView] = useState<(typeof views)[number]>(views[0]);
  const [query, setQuery] = useState("");
  const jobs = useMemo(() => {
    const filtered = occupations.filter((job) => `${job.title} ${job.category}`.toLowerCase().includes(query.toLowerCase()));
    return filtered.sort((a, b) => view === "Most exposed" ? b.aiExposure - a.aiExposure : view === "Most AI-resistant" || view === "Lowest replacement risk" ? a.replacementRisk - b.replacementRisk : b.replacementRisk - a.replacementRisk);
  }, [occupations, query, view]);
  return <>
    <div className="filter-panel"><label><span className="sr-only">Search rankings</span><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search by job or profession…" /></label><div className="tab-list" role="tablist" aria-label="Ranking views">{views.map((item) => <button key={item} role="tab" aria-selected={view === item} className={view === item ? "active" : ""} onClick={() => setView(item)}>{item}</button>)}</div></div>
    <div className="card ranking-table"><div className="ranking-row ranking-header"><b>#</b><b>Occupation</b><b>Category</b><b>AI Exposure</b><b>Replacement Risk</b><span></span></div>{jobs.map((job, index) => <div className="ranking-row" key={job.slug}><strong className="rank-number">{index + 1}</strong><div><b>{job.title}</b><span className="mobile-category">{job.category}</span></div><span>{job.category}</span><b>{job.aiExposure}</b><b>{job.replacementRisk}</b><Link className="button secondary" href={`/jobs/${job.slug}`}>View <span aria-hidden="true">→</span></Link></div>)}{jobs.length === 0 && <div className="empty-state">{occupations.length === 0 ? "No occupations are published yet." : `No occupations match “${query}”.`}</div>}</div>
  </>;
}
