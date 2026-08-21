import type { Metadata } from "next";
import { Suspense } from "react";
import { CareerFinderForm } from "@/components/CareerFinderForm";
import { PageHero, PageShell } from "@/components/PageShell";
import { getOccupations } from "@/lib/api";

export const dynamic = "force-dynamic";

export const metadata: Metadata = { title: "Career Finder", description: "Find resilient career moves based on your experience, skills, and retraining appetite." };

export default async function CareerFinderPage() { const occupations = await getOccupations(); return <PageShell><PageHero dark eyebrow="Career Finder" title="Find your smartest next move." copy="We rank realistic transitions by AI resilience, skill overlap, future demand, and retraining effort." /><main className="page-main"><div className="container narrow"><Suspense><CareerFinderForm occupations={occupations} /></Suspense></div></main></PageShell>; }
