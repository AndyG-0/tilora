# Admin Guide Overview

Tilora includes a dedicated administrative tier for managing household accounts, third-party service credentials, AI models, hardware acceleration, and system updates.

---

## The Admin Role

The user profile created during initial onboarding automatically receives the **`admin`** role. Admins have access to:

- **Household User Management**: Create, promote, demote, or delete household member profiles.
- **AI Provider Configuration**: Manage API keys, select LLM model strings, and set reasoning effort parameters.
- **Voice System Infrastructure**: Configure cloud Whisper speech-to-text, Piper neural TTS servers, and browser autoplay policies.
- **Network Integrations**: Centrally store credentials for Pi-hole, Jellyfin, Synology, Asus Router SSH, HDHomeRun, and Docker hosts.
- **Hardware Acceleration Tuning**: Configure GPU DRM render nodes, VA-API drivers, and test transcoding pipelines.
- **Software Updates**: Trigger live fast-forward software updates directly from the user interface.

Non-admin household members only see personal settings (Profile, Appearance, Personal RSS, To-Do lists, Personal Voice selection, Location override).

---

## Admin Section Index

<div class="grid cards" markdown>

-   :material-account-group:{ .lg .middle } __[Household Management](household.md)__
    Manage profiles, roles, and PIN codes.

-   :material-robot:{ .lg .middle } __[AI Providers & Models](ai-providers.md)__
    Connect Claude, GPT-4o, Gemini, SearXNG, and MCP servers.

-   :material-microphone:{ .lg .middle } __[Voice Setup & Audio](voice-setup.md)__
    STT (Whisper), TTS (Piper/OpenAI), and browser autoplay policies.

-   :material-calendar-lock:{ .lg .middle } __[Calendar & OAuth Setup](calendar-oauth.md)__
    Google Cloud Console and Microsoft Entra ID step-by-step guides.

-   :material-lan:{ .lg .middle } __[Network Integrations](network-integrations.md)__
    Pi-hole, Jellyfin, Synology, Asus router, and HDHomeRun setup.

-   :material-docker:{ .lg .middle } __[Container Host Management](container-hosts.md)__
    Docker, Podman, and socket-proxy sidecar security.

-   :material-gpu:{ .lg .middle } __[Hardware Acceleration](hardware-acceleration.md)__
    GPU render nodes, VA-API, Quick Sync, NVENC, and diagnostics.

-   :material-update:{ .lg .middle } __[Updates & Maintenance](backup-update.md)__
    In-app updates, service restarts, and database snapshots.

-   :material-shield-lock:{ .lg .middle } __[Security & LAN Exposure](security.md)__
    Authentication tiers, network exposure, and VPN best practices.

</div>
