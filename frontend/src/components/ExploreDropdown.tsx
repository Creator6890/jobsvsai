"use client";

import { NavDropdown } from "./NavDropdown";

const EXPLORE_ITEMS = [
  {
    href: "/careers",
    title: "Career Fields",
    description: "Browse 19 canonical industry domains",
  },
  {
    href: "/compare",
    title: "Compare Careers",
    description: "Side-by-side risk comparison",
  },
];

export function ExploreDropdown() {
  return <NavDropdown label="Explore" items={EXPLORE_ITEMS} />;
}
