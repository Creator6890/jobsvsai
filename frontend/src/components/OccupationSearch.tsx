"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import type { Occupation } from "@/types/occupation";
import { trackEvent } from "@/lib/analytics";

type SearchState = "idle" | "searching" | "not-found" | "error";

export function OccupationSearch({ popularOccupations }: { popularOccupations: Occupation[] }) {
  const [query, setQuery] = useState("");
  const [phase, setPhase] = useState<"search" | "loading" | "result">("search");
  const [selected, setSelected] = useState<Occupation | null>(null);
  const [matches, setMatches] = useState<Occupation[]>([]);
  const [searchState, setSearchState] = useState<SearchState>("idle");

  useEffect(() => {
    const trimmed = query.trim();
    if (trimmed.length < 2 || selected) {
      return;
    }
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setSearchState("searching");
      try {
        const response = await fetch(`/api/occupations/search?q=${encodeURIComponent(trimmed)}`, {
          signal: controller.signal,
          headers: { Accept: "application/json" },
        });
        if (!response.ok) throw new Error("Search unavailable");
        const results = await response.json() as Occupation[];
        setMatches(results);
        setSearchState(results.length ? "idle" : "not-found");
      } catch (error) {
        if ((error as Error).name !== "AbortError") setSearchState("error");
      }
    }, 250);
    return () => { controller.abort(); window.clearTimeout(timer); };
  }, [query, selected]);

  async function analyze(event: FormEvent) {
    event.preventDefault();
    const trimmed = query.trim();
    if (trimmed.length < 2) {
      setSearchState("not-found");
      return;
    }
    let job = selected ?? matches[0] ?? null;
    let resultCount = matches.length;
    if (!job) {
      setSearchState("searching");
      try {
        const response = await fetch(`/api/occupations/search?q=${encodeURIComponent(trimmed)}`);
        if (!response.ok) throw new Error("Search unavailable");
        const results = await response.json() as Occupation[];
        setMatches(results);
        resultCount = results.length;
        job = results[0] ?? null;
      } catch {
        setSearchState("error");
        return;
      }
    }

    trackEvent("occupation_search_used", {
      query_result_count: resultCount,
      selected_occupation_slug: job ? job.slug : undefined,
    });

    if (!job) {
      setSearchState("not-found");
      return;
    }
    setSelected(job);
    setPhase("loading");
    window.setTimeout(() => setPhase("result"), 700);
  }

  function choose(job: Occupation) {
    setQuery(job.title);
    setSelected(job);
    setMatches([]);
    setSearchState("idle");
  }

  function updateQuery(value: string) {
    setQuery(value);
    setSelected(null);
    if (value.trim().length < 2) {
      setMatches([]);
      setSearchState("idle");
    }
  }

  function reset() {
    setQuery("");
    setSelected(null);
    setMatches([]);
    setSearchState("idle");
    setPhase("search");
  }

  if (phase === "loading") return <div className="analysis-state" role="status"><span className="analysis-mark">vs</span><div><strong>Building your career risk picture…</strong><p>Checking tasks, AI capabilities, and market resilience.</p></div></div>;
  if (phase === "result" && selected) return (
    <article className="search-result-card">
      <div className="result-heading"><div><span className="chip">{selected.category}</span><h2>{selected.title}</h2></div><button className="text-button" onClick={reset}>Search again</button></div>
      <div className="result-score-grid"><MiniScore label="AI Exposure" value={selected.aiExposure} /><MiniScore label="Replacement Risk" value={selected.replacementRisk} /><div className="result-verdict"><span className="metric-label">What it means</span><strong>{selected.verdict}</strong><p>{selected.summary}</p></div></div>
      <Link
        className="button result-link"
        href={`/jobs/${selected.slug}`}
      >See the full analysis <span aria-hidden="true">→</span></Link>
    </article>
  );

  return (
    <div className="search-area">
      <form className="occupation-search" onSubmit={analyze}>
        <label className="sr-only" htmlFor="occupation">Search your occupation</label>
        <span className="search-icon" aria-hidden="true"></span>
        <input id="occupation" value={query} onChange={(event) => updateQuery(event.target.value)} placeholder="Search your job or profession…" autoComplete="off" aria-describedby="occupation-search-message" />
        <button type="submit" disabled={searchState === "searching"}>Check my job <span aria-hidden="true">→</span></button>
      </form>
      {matches.length > 0 && !selected && <ul className="autocomplete">{matches.map((job) => <li key={job.slug}><button type="button" onClick={() => choose(job)}><span>{job.title}</span><small>{job.category}</small></button></li>)}</ul>}
      <div id="occupation-search-message" className="search-message" aria-live="polite">
        {searchState === "searching" && "Searching occupations…"}
        {searchState === "not-found" && "No matching occupation found. Try another title or a broader term."}
        {searchState === "error" && "Occupation search is temporarily unavailable. Please try again."}
      </div>
      <div className="popular-searches"><span>Popular:</span>{popularOccupations.map((job) => <button type="button" key={job.slug} onClick={() => choose(job)}>{job.title}</button>)}</div>
    </div>
  );
}

function MiniScore({ label, value }: { label: string; value: number }) {
  return <div className="mini-score"><span className="metric-label">{label}</span><strong>{value}<small>/100</small></strong><span className="chip">{value >= 75 ? "Very high" : value >= 60 ? "High" : value >= 40 ? "Moderate" : "Low"}</span></div>;
}
