import Image from "next/image";
import Link from "next/link";

// The wordmark is a single asset used by both the header and the footer. Intrinsic size is
// the trimmed artwork (1674x297); the rendered height comes from `.logo img` in CSS so the
// header and footer stay in step with the rest of the spacing scale.
//
// `alt` is deliberately empty: the link already carries an aria-label, and labelling both
// would make a screen reader announce the brand twice for one control.
//
// `loading="eager"` rather than `preload`: the mark sits above the fold on every page, but
// the page heading is the likely LCP element, and Next 16's docs steer away from `preload`
// when something else is competing for it. (`priority` is deprecated as of Next 16.)
export function Logo() {
  return (
    <Link className="logo" href="/" aria-label="JobsVsAI home">
      <Image src="/logo.png" alt="" width={1674} height={297} loading="eager" />
    </Link>
  );
}
