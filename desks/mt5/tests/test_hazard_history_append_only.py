"""The hazard's history is append-only, and a recovered sleeve keeps its past breaks (2026-10-06).

`drift_monitor` appends every pass's per-sleeve hazards to data/edge_hazard_history.jsonl and
never rewrites it; each row then carries `past_breaks` from that file, so a sleeve that broke and
recovered is still visibly a sleeve that broke. Every sleeve with a shadow ledger is scored --
funded or not -- and a ledger that stopped is a DATA_FAILURE, never a decay reading.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.research import perishability as ph  # noqa: E402
from research import drift_monitor as dm  # noqa: E402


def _trades(sleeve: str, rs: list[float], day0: int = 1) -> list[SimpleNamespace]:
    return [SimpleNamespace(sleeve=sleeve, when=f"2026-08-{day0 + i // 24:02d}T{i % 24:02d}:00Z",
                            r=r) for i, r in enumerate(rs)]


def _rows(trades: list[SimpleNamespace], past: dict | None = None) -> dict:
    shared = [ph.unmeasured_pressure(c, "not in this fixture")
              for c in ("state_decay", "factor_drift", "relationship_drift")]
    return dm.hazard_by_sleeve({}, {}, trades, claims={"EURUSD_a": 0.4, "GBPUSD_b": 0.4},
                               twin={}, shared=shared, past=past)


def test_history_is_appended_never_rewritten_and_past_breaks_survive_recovery(
        tmp_path: Path) -> None:
    path = tmp_path / "edge_hazard_history.jsonl"
    breaking = _rows(_trades("EURUSD_a", [0.4] * 20 + [-0.4] * 20))
    assert breaking["EURUSD_a"]["verdict"] == ph.BREAKING
    dm.append_hazard_history(breaking, {"scale_days": 120.0}, path)
    first = path.read_text("utf-8")
    healthy = _rows(_trades("EURUSD_a", [0.4] * 40), past=dm.read_hazard_history(path))
    assert healthy["EURUSD_a"]["verdict"] == ph.HOLDING
    assert healthy["EURUSD_a"]["past_breaks"] == 1, "the recovery does not erase the break"
    dm.append_hazard_history(healthy, {"scale_days": 120.0}, path)
    text = path.read_text("utf-8")
    assert text.startswith(first), "the earlier line is byte-for-byte untouched"
    assert len(text.splitlines()) == 2
    assert dm.read_hazard_history(path)["EURUSD_a"]["breaks"] == 1


def test_an_unfunded_sleeve_is_still_measured_and_a_stopped_ledger_is_data_failure() -> None:
    # GBPUSD_b is not on any roster -- only its shadow ledger exists -- and its clock stopped
    # two months before the book's newest trade.
    trades = _trades("EURUSD_a", [0.4] * 40, day0=1) + \
        [SimpleNamespace(sleeve="GBPUSD_b", when=f"2026-06-{1 + i // 24:02d}T{i % 24:02d}:00Z",
                         r=0.4) for i in range(40)]
    rows = _rows(trades)
    assert set(rows) == {"EURUSD_a", "GBPUSD_b"}
    assert rows["GBPUSD_b"]["hazard"] is not None, "shadow observation keeps being measured"
    assert rows["GBPUSD_b"]["causes"][ph.DATA_FAILURE]["flag"] is True
    assert rows["EURUSD_a"]["causes"][ph.DATA_FAILURE]["flag"] is False
    s = dm.hazard_summary(rows, {"scale_days": 108.5})
    assert s["data_failure"] == ["GBPUSD_b"]
    assert s["lines"]["scale_days"] == 108.5 and s["lines"]["prior_scale_days"] == 120.0


def test_a_later_break_the_same_day_is_kept_and_counted_once(tmp_path) -> None:
    """Audit M3 of PR #261: every run appends, so a BREAKING verdict that arrives after the day's
    first run is not lost; breaks are counted at most once per sleeve per UTC day, so the hourly
    leg neither drops nor inflates them."""
    import json as _json

    from research import drift_monitor as dm
    p = tmp_path / "hist.jsonl"
    rows = [{"at": "2026-10-07T01:00:00+00:00", "rows": {"s": {"verdict": "WATCH"}}},
            {"at": "2026-10-07T05:00:00+00:00", "rows": {"s": {"verdict": "BREAKING"}}},
            {"at": "2026-10-07T06:00:00+00:00", "rows": {"s": {"verdict": "BREAKING"}}},
            {"at": "2026-10-08T01:00:00+00:00", "rows": {"s": {"verdict": "BREAKING"}}}]
    p.write_text("".join(_json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    h = dm.read_hazard_history(p)
    assert h["s"]["breaks"] == 2
    assert h["s"]["last_break_at"] == "2026-10-08T01:00:00+00:00"
