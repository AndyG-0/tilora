from __future__ import annotations

from app.plugins.bookmarks.plugin import BookmarksPlugin


def make_plugin(widget_id: str = "bookmarks", **settings) -> BookmarksPlugin:
    return BookmarksPlugin({"id": widget_id, "settings": settings})


def test_default_settings_start_with_an_empty_bookmark_list():
    assert BookmarksPlugin.default_settings == {"title": "Bookmarks", "bookmarks": []}


async def test_get_summary_returns_title_and_bookmarks():
    bookmarks = [{"name": "GitHub", "url": "https://github.com"}]
    plugin = make_plugin(title="Links", bookmarks=bookmarks)

    summary = await plugin.get_summary()

    assert summary == {"title": "Links", "bookmarks": bookmarks}


async def test_get_detail_returns_title_and_bookmarks():
    bookmarks = [{"name": "GitHub", "url": "https://github.com", "icon": "https://github.com/favicon.ico"}]
    plugin = make_plugin(title="Links", bookmarks=bookmarks)

    detail = await plugin.get_detail()

    assert detail == {"title": "Links", "bookmarks": bookmarks}


async def test_get_summary_title_defaults_to_bookmarks():
    plugin = make_plugin(bookmarks=[])

    summary = await plugin.get_summary()

    assert summary["title"] == "Bookmarks"


async def test_get_ai_tools_exposes_list_bookmarks_tool():
    bookmarks = [{"name": "GitHub", "url": "https://github.com"}]
    plugin = make_plugin(bookmarks=bookmarks)

    tools = plugin.get_ai_tools()

    assert len(tools) == 1
    assert tools[0].name == "list_bookmarks_bookmarks"
    result = await tools[0].handler()
    assert result["bookmarks"] == bookmarks


def test_get_ai_tools_names_are_scoped_per_widget_instance():
    first = make_plugin(widget_id="bookmarks-aaa1111", title="Work", bookmarks=[])
    second = make_plugin(widget_id="bookmarks-bbb2222", title="Personal", bookmarks=[])

    first_tool = first.get_ai_tools()[0]
    second_tool = second.get_ai_tools()[0]

    assert first_tool.name != second_tool.name
    assert first_tool.name == "list_bookmarks_bookmarks-aaa1111"
    assert "Work" in first_tool.description
    assert "Personal" in second_tool.description
