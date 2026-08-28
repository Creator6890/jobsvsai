"use client";

import { NavDropdown } from "./NavDropdown";

const RESEARCH_ITEMS = [
  {
    href: "/research",
    title: "AI & Jobs Research",
    description: "Evidence-led analysis & findings",
  },
  {
    href: "/methodology",
    title: "Methodology",
    description: "How we calculate AI exposure & replacement risk",
  },
];

export function ResearchDropdown() {
  return <NavDropdown label="Research" items={RESEARCH_ITEMS} />;
}
