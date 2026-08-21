import type { ReactNode } from "react";
import { SiteFooter } from "./SiteFooter";
import { SiteHeader } from "./SiteHeader";

export function PageShell({ children, admin = false }: { children: ReactNode; admin?: boolean }) {
  return <>{!admin && <SiteHeader />}{children}{!admin && <SiteFooter />}</>;
}

export function PageHero({ eyebrow, title, copy, dark = false, children }: { eyebrow: string; title: ReactNode; copy?: string; dark?: boolean; children?: ReactNode }) {
  return <section className={`page-hero ${dark ? "dark" : ""}`}><div className="container"><div className="eyebrow">{eyebrow}</div><div className="page-hero-row"><div><h1>{title}</h1>{copy && <p className="lead">{copy}</p>}</div>{children}</div></div></section>;
}
