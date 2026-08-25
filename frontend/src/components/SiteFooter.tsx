import Link from "next/link";
import { Logo } from "./Logo";

export function SiteFooter() {
  return (
    <footer className="site-footer"><div className="container footer-inner"><div><Logo /><p>Clear career intelligence for the AI era.</p></div><nav aria-label="Footer navigation"><Link href="/rankings">Rankings</Link><Link href="/career-fit">Career Fit</Link><Link href="/methodology">Methodology</Link><Link href="/about">About</Link></nav><p className="small">Scores are decision-support indicators, not predictions of individual job loss.</p></div></footer>
  );
}
