"""Heat per band of the day, and the bands the day never bid for. Report only."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import session_capital as sc  # noqa: E402

NOW = datetime(2026, 9, 9, tzinfo=UTC)


def _alloc(**over):
    base = {"book": {}, "marginal_delta_elog": {}, "heat": {"target": 0.20, "total": 0.10}}
    base.update(over)
    return base


def test_bands_carry_the_books_heat_and_the_priced_value() -> None:
    from research.portfolio_gap import band_of, window_hours
    hours = window_hours()
    # single-token windows only: sleeve_axes takes the last "_" segment as the window
    win, other = "asia", "afternoon"          # 07:00 -> 04-08, 17:00 -> 16-20
    doc = sc.build(_alloc(book={f"XAUUSD_session_range_breakout_{win}": 0.08,
                                f"EURUSD_overnight_gap_decay_{other}": 0.02},
                          marginal_delta_elog={f"EURUSD_overnight_gap_decay_{other}": 0.5,
                                               f"XAUUSD_session_range_breakout_{win}": -0.1}),
                   [{"symbol": "XAUUSD", "window": win, "family": "session_range_breakout"}],
                   ledger=Path("/nonexistent"), now=NOW)
    rows = {r["band"]: r for r in doc["bands"]}
    assert rows[band_of(hours[win])]["held_heat"] == 0.08
    assert rows[band_of(hours[win])]["certificates"] == 1
    assert rows[band_of(hours[other])]["positive_marginal"] == 0.5
    assert rows[band_of(hours[win])]["positive_marginal"] == 0.0, "a negative marginal is not value"
    assert doc["unfilled_heat"] == 0.1 and doc["measured"] is True


def test_a_band_with_value_and_no_heat_is_underspent_and_an_empty_band_is_dark() -> None:
    from research.portfolio_gap import band_of, window_hours
    hours = window_hours()
    win, other = "asia", "afternoon"
    doc = sc.build(_alloc(book={f"XAUUSD_f_{win}": 0.10},
                          marginal_delta_elog={f"EURUSD_g_{other}": 0.3}),
                   [], ledger=Path("/nonexistent"), now=NOW)
    assert band_of(hours[other]) in doc["underspent_bands"]
    assert band_of(hours[win]) not in doc["underspent_bands"]
    assert band_of(hours[win]) not in doc["dark_bands"]
    assert len(doc["dark_bands"]) >= 3, "the bands nothing trades are named"


def test_no_unfilled_heat_means_nothing_is_underspent() -> None:
    other = "afternoon"
    doc = sc.build(_alloc(heat={"target": 0.20, "total": 0.20},
                          marginal_delta_elog={f"EURUSD_g_{other}": 0.3}),
                   [], ledger=Path("/nonexistent"), now=NOW)
    assert doc["unfilled_heat"] == 0.0 and doc["underspent_bands"] == []


def test_realised_r_is_read_per_band_from_the_ledger(tmp_path: Path) -> None:
    led = tmp_path / "live_ledger.jsonl"
    led.write_text("".join(json.dumps(r) + "\n" for r in [
        {"closed_at": "2026-09-08T01:00:00+00:00", "realized_r": 1.5},
        {"closed_at": "2026-09-08T02:30:00+00:00", "realized_r": -0.5},
        {"closed_at": "2026-09-08T14:00:00+00:00", "r_multiple": 2.0},
        {"closed_at": "bad stamp", "realized_r": 9.0},
        {"realized_r": 9.0}]) + "not json\n", "utf-8")
    doc = sc.build(_alloc(), [], ledger=led, now=NOW)
    rows = {r["band"]: r for r in doc["bands"]}
    assert rows["00-04"]["realised"] == {"n": 2, "r": 1.0, "mean_r": 0.5}
    assert rows["12-16"]["realised"] == {"n": 1, "r": 2.0, "mean_r": 2.0}
    assert rows["04-08"]["realised"] is None


def test_an_empty_desk_is_unmeasured_and_main_writes_it(tmp_path: Path, monkeypatch) -> None:
    assert sc.build(_alloc(), [], ledger=Path("/nonexistent"), now=NOW)["measured"] is False
    monkeypatch.setattr(sc, "ALLOC", tmp_path / "a.json")
    monkeypatch.setattr(sc, "SURVIVORS", tmp_path / "s.json")
    monkeypatch.setattr(sc, "LEDGER", tmp_path / "l.jsonl")
    monkeypatch.setattr(sc, "OUT", tmp_path / "out.json")
    assert sc.main([]) == 0
    doc = json.loads((tmp_path / "out.json").read_text("utf-8"))
    assert doc["measured"] is False and "no sizing, no cap" in doc["why"]
