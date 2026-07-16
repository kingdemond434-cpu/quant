"""Tests for identifier helpers."""

from __future__ import annotations

import pytest

from libs.core.ids import generate_id, new_correlation_id, new_run_id, new_stamp_id


def test_generate_id_format() -> None:
    value = generate_id("run")
    prefix, _, hexpart = value.partition("_")
    assert prefix == "run"
    assert len(hexpart) == 32
    int(hexpart, 16)  # parses as hex


def test_generate_id_is_unique() -> None:
    assert len({generate_id("x") for _ in range(1000)}) == 1000


def test_generate_id_rejects_invalid_prefix() -> None:
    with pytest.raises(ValueError):
        generate_id("not a prefix")
    with pytest.raises(ValueError):
        generate_id("")


def test_named_id_prefixes() -> None:
    assert new_run_id().startswith("run_")
    assert new_correlation_id().startswith("corr_")
    assert new_stamp_id().startswith("stamp_")
