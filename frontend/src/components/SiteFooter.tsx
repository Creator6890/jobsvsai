import Link from "next/link";
import { Logo } from "./Logo";

export function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="container footer-content">
        <div className="footer-brand-col">
          <Logo />
          <p className="footer-authority-line">
            Evidence-based AI career analysis built from occupational tasks, current AI capability and structural replacement constraints.
          </p>
        </div>

        <div className="footer-nav-groups">
          <div className="footer-group">
            <span className="footer-group-title">Explore</span>
            <nav aria-label="Explore navigation">
              <Link href="/careers">Career Fields</Link>
              <Link href="/rankings">Rankings</Link>
              <Link href="/compare">Compare Careers</Link>
              <Link href="/career-fit">Career Fit</Link>
            </nav>
          </div>

          <div className="footer-group">
            <span className="footer-group-title">Research</span>
            <nav aria-label="Research navigation">
              <Link href="/research">AI &amp; Jobs Research</Link>
              <Link href="/methodology">Methodology</Link>
              <Link href="/methodology/technical">Technical Methodology</Link>
              <Link href="/methodology/changelog">Methodology Changelog</Link>
              <Link href="/news">AI News</Link>
            </nav>
          </div>

          <div className="footer-group">
            <span className="footer-group-title">JobsVsAI</span>
            <nav aria-label="JobsVsAI navigation">
              <Link href="/about">About</Link>
            </nav>
          </div>
        </div>
      </div>

      <div className="container footer-bottom">
        <p className="small">Scores are decision-support indicators, not predictions of individual job loss.</p>
        <p className="small">© 2026 JobsVsAI. All rights reserved.</p>
      </div>
    </footer>
  );
}
