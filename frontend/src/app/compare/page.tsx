import type { Metadata } from "next";
import { CompareSelector } from "@/components/CompareSelector";
import { PageHero, PageShell } from "@/components/PageShell";
import { getOccupations } from "@/lib/api";

export const dynamic = "force-dynamic";

export const metadata: Metadata = { title: "Compare careers", description: "Compare two careers across AI exposure, replacement risk, human dependency, demand, and resilience." };
export default async function ComparePage() { const occupations = await getOccupations(); return <PageShell><PageHero dark eyebrow="Career comparison" title="Put two careers head to head." copy="Compare AI exposure, replacement risk, future demand, and the human advantage of different occupations." /><main className="page-main"><div className="container"><CompareSelector occupations={occupations} /><div className="compare-empty"><span className="vs-badge">VS</span><h2>Choose two careers to see the full comparison.</h2><p>We will keep technical exposure separate from real-world replacement risk.</p></div></div></main></PageShell>; }
