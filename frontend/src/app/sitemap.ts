import type { MetadataRoute } from "next";
import { getOccupations } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const origin = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";
  // /career-finder is excluded from launch: it still depends on legacy demo score columns.
  const staticRoutes = ["", "/rankings", "/compare", "/methodology", "/about"];
  const jobs = await getOccupations();
  return [
    ...staticRoutes.map((path) => ({ url: `${origin}${path}`, changeFrequency: path === "" ? "weekly" as const : "monthly" as const, priority: path === "" ? 1 : .7 })),
    ...jobs.map((job) => ({ url: `${origin}/jobs/${job.slug}`, lastModified: new Date(job.updatedAt), changeFrequency: "monthly" as const, priority: .8 })),
  ];
}
