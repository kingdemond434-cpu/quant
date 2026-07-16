"""Tests for structured logging, correlation ids, and redaction."""

from __future__ import annotations

import json
import logging

import pytest

from libs.core.config import load_settings
from libs.core.logging import (
    REDACTED,
    bind,
    configure_logging,
    correlation_context,
    get_correlation_id,
    get_logger,
)


def _settings(**logging_overrides: object):
    return load_settings("dev", overrides={"logging": logging_overrides})


def _last_json_line(out: str) -> dict:
    lines = [line for line in out.strip().splitlines() if line.strip()]
    assert lines, "no log output captured"
    return json.loads(lines[-1])


def test_json_log_has_core_fields(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(_settings(json=True, level="DEBUG"))
    log = get_logger("test.json")
    log.info("hello", extra={"context": {"symbol": "XAUUSD", "qty": 0.1}})
    record = _last_json_line(capsys.readouterr().out)
    assert record["level"] == "INFO"
    assert record["logger"] == "test.json"
    assert record["message"] == "hello"
    assert record["timestamp"].endswith("Z")
    assert record["context"] == {"symbol": "XAUUSD", "qty": 0.1}


def test_correlation_id_threaded(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(_settings(json=True, level="DEBUG"))
    log = get_logger("test.corr")
    with correlation_context("corr_fixed") as cid:
        assert cid == "corr_fixed"
        assert get_correlation_id() == "corr_fixed"
        log.info("inside")
    record = _last_json_line(capsys.readouterr().out)
    assert record["correlation_id"] == "corr_fixed"
    # context is restored on exit
    assert get_correlation_id() is None


def test_secret_keys_are_redacted(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(_settings(json=True, level="DEBUG"))
    log = get_logger("test.redact")
    log.info(
        "auth",
        extra={"context": {"password": "hunter2", "nested": {"secret": "abc", "ok": 1}}},
    )
    out = capsys.readouterr().out
    record = _last_json_line(out)
    assert record["context"]["password"] == REDACTED
    assert record["context"]["nested"]["secret"] == REDACTED
    assert record["context"]["nested"]["ok"] == 1
    # the actual secret values never appear anywhere in the output
    assert "hunter2" not in out
    assert "abc" not in out


def test_bind_merges_context(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(_settings(json=True, level="DEBUG"))
    log = bind(get_logger("test.bind"), component="risk")
    log.info("sized", extra={"context": {"qty": 2}})
    record = _last_json_line(capsys.readouterr().out)
    assert record["context"] == {"component": "risk", "qty": 2}


def test_human_formatter_is_readable(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(_settings(json=False, level="DEBUG"))
    log = get_logger("test.human")
    with correlation_context("corr_h"):
        log.warning("watch out")
    out = capsys.readouterr().out.strip()
    assert "watch out" in out
    assert "WARNING" in out
    assert "corr_h" in out


def test_configure_logging_is_idempotent() -> None:
    settings = _settings(json=True, level="INFO")
    configure_logging(settings)
    configure_logging(settings)
    root = logging.getLogger()
    tagged = [h for h in root.handlers if getattr(h, "_qp_core_handler", False)]
    assert len(tagged) == 1


def test_level_filters_below_threshold(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(_settings(json=True, level="WARNING"))
    log = get_logger("test.level")
    log.info("suppressed")
    log.warning("shown")
    out = capsys.readouterr().out
    assert "suppressed" not in out
    assert "shown" in out
