/**
 * Curated Comparison SEO Allowlist Infrastructure
 *
 * Up to 10 high-value, authoritative career comparisons permitted for search indexing.
 * All other dynamic comparison permutations are enforced as `noindex, follow` to prevent
 * combinatorial crawler traps and low-value duplicate search surfaces.
 */

export interface AllowlistedComparison {
  slug: string;
  aSlug: string;
  bSlug: string;
}

export const ALLOWLISTED_COMPARISONS: AllowlistedComparison[] = [
  {
    slug: "accountant-vs-budget-analysts",
    aSlug: "accountant",
    bSlug: "budget-analysts",
  },
  {
    slug: "mechanical-engineers-vs-electrical-engineers",
    aSlug: "mechanical-engineers",
    bSlug: "electrical-engineers",
  },
  {
    slug: "civil-engineers-vs-construction-managers",
    aSlug: "civil-engineers",
    bSlug: "construction-managers",
  },
  {
    slug: "acute-care-nurses-vs-home-health-aides",
    aSlug: "acute-care-nurses",
    bSlug: "home-health-aides",
  },
  {
    slug: "advertising-sales-agents-vs-insurance-sales-agents",
    aSlug: "advertising-sales-agents",
    bSlug: "insurance-sales-agents",
  },
  {
    slug: "paralegals-and-legal-assistants-vs-judicial-law-clerks",
    aSlug: "paralegals-and-legal-assistants",
    bSlug: "judicial-law-clerks",
  },
  {
    slug: "architectural-and-engineering-managers-vs-industrial-production-managers",
    aSlug: "architectural-and-engineering-managers",
    bSlug: "industrial-production-managers",
  },
  {
    slug: "computer-programmers-vs-business-intelligence-analysts",
    aSlug: "computer-programmers",
    bSlug: "business-intelligence-analysts",
  },
  {
    slug: "financial-examiners-vs-financial-quantitative-analysts",
    aSlug: "financial-examiners",
    bSlug: "financial-quantitative-analysts",
  },
  {
    slug: "commercial-and-industrial-designers-vs-fashion-designers",
    aSlug: "commercial-and-industrial-designers",
    bSlug: "fashion-designers",
  },
];

const ALLOWLIST_SET = new Set(ALLOWLISTED_COMPARISONS.map((c) => c.slug));

export function isComparisonAllowlisted(comparisonSlug: string): boolean {
  return ALLOWLIST_SET.has(comparisonSlug);
}

export function getAllowlistedComparisons(): AllowlistedComparison[] {
  return [...ALLOWLISTED_COMPARISONS];
}
