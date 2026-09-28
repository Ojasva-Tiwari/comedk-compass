# COMEDK Compass implementation plan

## Product direction
- Build a complete frontend-only counselling product with a restrained academic/technical visual system, dense but readable analytics, semantic probability colors, and equally intentional light and dark themes.
- Keep every figure clearly labeled as demo, estimated, historical, sourced, year-specific, and confidence-qualified where applicable.

## Shared foundation
- Replace the placeholder with the COMEDK Compass application shell: sticky desktop navigation, mobile menu and bottom navigation, global search command palette, theme control, responsive content frame, page transitions, focus states, and reduced-motion support.
- Define the brand system in shared tokens: neutral surfaces, one strong blue accent, semantic green/amber/red/purple states, compact radii, typography, shadows, chart colors, and the compass mark.
- Create typed mock-data modules and domain interfaces for colleges, branches, cutoffs, fees, placements, counselling rounds, probabilities, preference entries, and student submissions. Components will consume selectors/adapters rather than inline data.
- Add reusable product components for sourced metrics, badges, college cards/logos, charts, probability timelines, cutoff tables, filters, rank inputs, predictor results, comparison views, counselling timelines, preference rows, feedback states, skeletons, and toasts.

## Pages and flows
1. **Home (`/`)** — Interactive rank predictor and animated rank-to-college-to-round visualization, feature visualizations, live counselling snapshot, switchable cutoff chart, round-wise probability story, college discovery cards, comparison preview, data-source trust section, student contribution prompt, and closing actions.
2. **Dashboard (`/dashboard`)** — Student counselling profile, admission overview, shortlist probabilities, current-round timeline, and data-backed recommended actions.
3. **Predictor (`/predictor`)** — Two-step marks-or-rank flow, validation, range-based estimate with confidence, and navigation into ranked college results.
4. **Colleges (`/colleges`)** — Responsive discovery layout with collapsible mobile filters, sorting, animated result updates, realistic metrics, and a no-results state.
5. **College detail (`/colleges/$slug`)** — Polished overview, branch cutoff table, opening/closing trend controls, rank-driven round probabilities, fee and placement breakdowns, source/year labels, verified submissions, and discrepancy treatment.
6. **Cutoffs (`/cutoffs`)** — Filterable data-exploration table with round columns, trends, and expandable historical row detail.
7. **Compare (`/compare`)** — Two-to-three college comparison with sticky headers, metric bars, compact visualization, and mobile horizontal scrolling.
8. **Counselling (`/counselling`)** — Current 2026 phase, next-event countdown, and personalized safe/target/reach strategy with movement and round probability.
9. **Preference list (`/preference-list`)** — Reorderable list with add/remove controls, coverage summary, admission-category balance, and a clear no-guarantee disclaimer.

## Interaction and navigation
- Connect every navigation item, CTA, college card, search result, and detail action to a real route.
- Implement command search for colleges, branches, cutoffs, and pages with keyboard navigation and Cmd/Ctrl+K.
- Persist only presentation preferences needed for the demo, such as theme and locally edited preference order; no backend or authentication will be added.
- Use Recharts for data graphics and lightweight CSS/React animation for entrances, counters, timelines, filter transitions, and tactile controls; avoid decorative motion.

## Verification
- Give every content route unique title, description, Open Graph, and Twitter metadata.
- Verify compilation, route navigation, command search, predictor transitions, filters, comparison controls, preference reordering, theme switching, empty/loading/error states, and desktop/mobile layouts in the running preview.
- Keep the implementation on the project’s existing TanStack Start stack; this provides the requested React/TypeScript/Tailwind experience without replacing the workspace framework.
