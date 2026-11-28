"""#444 rebuilt on LIVE: the armed book never funds a sleeve the roster RETIRED by its own name.

`live_policy_zero` never reads status, so a RETIRED row of an admissible symbol was still funded
and the gateway (LIVE rows only) never placed that heat. `retired_zero` binds those columns to 0
through the exchange-zero path, which refills the heat; STANDBY rows stay priced for admission.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import pf_allocator as pa  # noqa: E402


@pytest.fixture
def roster(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    (data / "sleeves.json").write_text(json.dumps({"sleeves": [
        {"name": "xau_retired_one", "symbol": "XAUUSD", "family": "breakout", "selector": "ny",
         "status": "RETIRED", "retired_by": None, "retire_reason": "rolling-20 exp <= 0"},
        {"name": "xau_standby_one", "symbol": "XAUUSD", "family": "carry", "selector": "asia",
         "status": "STANDBY"},
        {"name": "xau_live_one", "symbol": "XAUUSD", "family": "fade", "selector": "ldn",
         "status": "LIVE"},
        {"name": "usdnok_carry_asia_p_ff35bb7c8427d66f", "symbol": "USDNOK", "family": "carry",
         "selector": "asia", "status": "RETIRED", "retired_by": "live_policy"},
        {"name": "eurusd_old", "symbol": "EURUSD", "family": "drift", "selector": "ny",
         "status": "RETIRED"}]}), "utf-8")
    monkeypatch.setattr(pa, "BASE", tmp_path)
    return tmp_path


def test_only_exact_name_retired_columns_are_zeroed(roster) -> None:
    names = ["xau_retired_one", "xau_standby_one", "xau_live_one",
             "usdnok_carry_asia_p_ff35bb7c8427d66f", "EURUSD_drift_ny", "library_cell"]
    zero, meta = pa.retired_zero(names)
    assert zero == {"xau_retired_one"}
    assert meta["status"] == "MEASURED" and meta["n_zeroed"] == 1
    assert "rolling-20" in meta["zeroed"]["xau_retired_one"]
    # A key-only match is measured, never zeroed: a new candidate of that mechanism joins on it.
    assert meta["key_only_retired"] == ["EURUSD_drift_ny"]


def test_a_retired_zero_refills_heat_through_the_exchange_zero_path(roster) -> None:
    zero, _ = pa.retired_zero(["xau_retired_one", "xau_live_one"])
    assert pa.exchange_zero_bounds({"xau_retired_one": 0.1, "xau_live_one": 0.1},
                                   zero)["xau_retired_one"] == 0.0
    book, meta = pa.exchange_zero({"xau_retired_one": 0.1, "xau_live_one": 0.1}, zero)
    assert book.get("xau_retired_one", 0.0) == 0.0
    # The heat is moved, never cut: the floor stays filled.
    assert book["xau_live_one"] == pytest.approx(0.2)
    assert meta["freed_heat"] == pytest.approx(0.1)


def test_an_unreadable_roster_is_unmeasured_and_zeroes_nothing(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(pa, "BASE", tmp_path)
    zero, meta = pa.retired_zero(["anything"])
    assert zero == frozenset() and meta["status"] == "UNMEASURED"
