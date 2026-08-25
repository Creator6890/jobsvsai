import Link from "next/link";
import { Logo } from "./Logo";
import { NavLinks, type NavLink } from "./NavLinks";

// /career-finder is intentionally absent: it still runs on legacy demo score columns
// (salary_potential, future_demand, location_demand) and is excluded from launch.

const links: readonly NavLink[] = [
  ["Home", "/"],
  ["Rankings", "/rankings"],
  ["Career Fit", "/career-fit"],
  ["News", "/news"],
  ["Compare", "/compare"],
  ["Methodology", "/methodology"],
  ["About", "/about"],
];

export function SiteHeader() {
  return (
    <header className="site-header">
      <div className="container nav">
        <Logo />
        <NavLinks links={links} className="nav-links" ariaLabel="Primary navigation" />
        <Link className="button nav-cta" href="/rankings">Explore the rankings <span aria-hidden="true">→</span></Link>
        <details className="mobile-menu">
          <summary aria-label="Open navigation"><span></span><span></span><span></span></summary>
          <NavLinks links={links} ariaLabel="Mobile navigation" />
        </details>
      </div>
    </header>
  );
}
