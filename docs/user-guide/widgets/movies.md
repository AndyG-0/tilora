# Movies & TV Shows Widget

The **Movies** widget (`type: movies`) connects to The Movie Database (TMDB) to showcase popular and trending films and television series, enriched with streaming availability data sourced from JustWatch.

---

## Features

- **Curated Categories**: Browse `popular_movies`, `popular_tv`, `trending_movies`, `trending_tv`, and `on_streaming`.
- **Where to Stream**: Shows which subscription streaming providers (e.g. Netflix, Prime Video, Disney+, Apple TV+, Max) have each title available in your region.
- **Provider Filtering**: Filter the streaming catalog to just the services your household subscribes to.
- **AI Voice Querying**: Ask *"Tilora, what are the trending sci-fi movies right now?"* or *"Is Dune available on streaming?"*.

---

## Configuration (`dashboard.yaml`)

```yaml
- id: movies
  type: movies
  enabled: true
  layout: { col: 1, row: 5, colSpan: 3, rowSpan: 1 }
  settings:
    region: "US"
    # Optional: limit categories or providers (e.g. [8, 337] for Netflix & Disney+)
    # categories: [popular_movies, popular_tv, trending_movies, trending_tv, on_streaming]
    # providers: [8, 337]
```

---

## Requirements

Requires a free TMDB API key (v3) configured in **Settings → Admin settings → TMDB** or in `backend/.env` as `TMDB_API_KEY`.
