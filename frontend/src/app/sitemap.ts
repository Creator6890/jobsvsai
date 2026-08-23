import type { MetadataRoute } from "next";
import { getNewsSitemapEntries, getOccupations } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const origin = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";
  // /career-finder is excluded from launch: it still depends on legacy demo score columns.
  const staticRoutes = ["", "/rankings", "/news", "/compare", "/methodology", "/about"];
  const jobs = await getOccupations();
  // Published articles only: the API's own predicate decides, so draft, review_required
  // and rejected articles cannot reach the sitemap even by mistake.
  const news = await getNewsSitemapEntries();
  return [
    ...staticRoutes.map((path) => ({ url: `${origin}${path}`, changeFrequency: path === "" ? "weekly" as const : "monthly" as const, priority: path === "" ? 1 : .7 })),
    ...jobs.map((job) => ({ url: `${origin}/jobs/${job.slug}`, lastModified: new Date(job.updatedAt), changeFrequency: "monthly" as const, priority: .8 })),
    ...news.map((article) => ({ url: `${origin}/news/${article.slug}`, lastModified: new Date(article.updatedAt), changeFrequency: "weekly" as const, priority: .6 })),
  ];
}
