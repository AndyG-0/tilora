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

# litellm defaults `max_tokens`/`max_completion_tokens` to unbounded ("infinity"
# per its own docstring) when omitted. For OpenAI-family models this lets the
# provider reserve the model's entire remaining context window as output
# headroom when checking a request against a TPM rate limit — a large-context
# reasoning model can reserve hundreds of thousands of tokens for a one-line
# question, tripping even a generous rate limit. Anthropic doesn't show this
# (it requires a bounded max_tokens on every request), but capping here keeps
# behavior consistent and answers concise across providers regardless.
_MAX_COMPLETION_TOKENS = 4096

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
    if key_name is None:
        # Unknown/custom provider prefix — fall back to whichever key is
        # configured, so a custom/test model string still works.
        return settings.get("anthropic_api_key") or settings.get("openai_api_key") or settings.get("gemini_api_key")
    # Known provider: only ever use its own key. Falling back to another
    # provider's key here would send it to the wrong provider's API (e.g. an
    # OpenAI key sent as `x-api-key` to Anthropic), producing a confusing
    # auth error instead of a clear "no key configured" one.
    return settings.get(key_name)


class AIProvider:
    def __init__(self, tool_bridge: ToolBridge, model: str | None = None):
        self._tools = tool_bridge
        self._model = model or effective_settings()["ai_model"]

    async def run_prompt(self, prompt: str, max_tool_rounds: int = 4, system_prompt: str | None = None) -> str:
        """Run a prompt to completion, letting the model call tools as needed.

        `system_prompt`, when given, is prepended as a `system` message —
        used by the voice assistant route to ask for plain, speakable
        sentences, since its answer goes straight into `SpeechSynthesis`.
        Scheduled AI-insight widgets (rendered as text on a tile) pass none.
        """
        # Imported lazily: litellm pulls in the openai SDK, tiktoken,
        # tokenizers, and huggingface_hub (~200MB RSS, ~1s import time), so
        # installs that never use the AI assistant or an ai_insights widget
        # shouldn't pay that cost on every backend start.
        import litellm

        messages: list[dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        tool_schemas = self._tools.schemas()
        settings = effective_settings()
        api_key = _api_key_for_model(self._model, settings)
        # `drop_params=True` scopes the leniency to just this one param: if the
        # configured model doesn't support reasoning_effort, litellm drops it
        # instead of raising UnsupportedParamsError, so the setting stays safe
        # to turn on regardless of which model/provider is currently active.
        reasoning_effort = settings.get("ai_reasoning_effort")
        extra_kwargs: dict[str, Any] = (
            {"reasoning_effort": reasoning_effort, "drop_params": True} if reasoning_effort else {}
        )

        for _ in range(max_tool_rounds):
            response = await litellm.acompletion(
                model=self._model,
                messages=messages,
                tools=tool_schemas or None,
                api_key=api_key,
                timeout=_REQUEST_TIMEOUT_SECONDS,
                num_retries=_NUM_RETRIES,
                max_completion_tokens=_MAX_COMPLETION_TOKENS,
                **extra_kwargs,
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
            max_completion_tokens=_MAX_COMPLETION_TOKENS,
            **extra_kwargs,
        )
        return response.choices[0].message.content or ""
