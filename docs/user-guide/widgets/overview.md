# Widget Catalog

Tilora ships with over 30 built-in plugins spanning weather, media, network management, personal productivity, gaming, and ambient display.

Every widget operates as a modular plugin (`backend/app/plugins/`):
- **Dashboard Tile**: A concise summary card rendered on the main grid that auto-refreshes via REST polling.
- **Detail View**: A full-screen interactive view accessed by tapping the tile.
- **AI Tool Integration**: Many widgets expose structured tools (e.g. `get_weather_summary`, `get_calendar_events`, `create_alert`, `add_shopping_item`) that the AI voice assistant can call during conversations.

---

## All Built-in Widgets

| Widget | Type | Category | Summary Description |
|---|---|---|---|
| [AI Daily Briefing](ai-insights.md) | `ai` | Productivity / AI | Scheduled AI summary and prompt runner with tool calling. |
| [Alerts](alert.md) | `alert` | System | Household and AI notification banner with severity indicators. |
| [Asus Router](asus-router.md) | `asus_router` | Network | Asus router WAN status, connected client list, and port scanner via SSH. |
| [Battlefield 6 / Stats](bf6.md) | `bf6` | Gaming | Live player stats and community server tracker via gametools.network. |
| [Bookmarks](bookmarks.md) | `bookmarks` | Utilities | Touch-friendly web bookmark launcher with auto-extracted favicons. |
| [Calendar](calendar.md) | `calendar` | Productivity | Multi-provider calendar events (Google, Microsoft 365, CalDAV / iCloud). |
| [Chores / To-Do](chores.md) | `chores` | Productivity | Personal to-do checklist for each household member. |
| [Clock](clock.md) | `clock` | Display | Multi-style clock (Digital, Analog, Binary, Word, Matrix). |
| [Container (Docker/Podman)](container.md) | `container` | Homelab | Multi-host Docker and Podman container monitor and log viewer. |
| [Date](date.md) | `date` | Display | Calendar date, day of week, and custom timezone display. |
| [Discord](discord.md) | `discord` | Social | Live Discord channel and thread message viewer with ticker modes. |
| [Flights (ADS-B)](flights.md) | `flights` | Travel | Live overhead aircraft radar, airline logos, and flight telemetry. |
| [Game 2048](game2048.md) | `game2048` | Games | Fullscreen 2048 puzzle game with swipe and keyboard controls. |
| [Goodreads](goodreads.md) | `goodreads` | Media | Goodreads reading progress and bookshelf status. |
| [HDHomeRun Live TV](hdhomerun.md) | `hdhomerun` | Media | Live TV streaming, EPG program guide, DVR recordings, and HW transcode. |
| [Jellyfin](jellyfin.md) | `jellyfin` | Media | Media server integration, active streams, and remote playback. |
| [Mapping & Directions](mapping.md) | `mapping` | Travel | Leaflet map with driving/walking/cycling directions and nearby places. |
| [Message Board](message.md) | `message` | Productivity | Household sticky note and announcement board. |
| [Movies & Shows](movies.md) | `movies` | Media | TMDB trending titles and streaming provider availability via JustWatch. |
| [NASA APOD](nasa-apod.md) | `nasa_apod` | Display | Daily Astronomy Picture of the Day with full-res imagery. |
| [Package Tracking](packages.md) | `packages` | Utilities | Multi-carrier package delivery tracking via 17Track. |
| [Photos Slideshow](photos.md) | `photos` | Media | Slideshow from local folders, iCloud Shared Albums, iCloud Private, or Immich. |
| [Pi-hole](pihole.md) | `pihole` | Network | Pi-hole v6+ DNS ad-blocking metrics, block rate, and top clients. |
| [qBittorrent](qbittorrent.md) | `qbittorrent` | Media | Active torrent downloads, speeds, and status management. |
| [RSS News](rss.md) | `rss` | News | RSS/Atom feed reader and headline ticker. |
| [Shopping List](shopping.md) | `shopping` | Productivity | Shared household grocery and shopping checklist. |
| [Speedtest](speedtest.md) | `speedtest` | Network | Internet speed metrics (down/up/ping) and history graphs. |
| [Sports Scores](sports.md) | `sports` | Sports | Live scores and TV broadcast networks for NFL, NBA, MLB, NHL, NCAA, WNBA. |
| [Steam](steam.md) | `steam` | Gaming | Currently playing game, recent activity, and online friends list. |
| [Synology NAS](synology.md) | `synology` | Storage | Synology DSM volume usage, disk health, CPU temp, and system uptime. |
| [System Monitor](system-monitor.md) | `system_monitor` | System | Host CPU, RAM, disk, and network throughput via psutil. |
| [Weather](weather.md) | `weather` | Weather | Open-Meteo forecasts, hourly/daily trends, air quality, pollen, and alerts. |
| [Wordle](wordle.md) | `wordle` | Games | Daily word puzzle game with touch keyboard and streak tracking. |
