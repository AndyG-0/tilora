# AI Providers & Model Configuration

Tilora includes a provider-agnostic AI layer powered by [LiteLLM](https://github.com/BerriAI/litellm). Switching models or providers is purely a configuration setting—no code modifications required.

---

## Supported Providers

Navigate to **Settings → Admin settings → AI provider**:

| Provider | Example Model String | API Key Field |
|---|---|---|
| **Anthropic** | `anthropic/claude-3-7-sonnet-latest`, `anthropic/claude-3-5-haiku-latest` | `Anthropic API key` |
| **OpenAI** | `openai/gpt-4o`, `openai/gpt-4o-mini`, `openai/o3-mini` | `OpenAI API key` |
| **Google Gemini** | `gemini/gemini-2.5-flash`, `gemini/gemini-2.5-pro` | `Gemini API key` |
| **Ollama / Local** | `ollama/llama3.2`, `openai/hosted_vllm/...` | Custom endpoint via `.env` |

---

## Agent Settings

- **Agent Name**: The persona name the AI assistant uses when responding to questions (defaults to `"Tilora"`).
- **Reasoning Effort**: For models supporting tunable extended thinking / reasoning (e.g. OpenAI o-series / GPT-5.x, Anthropic extended thinking, Gemini thinking). Choose `None`, `Minimal`, `Low`, `Medium`, `High`, or `Extra high`.
- **SearXNG URL (Web Search Tool)**: Enter the URL of a self-hosted SearXNG instance (e.g. `http://searxng:8080`). When configured, this gives the AI assistant tools to perform live web searches and fetch web page contents.

---

## External MCP Tools

Tilora supports the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) to bridge external data and tools into the AI assistant alongside local widget tools.

Configure MCP servers in `backend/config/dashboard.yaml`:

```yaml
mcp_servers:
  - name: filesystem
    command: npx
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed/dir"]
  - name: homeassistant
    url: "http://homeassistant.local:8123/mcp"
```
