from __future__ import annotations

from app.plugins.chores.plugin import ChoresPlugin
from app.storage import db


def make_plugin(user_id: str | None = "user-1") -> ChoresPlugin:
    return ChoresPlugin({"id": "chores", "settings": {}, "user_id": user_id})


async def test_get_summary_with_no_items(tmp_db):
    plugin = make_plugin()

    assert await plugin.get_summary() == {"title": "To-Do", "chores": [], "open_count": 0}


async def test_get_summary_uses_custom_title(tmp_db):
    plugin = ChoresPlugin({"id": "chores", "settings": {"title": "Chores"}, "user_id": "user-1"})

    summary = await plugin.get_summary()

    assert summary["title"] == "Chores"


async def test_get_summary_without_a_user_id_returns_empty_list(tmp_db):
    plugin = make_plugin(user_id=None)
    db.add_chore("chores", "user-1", "Someone else's item")

    assert await plugin.get_summary() == {"title": "To-Do", "chores": [], "open_count": 0}


async def test_get_summary_counts_only_open_items(tmp_db):
    plugin = make_plugin()
    done = db.add_chore("chores", "user-1", "Done already")
    db.add_chore("chores", "user-1", "Still open")
    db.complete_chore(done["id"], "user-1")

    summary = await plugin.get_summary()

    assert summary["open_count"] == 1
    assert len(summary["chores"]) == 2


async def test_get_detail_matches_get_summary(tmp_db):
    plugin = make_plugin()
    db.add_chore("chores", "user-1", "An item")

    assert await plugin.get_detail() == await plugin.get_summary()


async def test_add_item_tool_persists_chore(tmp_db):
    plugin = make_plugin()
    tools = {t.name: t for t in plugin.get_ai_tools()}

    result = await tools["add_todo_item_chores"].handler(text="Water the plants")

    assert result["text"] == "Water the plants"
    detail = await plugin.get_detail()
    assert detail["chores"][0]["text"] == "Water the plants"


async def test_add_item_tool_without_a_user_returns_error(tmp_db):
    plugin = make_plugin(user_id=None)
    tools = {t.name: t for t in plugin.get_ai_tools()}

    result = await tools["add_todo_item_chores"].handler(text="Nope")

    assert "error" in result


async def test_complete_item_tool_marks_done(tmp_db):
    plugin = make_plugin()
    chore = db.add_chore("chores", "user-1", "Finish me")
    tools = {t.name: t for t in plugin.get_ai_tools()}

    result = await tools["complete_todo_item_chores"].handler(chore_id=chore["id"])

    assert result["completed"] is True


async def test_complete_item_tool_unknown_id_returns_error(tmp_db):
    plugin = make_plugin()
    tools = {t.name: t for t in plugin.get_ai_tools()}

    result = await tools["complete_todo_item_chores"].handler(chore_id=9999)

    assert "error" in result


async def test_remove_item_tool_deletes_chore(tmp_db):
    plugin = make_plugin()
    chore = db.add_chore("chores", "user-1", "Remove me")
    tools = {t.name: t for t in plugin.get_ai_tools()}

    result = await tools["remove_todo_item_chores"].handler(chore_id=chore["id"])

    assert result["removed"]["text"] == "Remove me"
    detail = await plugin.get_detail()
    assert detail["chores"] == []


async def test_remove_item_tool_without_a_user_returns_error(tmp_db):
    plugin = make_plugin(user_id=None)
    tools = {t.name: t for t in plugin.get_ai_tools()}

    result = await tools["remove_todo_item_chores"].handler(chore_id=1)

    assert "error" in result
