"""Artificial Analysis language-model leaderboard HTTP client
(artificialanalysis.ai/data-api).

Only the free-tier endpoint (`/language/models/free`) is used — there is no
shared/demo key for this API, unlike NASA's, so a missing key fails fast
without a network call rather than falling back to anything.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_BASE_URL = "https://artificialanalysis.ai/api/v2/language/models/free"
_TIMEOUT_SECONDS = 20

# One retry is enough to smooth over a transient blip (a dropped connection,
# a momentary 5xx, a 429) — anything that fails twice in a row is unlikely to
# be fixed by a third try, and this endpoint is only ever called at most once
# a day (see ArtificialAnalysisPlugin._should_refetch), so there's no benefit
# to a longer backoff/retry budget here.
_MAX_ATTEMPTS = 2
_RETRY_BACKOFF_SECONDS = 0.5
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

# Safety cap so a misbehaving API (e.g. `has_more` never turning false)
# can't loop forever; the free language-model list is expected to fit on a
# single ~200-item page in practice.
_MAX_PAGES = 20


class ArtificialAnalysisError(Exception):
    """Raised when the Artificial Analysis API can't be reached or rejects a request."""


def _flatten_model(raw: dict[str, Any]) -> dict[str, Any]:
    evaluations = raw.get("evaluations") or {}
    pricing = raw.get("pricing") or {}
    performance = raw.get("performance") or {}
    creator = raw.get("model_creator") or {}

    price_input = pricing.get("price_1m_input_tokens")
    price_output = pricing.get("price_1m_output_tokens")
    blended_price = None
    if price_input is not None and price_output is not None:
        blended_price = (3 * price_input + price_output) / 4

    return {
        "id": raw.get("id"),
        "name": raw.get("name"),
        "slug": raw.get("slug"),
        "release_date": raw.get("release_date"),
        "creator": creator.get("name"),
        "intelligence_index": evaluations.get("artificial_analysis_intelligence_index"),
        "coding_index": evaluations.get("artificial_analysis_coding_index"),
        "agentic_index": evaluations.get("artificial_analysis_agentic_index"),
        "price_input_per_1m": price_input,
        "price_output_per_1m": price_output,
        "price_cache_hit_per_1m": pricing.get("price_1m_cache_hit_tokens"),
        "price_cache_write_per_1m": pricing.get("price_1m_cache_write_tokens"),
        "blended_price_per_1m": blended_price,
        "output_tokens_per_second": performance.get("median_output_tokens_per_second"),
        "time_to_first_token_seconds": performance.get("median_time_to_first_token_seconds"),
        "time_to_first_answer_token_seconds": performance.get("median_time_to_first_answer_token_seconds"),
        "end_to_end_response_time_seconds": performance.get("median_end_to_end_response_time_seconds"),
    }


async def _get_page(client: httpx.AsyncClient, api_key: str, page: int) -> dict[str, Any]:
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        is_last_attempt = attempt == _MAX_ATTEMPTS
        try:
            response = await client.get(_BASE_URL, headers={"x-api-key": api_key}, params={"page": page})
        except httpx.HTTPError as exc:
            if is_last_attempt:
                raise ArtificialAnalysisError(f"Could not reach Artificial Analysis API: {exc}") from exc
            logger.debug("Artificial Analysis request failed (%s), retrying", exc)
            await asyncio.sleep(_RETRY_BACKOFF_SECONDS)
            continue

        if response.status_code in _RETRYABLE_STATUS_CODES and not is_last_attempt:
            logger.debug("Artificial Analysis API returned HTTP %s, retrying", response.status_code)
            await asyncio.sleep(_RETRY_BACKOFF_SECONDS)
            continue
        break

    try:
        body = response.json()
    except ValueError as exc:
        raise ArtificialAnalysisError("Artificial Analysis API returned a non-JSON response") from exc

    if response.status_code >= 400:
        message = body.get("error", {}).get("message") if isinstance(body.get("error"), dict) else None
        raise ArtificialAnalysisError(f"Artificial Analysis API error: {message or f'HTTP {response.status_code}'}")

    return body


async def get_language_models(api_key: str | None) -> list[dict[str, Any]]:
    """Fetch every page of GET /api/v2/language/models/free, flattened.

    Raises ArtificialAnalysisError immediately (no network call) if `api_key`
    is empty, since this API has no shared/demo key to fall back to.
    """
    if not api_key:
        raise ArtificialAnalysisError("Artificial Analysis API key is not configured")

    models: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
        page = 1
        while page <= _MAX_PAGES:
            body = await _get_page(client, api_key, page)
            models.extend(_flatten_model(raw) for raw in body.get("data") or [])
            pagination = body.get("pagination") or {}
            if not pagination.get("has_more"):
                break
            page += 1

    return models


def is_configured(api_key: str | None) -> bool:
    return bool(api_key)
