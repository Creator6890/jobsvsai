"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export type NavLink = readonly [label: string, href: string];

/** True for the section's own page and anything nested under it, e.g. /compare/a-vs-b. */
function isActive(pathname: string, href: string): boolean {
  // "/" is every path's prefix, so the root link matches only itself — otherwise Home
  // would read as active on every page in the site.
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

// Shared by the desktop nav and the mobile menu so both indicate the same section. The
// active link is marked with aria-current; the colour comes from CSS keyed on that
// attribute, which keeps the styling declarative and the markup meaningful.
export function NavLinks({ links, className, ariaLabel }: {
  links: readonly NavLink[];
  className?: string;
  ariaLabel: string;
}) {
  const pathname = usePathname() ?? "";
  return (
    <nav className={className} aria-label={ariaLabel}>
      {links.map(([label, href]) => (
        <Link key={href} href={href} aria-current={isActive(pathname, href) ? "page" : undefined}>
          {label}
        </Link>
      ))}
    </nav>
  );
}
