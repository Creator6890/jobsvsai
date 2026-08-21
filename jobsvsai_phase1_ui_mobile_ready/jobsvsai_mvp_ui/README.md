# JobsVsAI Phase 1 UI Prototype

Static HTML handoff for Codex. This is a UX/reference prototype, not production code.

## Pages
- `index.html` — current homepage prototype
- `job-detail.html` — occupation detail / SEO template
- `rankings.html` — rankings index/template
- `career-finder.html` — multi-step career finder input state
- `career-results.html` — personalized career recommendations
- `compare.html` — two-career comparison
- `methodology.html` — scoring explanation
- `about.html` — brand/about page
- `admin.html` — internal data/scoring console

## Shared prototype assets
- `styles.css` — shared visual language for all new pages
- `app.js` — minimal interaction used by the form prototype

## Production implementation notes for Codex
1. Rebuild as Next.js App Router components rather than copying pages literally.
2. Use a shared `SiteHeader`, `SiteFooter`, buttons, chips, cards, score components and occupation search component.
3. `jobs/[slug]` must be one dynamic template driven by API/database data; do not hardcode occupations into pages.
4. Use server-rendered/cacheable public job and ranking pages for SEO.
5. Career Finder should become a real multi-step form with state and API submission.
6. Comparison pages should be generated only for meaningful related occupations.
7. Keep admin routes protected and separate from public SEO pages.
8. Preserve the visual system: white navigation, black type, logo-purple gradient, spacious layout, violet used as the primary interaction/accent color.
9. Scores are data outputs. UI must always distinguish AI Exposure from Replacement Risk.
10. Do not treat score values in these HTML prototypes as production data.


## Important
All HTML pages are self-contained. CSS and JavaScript are embedded in each file so the visual theme works when any page is opened independently or supplied to Codex.
