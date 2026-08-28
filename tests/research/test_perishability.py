"""The perishability fence, and the producer/consumer contract it exists to protect.

Every test here fails if a specific piece of wiring is removed. The three severance tests at the
bottom are the important ones: each reproduces a real defect found on 2026-08-27 in which the
financing chain was complete end to end and severed at one joint, silently, with the carry family
reporting the result as "no data recorded" -- an acquisition task -- rather than as a break.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

from libs.research.perishability import (
    BACKFILLABLE,
    NO_RECORDER,
    PASSING,
    PERISHING,
    RECORDING,
    UNINTERPRETABLE,
    UNMEASURED,
    Observable,
    build_report,
    grade,
)

_NOW = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)

_ROOT = Path(__file__).resolve().parent.parent.parent
_DESK = _ROOT / "desks" / "mt5"


@pytest.fixture
def fo():
    """`desks/mt5` imports itself as `mt5desk.*`, so it needs its own root on sys.path -- the
    same reason its 551 tests have never run in CI. These severance tests deliberately live in
    the suite that DOES run: a fence whose test never executes is not a fence (L1.49)."""
    import importlib
    if str(_DESK) not in sys.path:
        sys.path.insert(0, str(_DESK))
    return importlib.import_module("mt5desk.families_orthogonal")


def _obs(**kw) -> Observable:
    base = {"key": "k", "what": "w", "store": "store", "recorder": "mod:fn",
            "backfill_route": None, "max_staleness_h": 30.0}
    base.update(kw)
    return Observable(**base)  # type: ignore[arg-type]


def _write(root: Path, rel: str, rows: list[dict], age_h: float = 1.0) -> Path:
    d = root / rel
    d.mkdir(parents=True, exist_ok=True)
    p = d / "2026-08-27.json"
    p.write_text(json.dumps(rows), encoding="utf-8")
    ts = (_NOW - timedelta(hours=age_h)).timestamp()
    import os
    os.utime(p, (ts, ts))
    return p


def test_fresh_and_interpretable_is_recording(tmp_path: Path) -> None:
    _write(tmp_path, "store", [{"swap_long": 1.0, "swap_mode": 0}])
    row = grade(_obs(interpretive_fields=("swap_mode",)), tmp_path, _NOW, git_ok=True)
    assert row.status == RECORDING


def test_missing_interpretive_field_is_uninterpretable_not_recording(tmp_path: Path) -> None:
    """A FRESH store of unreadable numbers must not pass. This is the live financing case: 244
    symbols captured five times with no swap_mode, which every row-counting gauge reads as
    healthy."""
    _write(tmp_path, "store", [{"swap_long": -65.67, "swap_short": 32.04}])
    row = grade(_obs(interpretive_fields=("swap_mode", "point")), tmp_path, _NOW, git_ok=True)
    assert row.status == UNINTERPRETABLE
    assert row.missing_interpretive == ["swap_mode", "point"]


def test_uninterpretable_outranks_freshness(tmp_path: Path) -> None:
    """Recorded-and-unreadable is reported ahead of stale, because it looks healthy downstream."""
    _write(tmp_path, "store", [{"swap_long": 1.0}], age_h=999.0)
    row = grade(_obs(interpretive_fields=("swap_mode",)), tmp_path, _NOW, git_ok=True)
    assert row.status == UNINTERPRETABLE


def test_empty_store_with_a_recorder_is_perishing(tmp_path: Path) -> None:
    row = grade(_obs(), tmp_path, _NOW, git_ok=True)
    assert row.status == PERISHING
    assert "delay costs the data" in row.detail


def test_empty_store_with_no_recorder_is_worse(tmp_path: Path) -> None:
    row = grade(_obs(recorder=None), tmp_path, _NOW, git_ok=True)
    assert row.status == NO_RECORDER


def test_named_backfill_route_downgrades_to_backfillable(tmp_path: Path) -> None:
    """The whole point of the fence: a route means waiting is cheap, and that is a real pass."""
    row = grade(_obs(backfill_route="FRED series DGS10, free, full history"),
                tmp_path, _NOW, git_ok=True)
    assert row.status == BACKFILLABLE
    assert BACKFILLABLE in PASSING


def test_unmeasured_is_never_passing() -> None:
    """L1.28a: an unmeasured thing must never read as fine."""
    assert UNMEASURED not in PASSING
    assert PERISHING not in PASSING
    assert NO_RECORDER not in PASSING
    assert UNINTERPRETABLE not in PASSING


def test_stale_store_still_perishes(tmp_path: Path) -> None:
    _write(tmp_path, "store", [{"swap_mode": 0}], age_h=500.0)
    row = grade(_obs(interpretive_fields=("swap_mode",)), tmp_path, _NOW, git_ok=True)
    assert row.status == PERISHING
    assert "stale" in row.detail


def test_empty_register_is_unmeasured_not_pass() -> None:
    """L1.57: a verdict over an empty population is vacuous, never a pass."""
    rep = build_report(register=())
    assert rep.status == UNMEASURED


def test_live_register_is_non_empty_and_in_mandate() -> None:
    """A fence with nothing in its register is decoration. Guards against the roster being
    emptied to make the fence green."""
    rep = build_report()
    assert len(rep.rows) >= 3
    assert any(r.key == "financing_leg" for r in rep.rows)


# --------------------------------------------------------------------------------------------
# The three severances. Each of these passed review as correct code in isolation.
# --------------------------------------------------------------------------------------------

def test_recorder_records_the_fields_that_make_swap_readable() -> None:
    """swap_mode AND point AND contract_size, or the number is a numeral (L1.67)."""
    import importlib
    if str(_DESK) not in sys.path:
        sys.path.insert(0, str(_DESK))
    contract_terms_row = importlib.import_module("mt5desk.tape").contract_terms_row

    class _Info:
        swap_long, swap_short, swap_mode, swap_rollover3days = -6.55, 2.76, 0, 3
        trade_contract_size, trade_tick_size, trade_tick_value = 100_000.0, 1e-5, 1.0
        point, digits = 1e-5, 5
        currency_profit, currency_margin = "USD", "EUR"

    row = contract_terms_row("EURUSD", _Info(), _NOW)
    for f in ("swap_mode", "point", "contract_size", "currency_profit", "observed_at"):
        assert f in row, f"{f} absent -- the recorded swap cannot be converted to money"


def test_carry_consumer_reads_the_parquet_the_recorder_writes(tmp_path, monkeypatch, fo) -> None:
    """SEVERANCE 1: the recorder writes .parquet; the consumer globbed *.json only, so the carry
    family would have stayed dark even after the recorder was scheduled."""
    terms = tmp_path / "contract_terms"
    terms.mkdir(parents=True)
    pd.DataFrame([{"observed_at": "2026-08-27T00:00:00+00:00", "symbol": "USDJPY",
                   "swap_long": 6.35, "swap_short": -16.4, "swap_mode": 0,
                   "point": 0.001, "contract_size": 100_000.0}]).to_parquet(
        terms / "2026-08-27.parquet", index=False)
    monkeypatch.setattr(fo, "TERMS", terms)

    got = fo._swap_terms("USDJPY")
    assert got is not None, "parquet rows invisible to the consumer -- the chain is severed"
    assert got["swap_mode"] == 0


def test_swap_money_refuses_without_a_mode_and_scales_points_correctly(fo) -> None:
    """SEVERANCE 2: the magnitude gate compared a basis-point threshold against a raw field that
    is points on some symbols and currency on others."""
    swap_money_per_lot = fo.swap_money_per_lot

    # points mode on a 3-digit JPY cross: point*contract = 100, so raw 6.35 is 635 in money
    got = swap_money_per_lot({"swap_long": 6.35, "swap_short": -16.4, "swap_mode": 0,
                              "point": 0.001, "contract_size": 100_000.0})
    assert got is not None and got[0] == pytest.approx(635.0)

    # a 5-digit major: point*contract == 1.0, which is why the bug hides on the obvious spot-check
    same = swap_money_per_lot({"swap_long": -6.45, "swap_short": 2.69, "swap_mode": 0,
                               "point": 1e-5, "contract_size": 100_000.0})
    assert same is not None and same[0] == pytest.approx(-6.45)

    # no mode => no unit => stand aside, never a guessed scale
    assert swap_money_per_lot({"swap_long": 6.35, "swap_short": -16.4}) is None
    assert swap_money_per_lot({"swap_long": 6.35, "swap_short": -16.4, "swap_mode": 0}) is None


def test_family_carry_stands_aside_when_the_unit_is_unresolved(tmp_path, monkeypatch, fo) -> None:
    """The CALLER wiring, not just the helper: a terms row with no `swap_mode` must produce no
    signals at all. Without this, `family_carry` compares a bp-named threshold against a raw
    field whose scale is the broker's decimal places, and trades on it."""
    terms = tmp_path / "contract_terms"
    terms.mkdir(parents=True)
    pd.DataFrame([{"observed_at": "2026-08-27T00:00:00+00:00", "symbol": "USDJPY",
                   "swap_long": 6.35, "swap_short": -16.4}]).to_parquet(
        terms / "2026-08-27.parquet", index=False)
    monkeypatch.setattr(fo, "TERMS", terms)

    idx = pd.date_range("2026-01-01", periods=600, freq="1h", tz="UTC")
    df = pd.DataFrame({"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0}, index=idx)
    assert fo.family_carry(df, symbol="USDJPY") == []


def test_edge_search_reads_observed_at_from_parquet() -> None:
    """SEVERANCE 3: the recorder stamps `observed_at`; edge_search read `recorded_at`/`at`, so
    pd.Timestamp(None) raised into a bare `except Exception: continue` and dropped every row."""
    src = (_DESK / "research" / "edge_search.py").read_text("utf-8")
    assert 'glob("*.parquet")' in src, "edge_search cannot see the recorder's parquet output"
    assert '"observed_at"' in src, "edge_search does not read the recorder's own stamp"


def test_terms_only_entry_point_exists() -> None:
    """The financing leg is seconds of work and the tick pull is minutes; binding them meant the
    cheap perishable stream could only be scheduled at the expensive one's cadence."""
    assert "--terms-only" in (_DESK / "mt5desk" / "tape.py").read_text("utf-8")
