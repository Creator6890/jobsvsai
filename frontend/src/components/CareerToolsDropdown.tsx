"use client";

import { NavDropdown } from "./NavDropdown";

const CAREER_TOOLS_ITEMS = [
  {
    href: "/career-fit",
    title: "Career Fit",
    description: "Find careers matching your strengths",
  },
  {
    href: "/compare",
    title: "Compare Careers",
    description: "Side-by-side AI risk comparison",
  },
];

export function CareerToolsDropdown() {
  return <NavDropdown label="Career Tools" items={CAREER_TOOLS_ITEMS} />;
}
