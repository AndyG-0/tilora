# RSS / Atom News Widget

The **RSS** widget (`type: rss`) aggregates news articles, tech blogs, and announcements from any public RSS or Atom feed.

---

## Features

- **Multi-Feed Aggregation**: Combines articles from multiple news sources into a single stream.
- **Personal Scope**: Each household member can follow their own set of RSS feeds.
- **Article Reader**: Tap any headline in the detail view to read the summary and open the full article.
- **Screensaver Animation**: Participates in the screensaver cycle with animated headline tickers.

---

## Configuration (`dashboard.yaml`)

```yaml
- id: rss
  type: rss
  enabled: true
  layout: { col: 3, row: 6, colSpan: 2, rowSpan: 2 }
  settings:
    title: "Headlines"
    feeds:
      - url: "https://hnrss.org/frontpage"
        name: "Hacker News"
      - url: "https://feeds.arstechnica.com/arstechnica/index"
        name: "Ars Technica"
    item_limit: 10
```
