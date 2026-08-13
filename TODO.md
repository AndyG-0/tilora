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
2. Fix issues with multiple devices. Different device widgets are ending up on the same device. When looking at the full user widget list it shows all widgets for all devices. This might be ok but there is no way to distinguish one from the other. Widgets from one device should not automatically be added to other devices. We need to make it so that this is a better user experience overall. There are too many options is probably one of the issues. There are admin settings, user settings, widget settings, device settings. We need a clean way to distinguish one from the other.
3. When the screensaver runs and the user either interupts it due to activity or if it is cycling through the various different screensavers, the scrensaver is not keeping track of what is was on when it stops. Then it starts over from the beginning again when it comes back on. We need some sort of cursor/tracking for the current item be it a photo or a message so it picks up where it left off.
4. Scheduled series recordings and maybe any scheduled recording are not actually recording on the recording server.

