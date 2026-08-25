"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import type { Occupation } from "@/types/occupation";

export function CompareSelector({ occupations, initialA, initialB }: { occupations: Occupation[]; initialA?: string; initialB?: string }) {
  // Hooks stay unconditional: with fewer than two published occupations there is
  // nothing to compare, so the selector renders a notice instead of a form.
  const router = useRouter(); const [a, setA] = useState(initialA ?? occupations[0]?.slug ?? ""); const [b, setB] = useState(initialB ?? occupations[1]?.slug ?? occupations[0]?.slug ?? "");
  function submit(e: FormEvent) {
    e.preventDefault();
    if (a === b) return;
    router.push(`/compare/${a}-vs-${b}`);
  }
  if (occupations.length < 2) return <p className="empty-state">Career comparisons open up once at least two occupations are published.</p>;
  return <form className="compare-selector" onSubmit={submit}><label>First career<select value={a} onChange={(e) => setA(e.target.value)}>{occupations.map((job) => <option value={job.slug} key={job.slug}>{job.title}</option>)}</select></label><span className="vs-badge">VS</span><label>Second career<select value={b} onChange={(e) => setB(e.target.value)}>{occupations.map((job) => <option value={job.slug} key={job.slug}>{job.title}</option>)}</select></label><button className="button" disabled={a === b}>Compare careers →</button></form>;
}
