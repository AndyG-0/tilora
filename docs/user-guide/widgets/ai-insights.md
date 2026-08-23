# AI Daily Briefing & Scheduled Prompts

The **AI Insights** widget (`type: ai`) executes automated scheduled prompts (e.g. a personalized morning briefing) using your configured AI model. It can call tools from local widgets (weather, calendar, chores) and external MCP servers to ground its answers in real-time data.

---

## Features

- **Scheduled Briefings**: Uses standard cron syntax to run prompts at designated times (e.g. `30 6 * * *` for 6:30 AM every day).
- **Tool-Calling Integration**: Automatically connects to local plugins (`get_weather_summary`, `get_calendar_events`, `get_shopping_list`) to produce context-aware responses.
- **Provider Agnostic**: Runs against any configured LiteLLM provider (Anthropic Claude, OpenAI GPT-4o/o3, Google Gemini).
- **Detail View History**: Tap the tile to view previous AI runs, timestamps, and full response text.

---

## Configuration (`dashboard.yaml`)

```yaml
- id: ai-insights
  type: ai
  enabled: true
  layout: { col: 1, row: 4, colSpan: 2, rowSpan: 1 }
  settings:
    title: "Daily Briefing"
    # Cron format: minute hour day month day_of_week
    cron: "30 6 * * *"
    prompt: >
      Write a short, friendly daily briefing (2-3 sentences) for someone
      glancing at a kitchen dashboard. Use the get_weather_summary tool to
      ground it in the current weather for their location. Mention the
      temperature and one practical suggestion.
```

---

## Requirements

- An AI API key configured in **Settings → Admin settings → AI provider** (Anthropic, OpenAI, or Gemini) or in `backend/.env`.
- See the [AI Providers Guide](../../admin-guide/ai-providers.md) for detailed setup.
