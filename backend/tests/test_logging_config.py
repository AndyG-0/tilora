from __future__ import annotations

import logging

from app.logging_config import RequestIdFilter, request_id_ctx


def test_request_id_filter_defaults_to_placeholder_outside_a_request():
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "msg", (), None)

    assert RequestIdFilter().filter(record) is True
    assert record.request_id == "-"


def test_request_id_filter_tags_record_with_the_current_context_value():
    token = request_id_ctx.set("abc123")
    try:
        record = logging.LogRecord("test", logging.INFO, __file__, 1, "msg", (), None)
        RequestIdFilter().filter(record)
        assert record.request_id == "abc123"
    finally:
        request_id_ctx.reset(token)


def test_configure_logging_quiets_third_party_loggers_at_info_level(monkeypatch):
    from app.config import settings
    from app.logging_config import configure_logging

    monkeypatch.setattr(settings, "log_level", "INFO")
    configure_logging()

    assert logging.getLogger().level == logging.INFO
    assert logging.getLogger("asyncssh").level == logging.WARNING
    assert logging.getLogger("httpx").level == logging.WARNING
    assert logging.getLogger("httpcore").level == logging.WARNING
    assert logging.getLogger("icloudpy").level == logging.CRITICAL
    assert logging.getLogger("uvicorn.access").level == logging.WARNING


def test_configure_logging_enables_debug_level_for_third_party_when_debug(monkeypatch):
    from app.config import settings
    from app.logging_config import configure_logging

    monkeypatch.setattr(settings, "log_level", "DEBUG")
    configure_logging()

    assert logging.getLogger().level == logging.DEBUG
    assert logging.getLogger("asyncssh").level == logging.DEBUG
    assert logging.getLogger("httpx").level == logging.DEBUG
    assert logging.getLogger("httpcore").level == logging.DEBUG
    assert logging.getLogger("icloudpy").level == logging.DEBUG
    assert logging.getLogger("uvicorn.access").level == logging.DEBUG
