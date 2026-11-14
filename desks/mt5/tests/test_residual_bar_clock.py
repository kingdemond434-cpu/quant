"""The residual study joins bar-clock trades to wall-clock modifier rows on TRUE UTC (2026-09-30).

A trade's `t` is a bar stamp (the broker's wall clock, New York + 7 h, under a UTC label: 2-3 h
ahead of UTC); a `capital_modifier_ledger` row is stamped in true UTC. Joined raw, a London-open
trade picked up a modifier written hours after it entered. The conversion is
`libs.regime.session_clock` (#134), and every expected offset below is DERIVED from it -- never
from a hard-coded +2/+3 and never from the box's offset files."""
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


def _broker_stamp(utc: str) -> pd.Timestamp:
    """The bar stamp the helper maps onto this true-UTC instant (the inverse of server_to_utc,
    found by search so the test asserts nothing the helper does not itself say)."""
    u = pd.Timestamp(utc, tz="UTC")
    hits = [u + pd.Timedelta(hours=h) for h in range(0, 13)
            if session_clock.server_to_utc(pd.DatetimeIndex([u + pd.Timedelta(hours=h)]))[0] == u]
    assert len(hits) == 1, (utc, hits)
    return hits[0]


# 08:00 UTC in a winter week, a summer week, and the March week when New York has moved its
# clocks and London has not -- the week that tells the New-York+7 clock from an EET/EEST one.
LONDON_0800_UTC = ("2026-01-15 08:00", "2026-07-15 08:00", "2026-03-10 08:00")


def test_a_london_0800_utc_bar_maps_back_to_0800_utc_through_the_helper() -> None:
    stamps = pd.DatetimeIndex([_broker_stamp(u) for u in LONDON_0800_UTC])
    assert list(session_clock.server_to_utc(stamps).hour) == [8, 8, 8]
    offsets = [int((s - pd.Timestamp(u, tz="UTC")) / pd.Timedelta(hours=1))
               for s, u in zip(stamps, LONDON_0800_UTC, strict=True)]
    assert all(2 <= h <= 3 for h in offsets)
    # the broker clock follows NEW YORK's DST: in the split March week it is already summer
    assert offsets[2] == offsets[1] != offsets[0]
    london = session_clock.in_session(stamps, "london")
    assert london is not None and london.tolist() == [True, True, True]


def _mods(path: Path, rows: list[tuple[str, str, float]]) -> Path:
    path.write_text("\n".join(json.dumps({"t": t, "sleeve": "s", "category": c,
                                          "multiplier": m}) for t, c, m in rows), "utf-8")
    return path


def test_a_london_open_trade_reads_the_modifier_in_force_at_its_true_utc_entry(
        tmp_path, monkeypatch) -> None:
    from research import residual_search as rs
    # 07:00 UTC is in force at the 08:00 UTC London open; the LATE row is written after it
    # (half an hour before the raw stamp read as UTC), so only a raw join would pick it up.
    summer_t = _broker_stamp("2026-07-15 08:00")
    winter_t = _broker_stamp("2026-01-15 08:00")

    def late(stamp: pd.Timestamp) -> str:
        """Half an hour before the RAW bar stamp read as UTC -- after the true entry."""
        return (stamp - pd.Timedelta(minutes=30)).isoformat()
    monkeypatch.setattr(rs, "MODIFIERS", _mods(tmp_path / "mods.jsonl", [
        ("2026-07-15T07:00:00+00:00", "EARLY", 1.0), (late(summer_t), "LATE", 2.0),
        ("2026-01-15T07:00:00+00:00", "EARLY", 1.0), (late(winter_t), "LATE", 2.0)]))
    summer = [{"sleeve": "s", "t": summer_t, "r": 1.0}] * 3
    winter = [{"sleeve": "s", "t": winter_t, "r": 1.0}] * 3
    got = rs.modifier_policy(summer + winter)
    assert set(got["categories"]) == {"EARLY"}
    assert got["categories"]["EARLY"]["n"] == 6


def test_no_trades_is_still_a_verdict(tmp_path, monkeypatch) -> None:
    from research import residual_search as rs
    monkeypatch.setattr(rs, "MODIFIERS", _mods(tmp_path / "mods.jsonl", [
        ("2026-07-15T07:00:00+00:00", "EARLY", 1.0)]))
    assert rs.modifier_policy([])["status"] == "UNMEASURED"
