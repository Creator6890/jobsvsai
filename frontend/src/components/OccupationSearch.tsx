"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, KeyboardEvent, useEffect, useState } from "react";
import type { Occupation } from "@/types/occupation";
import type { EstimatedOccupation } from "@/lib/api";
import { trackEvent } from "@/lib/analytics";

type SearchState = "idle" | "searching" | "not-found" | "unavailable" | "ambiguous" | "error";

/** What `/occupations/search/resolve` returns. A staged occupation may be *named* here, but
 *  never carries a score or a slug: there is no page to link to and no approved number to
 *  show, which is the whole point of saying so plainly instead of substituting something. */
type SearchResolution = {
  queryStatus: "public_matches" | "ambiguous" | "occupation_not_available" | "no_reliable_match";
  results: Occupation[];
  matchedTitle?: string | null;
  canonicalTitle?: string | null;
  isDisambiguation?: boolean;
  relatedPublicResults?: { slug: string; title: string }[];
  /** For `ambiguous`. May include an interpretation we cannot analyse: it is listed as
   *  unavailable rather than dropped, because dropping it would silently resolve the
   *  ambiguity in favour of whatever happens to be published. */
  choices?: { title: string; available: boolean; slug?: string | null; scoreStatus?: string | null }[];
  /** Preliminary estimates matching the same query, in relevance order. Search ranks the two
   *  classes together on identity relevance — an estimate is never demoted for being an
   *  estimate — and they arrive split only so the UI must label them. */
  estimatedResults?: EstimatedOccupation[];
  /** Every matched slug in one relevance order across both score classes. */
  resultOrder?: string[];
};

/** One row of the suggestion list, from either score class. `estimated` decides the label
 *  and nothing else: position in the list comes from relevance alone. */
type Suggestion = {
  slug: string;
  title: string;
  category: string;
  estimated: boolean;
  occupation?: Occupation;
};

export function OccupationSearch({ popularOccupations }: { popularOccupations: Occupation[] }) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [phase, setPhase] = useState<"search" | "loading" | "result">("search");
  const [selected, setSelected] = useState<Occupation | null>(null);
  const [matches, setMatches] = useState<Occupation[]>([]);
  const [estimates, setEstimates] = useState<EstimatedOccupation[]>([]);
  const [resultOrder, setResultOrder] = useState<string[]>([]);
  const [searchState, setSearchState] = useState<SearchState>("idle");
  const [unavailable, setUnavailable] = useState<SearchResolution | null>(null);
  // Keyboard highlight inside the typeahead. -1 means "nothing highlighted", which is not the
  // same as "the first row is highlighted": Enter with no highlight must submit what the user
  // actually typed, never silently pick a suggestion they never looked at.
  const [activeIndex, setActiveIndex] = useState(-1);
  // Escape and Tab close the list without clearing the query, so a dismissal is separate state
  // from "there are no matches".
  const [listDismissed, setListDismissed] = useState(false);

  // One list, in the relevance order search computed. The API splits the two score classes
  // into separate fields so an estimate can never be rendered as a verified score, but
  // concatenating them here would silently re-sort the results by class: "soft eng" ranks
  // Software Developer above Etchers and Engravers, and verified-first would have shown the
  // engraver anyway. `resultOrder` carries the true order across both.
  const unordered: Suggestion[] = [
    ...matches.map((job) => ({
      slug: job.slug, title: job.title, category: job.category,
      estimated: false, occupation: job,
    })),
    ...estimates.map((est) => ({
      slug: est.slug, title: est.title, category: est.category, estimated: true,
    })),
  ];
  const suggestions: Suggestion[] = resultOrder.length
    ? resultOrder
        .map((slug) => unordered.find((item) => item.slug === slug))
        .filter((item): item is Suggestion => item !== undefined)
    : unordered;

  const showList = suggestions.length > 0 && !selected && !listDismissed;

  useEffect(() => {
    const trimmed = query.trim();
    if (trimmed.length < 2 || selected) {
      return;
    }
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setSearchState("searching");
      try {
        const response = await fetch(`/api/occupations/search/resolve?q=${encodeURIComponent(trimmed)}`, {
          signal: controller.signal,
          headers: { Accept: "application/json" },
        });
        if (!response.ok) throw new Error("Search unavailable");
        const resolution = await response.json() as SearchResolution;
        setMatches(resolution.results ?? []);
        setEstimates(resolution.estimatedResults ?? []);
        setResultOrder(resolution.resultOrder ?? []);
        setActiveIndex(-1);
        if (resolution.queryStatus === "occupation_not_available") {
          setUnavailable(resolution);
          setSearchState("unavailable");
        } else if (resolution.queryStatus === "ambiguous") {
          setUnavailable(resolution);
          setSearchState("ambiguous");
        } else {
          setUnavailable(null);
          setSearchState(resolution.results?.length ? "idle" : "not-found");
        }
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
        const response = await fetch(`/api/occupations/search/resolve?q=${encodeURIComponent(trimmed)}`);
        if (!response.ok) throw new Error("Search unavailable");
        const resolution = await response.json() as SearchResolution;
        setMatches(resolution.results ?? []);
        setEstimates(resolution.estimatedResults ?? []);
        setResultOrder(resolution.resultOrder ?? []);
        resultCount = (resolution.results?.length ?? 0) + (resolution.estimatedResults?.length ?? 0);
        job = resolution.results?.[0] ?? null;
        // An estimate has no verified result card to show, so submitting a query that only
        // matched estimates navigates to the occupation's own page, where the preliminary
        // status is rendered before any number.
        if (!job && resolution.estimatedResults?.length) {
          trackEvent("occupation_search_used", { query_result_count: resultCount });
          router.push(`/jobs/${resolution.estimatedResults[0].slug}`);
          return;
        }
        if (resolution.queryStatus === "occupation_not_available") {
          setUnavailable(resolution);
          setSearchState("unavailable");
          // Recorded as a zero-result search. The query text itself is never sent.
          trackEvent("occupation_search_used", { query_result_count: 0 });
          return;
        }
        setUnavailable(null);
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

  function pick(suggestion: Suggestion) {
    if (suggestion.occupation) {
      choose(suggestion.occupation);
      return;
    }
    // Estimated occupations have no verified result card; their page carries the status.
    router.push(`/jobs/${suggestion.slug}`);
  }

  function choose(job: Occupation) {
    setQuery(job.title);
    setSelected(job);
    setMatches([]);
    setEstimates([]);
    setResultOrder([]);
    setSearchState("idle");
    setActiveIndex(-1);
    setListDismissed(false);
  }

  function updateQuery(value: string) {
    setQuery(value);
    setSelected(null);
    setActiveIndex(-1);
    // Typing again after dismissing re-opens the list: continuing to type is a new intent.
    setListDismissed(false);
    if (value.trim().length < 2) {
      setMatches([]);
      setEstimates([]);
      setResultOrder([]);
      setSearchState("idle");
    }
  }

  function reset() {
    setQuery("");
    setSelected(null);
    setMatches([]);
    setSearchState("idle");
    setPhase("search");
    setActiveIndex(-1);
    setListDismissed(false);
  }

  function onSearchKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (!showList) {
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((index) => (index + 1) % suggestions.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((index) => (index <= 0 ? suggestions.length - 1 : index - 1));
    } else if (event.key === "Escape") {
      // Closes the list, keeps the query. Erasing what someone typed because they wanted the
      // overlay out of the way would be a hostile reading of Escape.
      event.preventDefault();
      setListDismissed(true);
      setActiveIndex(-1);
    } else if (event.key === "Tab") {
      // Focus is leaving the field; an open overlay would hang over whatever gains focus next.
      setListDismissed(true);
      setActiveIndex(-1);
    } else if (event.key === "Enter" && activeIndex >= 0) {
      // Intercepted only while a row is highlighted, so plain type-and-Enter still submits.
      event.preventDefault();
      pick(suggestions[activeIndex]);
    }
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
      <div className="search-career-fit-handoff">
        <div className="handoff-content">
          <strong>Thinking about other options?</strong>
          <p>Find careers that align with your strengths and work preferences.</p>
        </div>
        <div className="handoff-action">
          <Link
            className="button secondary compact"
            href="/career-fit?from=homepage_search"
          >
            Find My Career Fit <span aria-hidden="true">→</span>
          </Link>
          <span className="handoff-time">Takes about 3 minutes</span>
        </div>
      </div>
    </article>
  );

  return (
    <div className="search-area">
      <form className="occupation-search" onSubmit={analyze}>
        <label className="sr-only" htmlFor="occupation">Search your occupation</label>
        <span className="search-icon" aria-hidden="true"></span>
        <input
          id="occupation"
          value={query}
          onChange={(event) => updateQuery(event.target.value)}
          onKeyDown={onSearchKeyDown}
          placeholder="Search your job or profession…"
          autoComplete="off"
          role="combobox"
          aria-expanded={showList}
          aria-controls="occupation-suggestions"
          aria-autocomplete="list"
          aria-activedescendant={activeIndex >= 0 ? `occupation-option-${activeIndex}` : undefined}
          aria-describedby="occupation-search-message"
        />
        <button type="submit" disabled={searchState === "searching"}>Check my job <span aria-hidden="true">→</span></button>
      </form>
      {showList && (
        <ul className="autocomplete" id="occupation-suggestions" role="listbox" aria-label="Matching occupations">
          {suggestions.map((job, index) => (
            <li key={job.slug} role="presentation">
              <button
                type="button"
                role="option"
                id={`occupation-option-${index}`}
                aria-selected={index === activeIndex}
                className={index === activeIndex ? "is-active" : undefined}
                // Options are reached with the arrow keys, not Tab: the ARIA combobox pattern
                // keeps focus in the input and moves aria-activedescendant instead.
                tabIndex={-1}
                onMouseEnter={() => setActiveIndex(index)}
                onClick={() => pick(job)}
              >
                <span>{job.title}</span>
                <small className={job.estimated ? "suggestion-estimated" : "suggestion-verified"}>
                  {job.estimated ? "Preliminary estimate" : "Verified analysis"}
                </small>
              </button>
            </li>
          ))}
        </ul>
      )}
      <div id="occupation-search-message" className="search-message" aria-live="polite">
        {searchState === "searching" && "Searching occupations…"}
        {searchState === "not-found" && "No matching occupation found. Try another title or a broader term."}
        {searchState === "ambiguous" && unavailable && (
          <div className="search-unavailable">
            <strong>{unavailable.matchedTitle ?? query.trim()}</strong>
            <p>Which role best matches what you do?</p>
            <ul className="search-unavailable-related">
              {(unavailable.choices ?? []).map((choice) => (
                <li key={choice.title}>
                  {choice.available && choice.slug ? (
                    <Link href={`/jobs/${choice.slug}`}>{choice.title}</Link>
                  ) : (
                    <span>{choice.title} — analysis not available yet</span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
        {searchState === "unavailable" && unavailable && (
          <div className="search-unavailable">
            <strong>{unavailable.matchedTitle ?? query.trim()}</strong>
            <p>
              We don&rsquo;t have a JobsVsAI analysis for this occupation yet
              {unavailable.canonicalTitle && unavailable.canonicalTitle !== unavailable.matchedTitle
                ? ` (${unavailable.canonicalTitle})`
                : ""}.
            </p>
            {unavailable.relatedPublicResults && unavailable.relatedPublicResults.length > 0 && (
              <>
                <p className="search-unavailable-related-label">
                  Related careers we can analyse today:
                </p>
                <ul className="search-unavailable-related">
                  {unavailable.relatedPublicResults.map((related) => (
                    <li key={related.slug}>
                      <Link href={`/jobs/${related.slug}`}>{related.title}</Link>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </div>
        )}
        {searchState === "error" && "Occupation search is temporarily unavailable. Please try again."}
      </div>
      <div className="popular-searches"><span>Popular:</span>{popularOccupations.map((job) => <button type="button" key={job.slug} onClick={() => choose(job)}>{job.title}</button>)}</div>
    </div>
  );
}

function MiniScore({ label, value }: { label: string; value: number }) {
  return <div className="mini-score"><span className="metric-label">{label}</span><strong>{value}<small>/100</small></strong><span className="chip">{value >= 75 ? "Very high" : value >= 60 ? "High" : value >= 40 ? "Moderate" : "Low"}</span></div>;
}
