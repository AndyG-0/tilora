from __future__ import annotations

from app.plugins.message.plugin import MessagePlugin


def make_plugin(**settings) -> MessagePlugin:
    return MessagePlugin({"id": "message", "settings": settings})


async def test_get_summary_returns_title_and_text():
    plugin = make_plugin(title="Reminder", text="Take out the trash")

    assert await plugin.get_summary() == {"title": "Reminder", "text": "Take out the trash"}


async def test_get_summary_defaults_to_empty_strings():
    plugin = make_plugin()

    assert await plugin.get_summary() == {"title": "", "text": ""}


async def test_get_detail_matches_get_summary():
    plugin = make_plugin(title="Reminder", text="Take out the trash")

    assert await plugin.get_detail() == await plugin.get_summary()
