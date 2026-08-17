"""Lightweight LLM pre-pass that narrows which plugins' tools the main
assistant call needs to see.

Every `/api/assistant/ask` request otherwise sends tool schemas for every
registered plugin (see app.ai.assistant.ask), which is the dominant
contributor to request size and the likely cause of recurring TPM rate
limits. This module runs one small, tool-free completion first to pick out
which topics (plugin ids, the same ones GET /api/assistant/topics lists) are
actually relevant to the user's text, so the caller can restrict
`allowed_widget_ids` to just those for the main call.

Best-effort by design: any failure here (timeout, malformed output, an empty
or all-unrecognized selection) returns None, which app.ai.assistant.ask
already treats as "don't restrict" -- identical to the behavior before this
existed. A router problem must never break or degrade the main call.
"""

from __future__ import annotations

import json
import logging
import re

from app.ai.provider import api_key_for_model
from app.config import effective_settings

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 15
_MAX_COMPLETION_TOKENS = 200

_SYSTEM_PROMPT = (
    "You are a routing step for a smart-home assistant. Given the user's request and a list of "
    "available topics, decide which topics (if any) are relevant to answering it -- a topic is "
    "relevant if answering the request requires looking up data from it. "
    'Respond with ONLY a JSON array of topic ids, e.g. ["weather", "mapping"]. '
    "If the request needs general or current-events knowledge not covered by any topic, or doesn't "
    "clearly match one, respond with an empty array [] -- do not guess."
)

# Non-greedy: models don't always obey "JSON only", so this pulls the first
# bracketed array out of whatever text comes back rather than requiring an
# exact match.
_JSON_ARRAY_PATTERN = re.compile(r"\[.*?\]", re.DOTALL)


def _parse_selected_ids(content: str, valid_ids: set[str]) -> list[str] | None:
    match = _JSON_ARRAY_PATTERN.search(content)
    if match is None:
        return None
    try:
        selected = json.loads(match.group(0))
    except (ValueError, TypeError):
        return None
    if not isinstance(selected, list):
        return None
    ids = [item for item in selected if isinstance(item, str) and item in valid_ids]
    return ids or None


async def select_relevant_topics(text: str, topics: list[dict[str, str]], model: str | None = None) -> list[str] | None:
    """Return the subset of `topics` (each {"id", "name"}) relevant to `text`.

    Returns None -- meaning "don't restrict" -- when `topics` is empty, the
    router call fails outright, or nothing it selected matches a known topic
    id.
    """
    if not topics:
        return None

    # Imported lazily, same as app.ai.provider -- litellm pulls in the
    # openai SDK, tiktoken, tokenizers, and huggingface_hub (~200MB RSS,
    # ~1s import time), so this cost shouldn't be paid on every backend
    # start for installs that never use the AI assistant.
    import litellm

    settings = effective_settings()
    resolved_model = model or settings["ai_model"]
    api_key = api_key_for_model(resolved_model, settings)
    topic_list = "\n".join(f"- {topic['id']}: {topic['name']}" for topic in topics)
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": f"Topics:\n{topic_list}\n\nRequest: {text}"},
    ]

    try:
        response = await litellm.acompletion(
            model=resolved_model,
            messages=messages,
            api_key=api_key,
            timeout=_TIMEOUT_SECONDS,
            num_retries=0,
            max_completion_tokens=_MAX_COMPLETION_TOKENS,
        )
        content = response.choices[0].message.content or "[]"
    except Exception:
        logger.warning("Tool-router call failed; falling back to unrestricted tools", exc_info=True)
        return None

    valid_ids = {topic["id"] for topic in topics}
    return _parse_selected_ids(content, valid_ids)
