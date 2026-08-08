# Follow-up work

The foundation (plugin system, provider-agnostic AI layer with scheduled
prompts + tool-calling, theming, drill-down navigation, kiosk deployment,
CI, GHCR image publishing) is built, along with several dozen reference
plugins — see `backend/app/plugins/` for the current list, and
`CONTRIBUTING.md` for the step-by-step pattern for adding another one.

## Remaining, ordered by effort/dependency

(small and self-contained first, large or speculative last, rather than by
when each idea came up)

1. **Create a separate marketplace** for external plugins to be published,
    with a plugin store for users to dynamically add them — the largest and
    most speculative item; depends on the plugin ecosystem maturing first.
    Design proposal written, see [`docs/marketplace-design.md`](docs/marketplace-design.md)
    for the manifest format, sandboxing/permission model, dynamic-loading,
    and install lifecycle. Implementation intentionally not started.

## Next Up

1. On the flight widget add a map to the detail page.
