"""Locale-aware string lookup for plugin-generated text.

Most plugin output is data (numbers, ISO dates, IDs) that the frontend
renders and formats itself, but a minority of strings are synthesized
server-side (weather condition labels, plugin error messages). `t()` is the
lookup used for those — catalogs are nested JSON under `app/locales/`, kept
in the same dotted-key shape as the frontend's `svelte-i18n` catalogs
(`frontend/src/lib/i18n/locales/`) purely so a key can be eyeballed across
both, though the two are otherwise unrelated systems.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

SUPPORTED_LOCALES = ("en", "es", "fr", "de")
DEFAULT_LOCALE = "en"

# English names for each supported locale, used to phrase LLM instructions
# (e.g. "Respond in Spanish.") — always written in English regardless of the
# target language, since that's what steers the model most reliably.
LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
}

_LOCALES_DIR = Path(__file__).parent / "locales"


@lru_cache(maxsize=len(SUPPORTED_LOCALES))
def _catalog(locale: str) -> dict[str, Any]:
    path = _LOCALES_DIR / f"{locale}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _lookup(catalog: dict[str, Any], key: str) -> str | None:
    node: Any = catalog
    for part in key.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node if isinstance(node, str) else None


def t(key: str, locale: str, **params: Any) -> str:
    """Translate `key` (dotted, e.g. "weather.condition.overcast") for `locale`.

    Falls back to `DEFAULT_LOCALE`, then to the key itself, so a missing
    translation degrades to something visible rather than raising. `**params`
    interpolates via `str.format()`, e.g. `t("sports.error.unsupported_league",
    locale, league=league)` against a catalog value like "Unsupported league
    '{league}'."
    """
    message = _lookup(_catalog(locale), key) or _lookup(_catalog(DEFAULT_LOCALE), key) or key
    return message.format(**params) if params else message
