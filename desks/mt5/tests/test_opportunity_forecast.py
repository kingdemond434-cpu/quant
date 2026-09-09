"""The graph read forward: recent success ranks first, burials rank last, unjudged cells inherit."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import opportunity_forecast as of  # noqa: E402

NOW = datetime(2026, 9, 9, tzinfo=UTC)


def _row(sym, fam, fate, days_ago, source="miner:reddit"):
    return {"symbol": sym, "family": fam, "fate": fate, "source": source,
            "at": (NOW - timedelta(days=days_ago)).isoformat()}


def test_recent_success_outranks_old_success_and_burials_sink() -> None:
    rows = [_row("XAUUSD", "f", "CERTIFIED", 3), _row("XAUUSD", "f", "BORN", 3),
            _row("EURUSD", "f", "CERTIFIED", 120),
            _row("GBPJPY", "f", "BURIED", 10), _row("GBPJPY", "f", "BURIED", 20),
            _row("GBPJPY", "f", "FAILED", 30)]
    doc = of.forecast(rows, NOW)
    order = [(e["symbol"], e["basis"]) for e in doc["ranked"]]
    assert order == [("XAUUSD", "cell"), ("EURUSD", "cell"), ("GBPJPY", "cell")]
    gbp = doc["ranked"][-1]
    assert gbp["burials"] == 3 and gbp["certified"] == 0 and gbp["score"] < 0.05
    assert doc["status"] == "MEASURED" and doc["cells"] == 3


def test_an_unjudged_cell_is_unexplored_and_carries_its_family_prior() -> None:
    rows = [_row("XAUUSD", "f", "CERTIFIED", 3), _row("XAUUSD", "f", "FAILED", 3),
            _row("USDJPY", "f", "BORN", 1), _row("USDJPY", "f", "BORN", 2)]
    doc = of.forecast(rows, NOW)
    assert [e["symbol"] for e in doc["unexplored"]] == ["USDJPY"]
    u = doc["unexplored"][0]
    assert u["basis"] == "family_prior" and u["certify_rate"] == doc["family_prior"]["f"] == 0.5
    assert u["born"] == 2 and u["last_success_age_d"] is None


def test_a_burial_older_than_the_stale_window_is_a_revival_candidate() -> None:
    rows = [_row("AUDNZD", "g", "BURIED", 400), _row("NZDCAD", "g", "BURIED", 5),
            _row("EURCHF", "g", "BURIED", 400), _row("EURCHF", "g", "CERTIFIED", 2)]
    doc = of.forecast(rows, NOW)
    assert [e["symbol"] for e in doc["stale_graveyard"]] == ["AUDNZD"], \
        "a fresh burial is not stale; a cell that certified since is not a graveyard"
    assert doc["stale_graveyard"][0]["last_burial_age_d"] == 400.0


def test_empty_graph_is_unmeasured_and_main_writes_the_report(tmp_path: Path, monkeypatch) -> None:
    assert of.forecast([], NOW)["status"] == "UNMEASURED"
    import libs.research.hypothesis_graph as hg

    class _G:
        def rows(self):
            return [_row("XAUUSD", "f", "CERTIFIED", 1)]
    monkeypatch.setattr(hg, "Graph", _G)
    monkeypatch.setattr(of, "OUT", tmp_path / "of.json")
    assert of.main([]) == 0
    doc = json.loads((tmp_path / "of.json").read_text("utf-8"))
    assert doc["ranked"][0]["symbol"] == "XAUUSD" and doc["status"] == "MEASURED"
