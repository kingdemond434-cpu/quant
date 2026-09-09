"""Regression coverage for ForexFactory calendar failure classification."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "desks/mt5/side_channels/forexfactory_miner.py"


@pytest.fixture()
def miner():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("_ff_miner_under_test", _SRC)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_successful_calendar_fetch_does_not_reference_exception(miner, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """A previous dedent used ``e`` after a successful request and killed the miner."""
    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> list[dict[str, str]]:
            return [{"impact": "High", "country": "USD", "title": "CPI", "date": "x"}]

    monkeypatch.setattr(miner.requests, "get", lambda *args, **kwargs: Response())
    rows = miner.mine_calendar()
    assert len(rows) == 2
    assert all(row.get("kind") != "fetch_error" for row in rows)


def test_failed_calendar_fetch_is_emitted_as_error_row(miner, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Failure must be visible to miner health rather than a silent empty result."""
    def fail(*args, **kwargs):
        raise RuntimeError("network unavailable")

    monkeypatch.setattr(miner.requests, "get", fail)
    rows = miner.mine_calendar()
    assert len(rows) == 2
    assert all(row["kind"] == "fetch_error" for row in rows)
    assert all(row["error"] == "RuntimeError: network unavailable" for row in rows)
