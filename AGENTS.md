<!-- LOVABLE:BEGIN -->
> [!IMPORTANT]
> This project is connected to [Lovable](https://lovable.dev). Avoid rewriting
> published git history — force pushing, or rebasing/amending/squashing commits
> that are already pushed — as it rewrites history on Lovable's side and the
> user will likely lose their project history.
>
> Commits you push to the connected branch sync back to Lovable and show up in
> the editor, so keep the branch in a working state.
<!-- LOVABLE:END -->

## COMEDK Compass architecture
- Keep domain data in `src/lib/mock-data` and render it through reusable product components so the frontend can later swap to API-backed repositories without redesigning pages.
- Keep shared site chrome in the TanStack root route and each major product area in its own typed file route for direct navigation and route-specific metadata.
