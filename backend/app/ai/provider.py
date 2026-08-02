"""Provider-agnostic LLM access, built on litellm.

litellm normalizes chat-completion and tool-calling requests across
providers (Anthropic, OpenAI, ...) behind one interface, so swapping models
is a config change (`AI_MODEL` in .env) rather than a code change.
"""

from __future__ import annotations

import json
from typing import Any

from app.ai.tools import ToolBridge
from app.config import effective_settings

# A scheduled AI job runs unattended (APScheduler cron, no user waiting on a
# response to retry manually), so a hung provider call needs its own bound
# rather than blocking that job indefinitely; litellm applies this per HTTP
# request and retries transient failures (timeouts, 429s, 5xxs) internally.
_REQUEST_TIMEOUT_SECONDS = 60
_NUM_RETRIES = 2

# Maps a model string's "<provider>/..." prefix (litellm's convention) to
# the effective_settings() key holding its API key.
_KEY_BY_MODEL_PREFIX = {
    "anthropic": "anthropic_api_key",
    "openai": "openai_api_key",
    "gemini": "gemini_api_key",
}


def _api_key_for_model(model: str, settings: dict[str, Any]) -> str | None:
    prefix = model.split("/", 1)[0]
    key_name = _KEY_BY_MODEL_PREFIX.get(prefix)
    if key_name and settings.get(key_name):
        return settings[key_name]
    # Unknown prefix (or that provider's key isn't set) — fall back to
    # whichever key is configured, so a custom/test model string still works.
    return settings.get("anthropic_api_key") or settings.get("openai_api_key") or settings.get("gemini_api_key")


class AIProvider:
    def __init__(self, tool_bridge: ToolBridge, model: str | None = None):
        self._tools = tool_bridge
        self._model = model or effective_settings()["ai_model"]

    async def run_prompt(self, prompt: str, max_tool_rounds: int = 4) -> str:
        """Run a prompt to completion, letting the model call tools as needed."""
        # Imported lazily: litellm pulls in the openai SDK, tiktoken,
        # tokenizers, and huggingface_hub (~200MB RSS, ~1s import time), so
        # installs that never use the AI assistant or an ai_insights widget
        # shouldn't pay that cost on every backend start.
        import litellm

        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
        tool_schemas = self._tools.schemas()
        api_key = _api_key_for_model(self._model, effective_settings())

        for _ in range(max_tool_rounds):
            response = await litellm.acompletion(
                model=self._model,
                messages=messages,
                tools=tool_schemas or None,
                api_key=api_key,
                timeout=_REQUEST_TIMEOUT_SECONDS,
                num_retries=_NUM_RETRIES,
            )
            message = response.choices[0].message
            tool_calls = getattr(message, "tool_calls", None)

            if not tool_calls:
                return message.content or ""

            messages.append(message.model_dump())
            for call in tool_calls:
                args = json.loads(call.function.arguments or "{}")
                result = await self._tools.call(call.function.name, args)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": json.dumps(result),
                    }
                )

        # Ran out of tool-call rounds; ask once more without tools to force
        # a final answer from whatever context has been gathered.
        response = await litellm.acompletion(
            model=self._model,
            messages=messages,
            api_key=api_key,
            timeout=_REQUEST_TIMEOUT_SECONDS,
            num_retries=_NUM_RETRIES,
        )
        return response.choices[0].message.content or ""
