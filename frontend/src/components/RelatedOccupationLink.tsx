"use client";

import Link from "next/link";
import { trackEvent } from "@/lib/analytics";

/** The related-occupation call to action on an occupation page.
 *
 * OccupationDetail is a server component, and it should stay one — it renders the whole
 * page. This is the smallest possible client boundary: one link that needs an onClick.
 * Navigation behaviour is unchanged; the event is fired alongside it, not instead of it.
 */
export function RelatedOccupationLink({
  sourceSlug,
  relatedSlug,
  relatedTitle,
  href,
  children,
}: {
  sourceSlug: string;
  relatedSlug: string;
  relatedTitle: string;
  href: string;
  children: React.ReactNode;
}) {
  return (
    <Link
      className="text-link"
      href={href}
      onClick={() => trackEvent("related_occupation_click", {
        source_occupation_slug: sourceSlug,
        related_occupation_slug: relatedSlug,
        related_occupation_title: relatedTitle,
        source: "related_occupations",
      })}
    >
      {children}
    </Link>
  );
}
