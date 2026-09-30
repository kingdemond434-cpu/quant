"""The residual study joins bar-clock trades to wall-clock modifier rows on TRUE UTC (2026-09-30).

A trade's `t` is a bar stamp (the broker's EET/EEST wall clock under a UTC label, 2-3 h ahead);
a `capital_modifier_ledger` row is stamped in true UTC. Joined raw, a London-open trade picked up
a modifier written hours after it entered. The conversion is `libs.regime.session_clock` (#134)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.regime import session_clock  # noqa: E402


def test_a_london_0800_utc_bar_is_broker_1000_in_winter_and_1100_in_summer() -> None:
    stamps = pd.DatetimeIndex(["2026-01-15 10:00", "2026-07-15 11:00"], tz="UTC")
    assert list(session_clock.server_to_utc(stamps).hour) == [8, 8]
    london = session_clock.in_session(stamps, "london")
    assert london is not None and london.tolist() == [True, True]


def _mods(path: Path, rows: list[tuple[str, str, float]]) -> Path:
    path.write_text("\n".join(json.dumps({"t": t, "sleeve": "s", "category": c,
                                          "multiplier": m}) for t, c, m in rows), "utf-8")
    return path


def test_a_london_open_trade_reads_the_modifier_in_force_at_its_true_utc_entry(
        tmp_path, monkeypatch) -> None:
    from research import residual_search as rs
    # 07:00 UTC is in force at the 08:00 UTC London open; the LATE row is written after it
    # (08:30 UTC in summer, 09:30 UTC in winter) and is still before the RAW bar stamp.
    monkeypatch.setattr(rs, "MODIFIERS", _mods(tmp_path / "mods.jsonl", [
        ("2026-07-15T07:00:00+00:00", "EARLY", 1.0), ("2026-07-15T08:30:00+00:00", "LATE", 2.0),
        ("2026-01-15T07:00:00+00:00", "EARLY", 1.0), ("2026-01-15T09:30:00+00:00", "LATE", 2.0)]))
    summer = [{"sleeve": "s", "t": pd.Timestamp("2026-07-15 11:00", tz="UTC"), "r": 1.0}] * 3
    winter = [{"sleeve": "s", "t": pd.Timestamp("2026-01-15 10:00", tz="UTC"), "r": 1.0}] * 3
    got = rs.modifier_policy(summer + winter)
    assert set(got["categories"]) == {"EARLY"}
    assert got["categories"]["EARLY"]["n"] == 6


def test_no_trades_is_still_a_verdict(tmp_path, monkeypatch) -> None:
    from research import residual_search as rs
    monkeypatch.setattr(rs, "MODIFIERS", _mods(tmp_path / "mods.jsonl", [
        ("2026-07-15T07:00:00+00:00", "EARLY", 1.0)]))
    assert rs.modifier_policy([])["status"] == "UNMEASURED"
