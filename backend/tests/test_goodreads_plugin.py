from __future__ import annotations

import httpx
import respx

from app.plugins.goodreads.plugin import GoodreadsPlugin

SHELF_FEED = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>listopia</title>
<item>
<title>Project Hail Mary by Andy Weir</title>
<link>https://www.goodreads.com/review/show/1</link>
<book_id>54493401</book_id>
<book_image_url>https://images.gr.example/hail-mary.jpg</book_image_url>
<author_name>Andy Weir</author_name>
<isbn>0593135202</isbn>
<user_rating>0</user_rating>
<user_read_at></user_read_at>
<user_date_added>Wed, 01 Jan 2026 12:00:00 -0800</user_date_added>
<average_rating>4.51</average_rating>
</item>
<item>
<title>Dune by Frank Herbert</title>
<link>https://www.goodreads.com/review/show/2</link>
<book_id>44767458</book_id>
<book_image_url>https://images.gr.example/dune.jpg</book_image_url>
<author_name>Frank Herbert</author_name>
<isbn>0441013597</isbn>
<user_rating>5</user_rating>
<user_read_at>Sun, 15 Feb 2026 12:00:00 -0800</user_read_at>
<user_date_added>Mon, 01 Dec 2025 12:00:00 -0800</user_date_added>
<average_rating>4.24</average_rating>
</item>
</channel>
</rss>
"""


def make_plugin(widget_id: str = "goodreads", **settings) -> GoodreadsPlugin:
    return GoodreadsPlugin({"id": widget_id, "settings": settings})


@respx.mock
async def test_get_summary_returns_books_with_covers_and_authors():
    respx.get("https://www.goodreads.com/review/list_rss/12345").mock(
        return_value=httpx.Response(200, content=SHELF_FEED)
    )
    plugin = make_plugin(user_id="12345", shelf="currently-reading")

    summary = await plugin.get_summary()

    assert summary["shelf"] == "currently-reading"
    assert [book["title"] for book in summary["books"]] == [
        "Project Hail Mary by Andy Weir",
        "Dune by Frank Herbert",
    ]
    assert summary["books"][0]["book_image_url"] == "https://images.gr.example/hail-mary.jpg"
    assert summary["books"][0]["author_name"] == "Andy Weir"
    assert "isbn" not in summary["books"][0]


@respx.mock
async def test_get_summary_respects_item_count_limit():
    many_items = b"".join(
        f"""<item>
<title>Book {i}</title>
<link>https://www.goodreads.com/review/show/{i}</link>
<author_name>Author {i}</author_name>
</item>
""".encode()
        for i in range(10)
    )
    feed = b'<?xml version="1.0"?><rss version="2.0"><channel><title>shelf</title>' + many_items + b"</channel></rss>"
    respx.get("https://www.goodreads.com/review/list_rss/12345").mock(return_value=httpx.Response(200, content=feed))
    plugin = make_plugin(user_id="12345")

    summary = await plugin.get_summary()

    assert len(summary["books"]) == 5


@respx.mock
async def test_get_detail_includes_ratings_and_dates():
    respx.get("https://www.goodreads.com/review/list_rss/12345").mock(
        return_value=httpx.Response(200, content=SHELF_FEED)
    )
    plugin = make_plugin(user_id="12345", shelf="read")

    detail = await plugin.get_detail()

    assert detail["shelf"] == "read"
    assert detail["user_id"] == "12345"
    dune = detail["books"][1]
    assert dune["isbn"] == "0441013597"
    assert dune["average_rating"] == "4.24"
    assert dune["user_rating"] == "5"
    assert dune["user_date_added"] == "Mon, 01 Dec 2025 12:00:00 -0800"
    assert dune["user_read_at"] == "Sun, 15 Feb 2026 12:00:00 -0800"


async def test_get_summary_returns_no_books_when_user_id_not_configured():
    plugin = make_plugin()

    summary = await plugin.get_summary()

    assert summary["books"] == []


async def test_get_detail_returns_no_books_when_user_id_not_configured():
    plugin = make_plugin()

    detail = await plugin.get_detail()

    assert detail["books"] == []
    assert detail["user_id"] == ""


@respx.mock
async def test_shelf_query_param_is_sent_to_goodreads():
    route = respx.get("https://www.goodreads.com/review/list_rss/12345").mock(
        return_value=httpx.Response(200, content=SHELF_FEED)
    )
    plugin = make_plugin(user_id="12345", shelf="to-read")

    await plugin.get_summary()

    assert route.calls.last.request.url.params["shelf"] == "to-read"


def test_default_settings_start_with_currently_reading_shelf():
    assert GoodreadsPlugin.default_settings == {"user_id": "", "shelf": "currently-reading"}


@respx.mock
async def test_get_detail_degrades_to_empty_when_goodreads_returns_error():
    respx.get("https://www.goodreads.com/review/list_rss/bad-id").mock(return_value=httpx.Response(404))
    plugin = make_plugin(user_id="bad-id", shelf="currently-reading")

    detail = await plugin.get_detail()

    assert detail["books"] == []
    assert detail["user_id"] == "bad-id"


@respx.mock
async def test_get_summary_degrades_to_empty_when_goodreads_returns_error():
    respx.get("https://www.goodreads.com/review/list_rss/bad-id").mock(return_value=httpx.Response(404))
    plugin = make_plugin(user_id="bad-id", shelf="currently-reading")

    summary = await plugin.get_summary()

    assert summary["books"] == []
