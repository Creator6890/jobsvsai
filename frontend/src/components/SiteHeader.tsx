import Link from "next/link";
import { Logo } from "./Logo";
import { CareerToolsDropdown } from "./CareerToolsDropdown";
import { ExploreDropdown } from "./ExploreDropdown";
import { ResearchDropdown } from "./ResearchDropdown";

export function SiteHeader() {
  return (
    <header className="site-header">
      <div className="container nav">
        <Logo />

        {/* Desktop Primary Navigation */}
        <nav className="nav-links" aria-label="Primary navigation">
          <Link href="/rankings">Rankings</Link>
          <ExploreDropdown />
          <CareerToolsDropdown />
          <ResearchDropdown />
          <Link href="/news">News</Link>
          <Link href="/about">About</Link>
        </nav>

        {/* Mobile Navigation */}
        <details className="mobile-menu">
          <summary aria-label="Open navigation">
            <span></span>
            <span></span>
            <span></span>
          </summary>
          <nav className="mobile-nav-inner" aria-label="Mobile navigation">
            <Link href="/rankings">Rankings</Link>
            <Link href="/careers">Career Fields</Link>
            <div className="mobile-nav-section">
              <span className="mobile-nav-section-title">Career Tools</span>
              <div className="mobile-nav-sublinks">
                <Link href="/career-fit" className="mobile-sublink">
                  <strong>Career Fit</strong>
                  <small>Find careers matching your strengths</small>
                </Link>
                <Link href="/compare" className="mobile-sublink">
                  <strong>Compare Careers</strong>
                  <small>Side-by-side AI risk comparison</small>
                </Link>
              </div>
            </div>
            <div className="mobile-nav-section">
              <span className="mobile-nav-section-title">Research & Methodology</span>
              <div className="mobile-nav-sublinks">
                <Link href="/research" className="mobile-sublink">
                  <strong>AI & Jobs Research</strong>
                  <small>Evidence-led analysis & findings</small>
                </Link>
                <Link href="/methodology" className="mobile-sublink">
                  <strong>Methodology</strong>
                  <small>How scores and risk are calculated</small>
                </Link>
              </div>
            </div>
            <Link href="/news">News</Link>
            <Link href="/about">About</Link>
          </nav>
        </details>
      </div>
    </header>
  );
}
