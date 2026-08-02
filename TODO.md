# Follow-up work

The foundation (plugin system, provider-agnostic AI layer with scheduled
prompts + tool-calling, theming, drill-down navigation, kiosk deployment,
CI, GHCR image publishing) is built, along with several dozen reference
plugins — see `backend/app/plugins/` for the current list, and
`CONTRIBUTING.md` for the step-by-step pattern for adding another one.

## Remaining, ordered by effort/dependency

(small and self-contained first, large or speculative last, rather than by
when each idea came up)

1. **i18n / multi-language support** — likely `svelte-i18n` or the
   SvelteKit paraglide integration on the frontend; plugin summary/detail
   text would need a locale-aware path too. Cross-cutting across every
   plugin, so left for after the plugin set stabilizes.
2. **Auth / multi-user support**, if ever needed for a shared/public
   deployment — security-sensitive and touches every API route.
3. **Create a separate marketplace** for external plugins to be published,
    with a plugin store for users to dynamically add them — the largest and
    most speculative item; depends on the plugin ecosystem maturing first.