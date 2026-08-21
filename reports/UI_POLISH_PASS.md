# UI polish pass

Date: 2026-08-21
Scope: **one file — `frontend/src/app/globals.css`** (444 → 468 lines). No component, route,
copy, API, data or product change. No colours, gradients, shadows or grid structures altered.

## Why the pass was needed

The stylesheet had accumulated ad-hoc values rather than a scale:

- **11 distinct literal border-radii** between 8px and 28px (8, 9, 10, 11, 12, 13, 14, 15,
  16, 18, 28), while the `--radius` token was used only 5 times and `--radius-sm` was
  declared but never used at all.
- **Control heights spread across 42, 44, 45, 48, 52, 53, 54, 56, 57, 58, 61px** with no
  discernible rule — buttons at 48, form inputs at 52, filter inputs at 58, search at 54.
- **Four different section rhythms** (96/86/76/50px) plus a second set of fixed mobile
  overrides that duplicated the same intent at different numbers.
- Card padding at 22, 26, 28, 34, 35, 62px; grid gaps at 12, 18, 20, 22, 24, 32, 50, 70px.

## What changed

### Tokens introduced

```css
--radius-xs: 10px; --radius-sm: 12px; --radius-md: 16px; --radius: 22px; --radius-lg: 26px;
--control-sm: 44px; --control: 48px; --control-lg: 54px;
--section-y: clamp(60px, 7vw, 92px);
--pad-card: 26px; --pad-card-lg: 32px; --pad-card-sm: 18px;
--gap-sm: 12px; --gap: 20px; --gap-lg: 28px;
--measure: 68ch;
```

### Radius

Every literal radius now maps onto the five-step scale. The only literals remaining are the
six `999px` pills, which are correct as literals. `--radius: 22px` was kept unchanged so
cards keep their existing identity; the outliers moved to it (28 → 26 for the two feature
cards, 18/15/14 → 16, 13/11 → 12, 9/8 → 10).

### Control heights

Buttons, inputs, menu items and tap targets now resolve to 44 / 48 / 54. Notably the filter
input dropped 58 → 54 to match the hero search, and form fields 52 → 48 to match buttons.

### Vertical rhythm

`.section`, `.content-section`, `.page-main` and `.score-section` all draw from one clamped
`--section-y`. Four fixed mobile overrides (`68px`, `62px`, `52px 0 48px`, `28px 0 60px`)
were deleted because the clamp already resolves to its small-screen value below ~860px —
they were a second source of truth saying almost the same thing.

### Typography

- `h3` was inheriting the display `line-height: 1.08` intended for `h1`/`h2`. At 1.22rem
  that left two-line occupation titles nearly touching. Now `1.3` with a softer
  `-.02em` tracking and `text-wrap: balance`.
- **Product hero scale reduced**: `clamp(3.1rem, 6.5vw, 5.4rem)` → `clamp(2.5rem, 5.2vw,
  4.4rem)`, mobile `clamp(2.75rem, 13vw, 4rem)` → `clamp(2.25rem, 10vw, 3.25rem)`. This is
  the one change with a visible effect on short headlines, and it was made for a real
  reason — see below.
- Card body copy settled on `.9rem` (was a mix of .85/.86/.88).
- `.career-card h3` 1.45rem → 1.3rem, bringing it back onto the heading scale.
- Long-form copy (`.editorial`, `.definition-card`, `.section-head p`) now uses a `68ch`
  measure and 1.6–1.65 line-height instead of pixel max-widths of 540px/720px.

### Density

Table and list rows normalised: task and ranking rows 72 → 68, ranking list 57 → 56,
comparison rows 61 → 56, data list 58 → 56, method steps 100 → 88, insight list 52 → 56,
compact list 42 → 44. Header rows 53 → 48 and 48 → 44.

### Mobile

Added one deliberate narrow-screen block: cards drop to `--pad-card-sm` (18px) below 680px
and 16px below 400px, with the container gutter tightening to 20px at 400px. Previously a
26px card padding on a 360px viewport consumed 29% of the width.

## The long-title problem this surfaced

The longest published title is 105 characters — *"Grinding, Lapping, Polishing, and Buffing
Machine Tool Setters, Operators, and Tenders, Metal and Plastic"*. The hero scale had been
tuned for short marketing headlines like "How jobs rank against AI", so on a 360px screen
that title rendered as a **nine-line headline at 47px**, filling the viewport before any
content appeared.

After the scale change, measured on the live page:

| Width | Before | After |
|---|---|---|
| 360 | 47px / 9 lines | **36px / 7 lines** |
| 390 | 51px / 9 lines | 39px / 7 lines |
| 430 | 56px / 9 lines | 43px / 7 lines |
| 768 | 50px / 5 lines | 40px / 4 lines |
| 1024 | 67px / 5 lines | 53px / 4 lines |
| 1440 | 86px / 5 lines | **70px / 4 lines** |

Short headlines remain large and confident (70px at 1440). `text-wrap: balance` distributes
the remaining lines evenly rather than leaving a one-word last line.

## Validation

Built and deployed to the running container, then measured in-browser.

- **42 combinations** (7 routes × 6 widths: 360, 390, 430, 768, 1024, 1440) —
  **zero horizontal overflow, zero clipped headings.**
- Routes checked: `/`, `/jobs/accountant`, the 105-character occupation page, `/rankings`,
  `/compare`, `/methodology`, `/about`.
- Consistency spot-check across pages at 390 and 1440: section padding 60/92 everywhere,
  card radius 22 everywhere, buttons 44px with 12px radius everywhere, nav 67/72.
- `npm run build` ✓ · `tsc --noEmit` ✓ (0 errors) · `eslint --max-warnings=0` ✓ (0 warnings).

## Intentionally left unchanged

- **Homepage hero** (`.home-hero h1`, `clamp(3.3rem, 8vw, 7rem)`). It is display copy on a
  page with no long content titles, and shrinking it would change the site's front door for
  no functional gain.
- **`--radius: 22px`** itself. Normalising the outliers onto it was the point; moving it
  would have restyled every card for no reason.
- **Colours, gradients, shadows, the violet scale, and all grid column definitions.**
- **`999px` pills** left as literals — a pill is not a step on a radius scale.
- **`.option-grid button` (94px) and `.match-metrics > div` (105px)** min-heights. They are
  career-finder only, a surface excluded from launch, and sizing them properly needs a look
  at that page's design rather than a token sweep.
- **Admin console** received only the shared token substitutions (radius, control heights).
  Its layout and density were not audited — it is an internal surface and out of scope here.
- **`.score-card` 286px min-height.** It keeps the three score columns aligned on desktop;
  it already collapses to `auto` on mobile.
- **The `.tab-list` two-column mobile grid override.** It looks unusual next to the desktop
  flex row, but it is a deliberate fix for tab overflow on narrow screens.
- **Publication `seo_slug` vs page `slug` divergence** — noted during the activation audit,
  not a UI concern and not touched here.
