"""Tests for core enumerations."""

from __future__ import annotations

import logging

import pytest

from libs.core.enums import Environment, LogLevel, RunMode


def test_environment_values() -> None:
    assert {e.value for e in Environment} == {"dev", "live", "test"}
    assert Environment("dev") is Environment.DEV


def test_run_mode_values() -> None:
    assert {m.value for m in RunMode} == {"research", "trade", "ops"}


def test_log_level_is_str_enum() -> None:
    assert LogLevel.INFO == "INFO"
    assert LogLevel("DEBUG") is LogLevel.DEBUG


@pytest.mark.parametrize(
    ("level", "expected"),
    [
        (LogLevel.DEBUG, logging.DEBUG),
        (LogLevel.INFO, logging.INFO),
        (LogLevel.WARNING, logging.WARNING),
        (LogLevel.ERROR, logging.ERROR),
        (LogLevel.CRITICAL, logging.CRITICAL),
    ],
)
def test_log_level_numeric(level: LogLevel, expected: int) -> None:
    assert level.numeric == expected
