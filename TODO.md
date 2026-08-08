# Follow-up work

The foundation (plugin system, provider-agnostic AI layer with scheduled
prompts + tool-calling, theming, drill-down navigation, kiosk deployment,
CI, GHCR image publishing) is built, along with several dozen reference
plugins — see `backend/app/plugins/` for the current list, and
`CONTRIBUTING.md` for the step-by-step pattern for adding another one.

## Remaining, ordered by effort/dependency

(small and self-contained first, large or speculative last, rather than by
when each idea came up)

1. ~~i18n / multi-language support~~ — infrastructure is done: svelte-i18n
   on the frontend, a backend `app/i18n.py` catalog + locale-aware plugin
   threading (`Plugin.locale`, locale-aware widget cache keys), and a
   Settings → Language picker (en/es/fr/de). Fully wired end-to-end across
   every plugin, shared frontend chrome, settings sections, and routes. See
   `CONTRIBUTING.md`'s Internationalization section for the pattern used
   throughout.
   - [x] Remaining plugins (backend + matching frontend tile/detail pair):
     ai_insights, alert, asus_router, bf6, bookmarks, calendar, clock,
     container, date, discord, game2048, goodreads, hdhomerun, jellyfin,
     message, movies, photos, pihole, rss, steam, synology,
     system_monitor, wordle
   - [x] Frontend shared chrome: TileCard, Screensaver + screensaver
     variants (Calendar/Clock/Date/Photo/Weather/Wordy), clock faces
     (Analog/Binary/Clock/Digital/Matrix/Word), HDHomeRunPlayer,
     JellyfinPlayer
   - [x] Remaining settings/+page.svelte sections: Profile, Devices,
     Screensaver, Voice, Microphone access, Software update
   - [x] login/, setup/, widget/[id]/ routes, and root +page.svelte chrome
     (e.g. theme-cycle button aria-label)
   - [x] AI-generated free text (AIDetail.svelte / ai_insights plugin) —
     the ai_insights widget now has a `language` setting (editable from its
     detail view) that becomes a `system_prompt` instruction passed into
     `assistant.ask()` on each scheduled run
2. **Create a separate marketplace** for external plugins to be published,
    with a plugin store for users to dynamically add them — the largest and
    most speculative item; depends on the plugin ecosystem maturing first.
    Design proposal written, see [`docs/marketplace-design.md`](docs/marketplace-design.md)
    for the manifest format, sandboxing/permission model, dynamic-loading,
    and install lifecycle. Implementation intentionally not started.

