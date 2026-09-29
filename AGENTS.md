
## COMEDK Compass architecture
- Keep domain data in `src/lib/mock-data` and render it through reusable product components so the frontend can later swap to API-backed repositories without redesigning pages.
- Keep shared site chrome in the TanStack root route and each major product area in its own typed file route for direct navigation and route-specific metadata.
