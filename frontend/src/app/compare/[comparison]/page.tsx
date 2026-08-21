import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { CareerComparison } from "@/components/CareerComparison";
import { CompareSelector } from "@/components/CompareSelector";
import { PageHero, PageShell } from "@/components/PageShell";
import { getOccupation, getOccupations } from "@/lib/api";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: PageProps<"/compare/[comparison]">): Promise<Metadata> { const { comparison } = await params; const [aSlug, bSlug] = splitComparison(comparison); const [a, b] = await Promise.all([getOccupation(aSlug), getOccupation(bSlug)]); return { title: a && b ? `${a.title} vs ${b.title}` : "Career comparison", description: a && b ? `Compare ${a.title} and ${b.title} across AI exposure, replacement risk, resilience, salary, and demand.` : undefined }; }
export default async function DynamicComparePage({ params }: PageProps<"/compare/[comparison]">) { const { comparison } = await params; const [aSlug, bSlug] = splitComparison(comparison); const [a, b, occupations] = await Promise.all([getOccupation(aSlug), getOccupation(bSlug), getOccupations()]); if (!a || !b) notFound(); return <PageShell><PageHero dark eyebrow="Career battle" title={`${a.title} vs ${b.title}`} copy="A transparent, side-by-side view of AI impact and career resilience." /><main className="page-main"><div className="container"><CompareSelector occupations={occupations} initialA={a.slug} initialB={b.slug} /><CareerComparison a={a} b={b} /></div></main></PageShell>; }
function splitComparison(value: string) { const marker = "-vs-"; const at = value.indexOf(marker); return at < 0 ? ["", ""] : [value.slice(0, at), value.slice(at + marker.length)]; }
