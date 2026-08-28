import type { MetadataRoute } from "next";
import { getNewsSitemapEntries, getOccupations } from "@/lib/api";
import { CANONICAL_CAREER_FIELDS } from "@/lib/careerFields";
import { getAllResearchArticles } from "@/lib/researchArticles";
import { getAllowlistedComparisons } from "@/lib/comparisonAllowlist";

export const dynamic = "force-dynamic";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const origin = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";

  const staticRoutes = [
    "",
    "/rankings",
    "/careers",
    "/career-fit",
    "/compare",
    "/methodology",
    "/methodology/technical",
    "/methodology/changelog",
    "/about",
    "/research",
  ];

  const fieldRoutes = Object.keys(CANONICAL_CAREER_FIELDS).map((slug) => `/careers/${slug}`);
  const researchArticles = getAllResearchArticles();
  const allowlistedComparisons = getAllowlistedComparisons();

  const jobs = await getOccupations();
  const news = await getNewsSitemapEntries();

  return [
    ...staticRoutes.map((path) => ({
      url: `${origin}${path}`,
      changeFrequency: path === "" ? ("weekly" as const) : ("monthly" as const),
      priority: path === "" ? 1 : 0.7,
    })),
    ...fieldRoutes.map((path) => ({
      url: `${origin}${path}`,
      changeFrequency: "weekly" as const,
      priority: 0.85,
    })),
    ...researchArticles.map((article) => ({
      url: `${origin}/research/${article.slug}`,
      lastModified: new Date(article.dateModified),
      changeFrequency: "monthly" as const,
      priority: 0.75,
    })),
    ...allowlistedComparisons.map((comp) => ({
      url: `${origin}/compare/${comp.slug}`,
      changeFrequency: "monthly" as const,
      priority: 0.7,
    })),
    ...jobs.map((job) => ({
      url: `${origin}/jobs/${job.slug}`,
      lastModified: new Date(job.updatedAt),
      changeFrequency: "monthly" as const,
      priority: 0.8,
    })),
    ...news.map((article) => ({
      url: `${origin}/news/${article.slug}`,
      lastModified: new Date(article.updatedAt),
      changeFrequency: "weekly" as const,
      priority: 0.6,
    })),
  ];
}
