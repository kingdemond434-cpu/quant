"""Frozen bars are withheld from minting; a slow leg or an outage never empties the universe."""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
if str(DESK) not in sys.path:
    sys.path.insert(0, str(DESK))

from research import bar_freshness as bf  # noqa: E402

END = datetime(2026, 11, 4, 12, tzinfo=UTC)


def _bars(root: Path, sym: str, last: datetime, n: int = 48) -> None:
    idx = pd.date_range(end=last.replace(tzinfo=None), periods=n, freq="h", name="time")
    pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0}, index=idx).to_parquet(
        root / f"{sym}_H1.parquet"
    )


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(bf, "REPORT", tmp_path / "STALE_BARS.json")
    monkeypatch.setattr(bf, "SWITCH_OFF", tmp_path / "STALE_BAR_GUARD_OFF")


def test_a_series_that_stopped_while_the_rest_moved_is_withheld(tmp_path):
    for s in ("EURUSD", "USDJPY", "XAUUSD", "US500"):
        _bars(tmp_path, s, END)
    _bars(tmp_path, "UST10Y", datetime(2025, 12, 31, 22, tzinfo=UTC))
    kept, doc = bf.live_symbols({"EURUSD", "USDJPY", "XAUUSD", "US500", "UST10Y"}, tmp_path)
    assert "UST10Y" not in kept and len(kept) == 4
    assert doc["withheld_from_minting"] == ["UST10Y"]
    assert doc["frozen"]["UST10Y"] > 300
    assert bf.REPORT.exists()
    assert doc["missed_growth"]["withheld_symbols"] == 1


def test_a_slow_refresh_leg_holding_most_symbols_is_never_frozen(tmp_path):
    # FX refreshed hourly, the equity leg three weeks behind: the median follows the majority.
    for s in ("EURUSD", "USDJPY"):
        _bars(tmp_path, s, END)
    for s in ("AAPL", "MSFT", "NVDA"):
        _bars(tmp_path, s, END - timedelta(days=21))
    kept, doc = bf.live_symbols({"EURUSD", "USDJPY", "AAPL", "MSFT", "NVDA"}, tmp_path)
    assert len(kept) == 5 and doc["verdict"] == "ALL_FRESH"


def test_an_outage_that_ages_everything_freezes_nothing(tmp_path):
    for s in ("EURUSD", "USDJPY", "XAUUSD"):
        _bars(tmp_path, s, END - timedelta(days=60))
    kept, _ = bf.live_symbols({"EURUSD", "USDJPY", "XAUUSD"}, tmp_path)
    assert kept == {"EURUSD", "USDJPY", "XAUUSD"}


def test_unreadable_file_is_unmeasured_never_frozen(tmp_path):
    for s in ("EURUSD", "USDJPY"):
        _bars(tmp_path, s, END)
    (tmp_path / "BROKEN_H1.parquet").write_bytes(b"not a parquet")
    kept, doc = bf.live_symbols({"EURUSD", "USDJPY", "BROKEN"}, tmp_path)
    assert "BROKEN" in kept and doc["unmeasured"] == ["BROKEN"]


def test_switch_off_keeps_every_symbol(tmp_path):
    _bars(tmp_path, "EURUSD", END)
    _bars(tmp_path, "USDJPY", END)
    _bars(tmp_path, "UST10Y", datetime(2025, 12, 31, tzinfo=UTC))
    bf.SWITCH_OFF.write_text("")
    kept, doc = bf.live_symbols({"EURUSD", "USDJPY", "UST10Y"}, tmp_path)
    assert "UST10Y" in kept and doc["verdict"] == "SWITCHED_OFF"


def test_compiler_universe_withholds_the_frozen_series(tmp_path, monkeypatch):
    import research.miner_candidate_compiler as mcc

    for s in ("EURUSD", "USDJPY", "XAUUSD"):
        _bars(tmp_path, s, END)
    _bars(tmp_path, "UST05Y", datetime(2025, 12, 31, tzinfo=UTC))
    monkeypatch.setattr(mcc, "UNIVERSE", tmp_path)
    universe, note = mcc.live_known_symbols()
    assert universe == {"EURUSD", "USDJPY", "XAUUSD"}
    assert note["withheld_from_minting"] == ["UST05Y"]


def test_a_cell_reading_a_frozen_factor_is_withheld_by_name():
    import research.miner_candidate_compiler as mcc

    cands = [
        {
            "symbol": "EURUSD",
            "family": "cross_asset_residual",
            "params": {"factor_symbols": ["USDX", "UST10Y"]},
        },
        {"symbol": "XAUUSD", "family": "lead_lag", "params": {"peer_symbol": "UST05Y"}},
        {"symbol": "USDJPY", "family": "pairs", "params": {"leg_b_symbol": "EURUSD"}},
        {"symbol": "UST10Y", "family": "turn_of_month", "params": {}},
    ]
    kept, withheld = mcc.withhold_frozen_inputs(cands, {"UST10Y", "UST05Y"})
    assert [c["symbol"] for c in kept] == ["USDJPY"]
    assert withheld == ["UST10Y", "UST05Y", "UST10Y"]


def test_ust10y_spelled_in_lower_case_is_still_withheld():
    import research.miner_candidate_compiler as mcc

    kept, withheld = mcc.withhold_frozen_inputs(
        [{"symbol": "EURUSD", "params": {"factor_symbols": ["ust10y"]}}], {"UST10Y"}
    )
    assert kept == [] and withheld == ["UST10Y"]


class _GraphStub:
    def prior_failures(self, *_a, **_k):
        return {"n_failed": 0, "region": ""}

    def rows(self):
        return []


def test_a_row_whose_only_cell_reads_a_frozen_factor_is_refused_never_deepened(
    tmp_path, monkeypatch
):
    import json

    import research.miner_candidate_compiler as mcc

    import libs.ops.repair_invoke as ri
    import libs.research.hypothesis_graph as hg

    root = tmp_path / "intel"
    (root / "seat").mkdir(parents=True)
    row = {
        "kind": "hypothesis",
        "family": "cross_asset_residual",
        "symbols": ["EURUSD"],
        "title": "dollar residual",
        "url": "u1",
    }
    (root / "seat" / "discoveries_1.json").write_text(json.dumps([row]), "utf-8")
    for name, val in (
        ("INTEL_ROOTS", (root,)),
        ("OUT", tmp_path / "out.json"),
        ("DEEPEN", tmp_path / "deepen.json"),
        ("DEEPEN_WORKED", tmp_path / "worked.jsonl"),
        ("DEEPENED", tmp_path / "deepened.json"),
        ("CURSOR", tmp_path / "cursor.json"),
    ):
        monkeypatch.setattr(mcc, name, val)
    cell = {
        "symbol": "EURUSD",
        "family": "cross_asset_residual",
        "params": {"factor_symbols": ["UST10Y"]},
        "mechanism_status": "NAMED",
        "mechanism_note": "the dollar residual against the ten-year yield",
    }
    monkeypatch.setattr(
        mcc, "live_known_symbols", lambda: ({"EURUSD"}, {"frozen": {"UST10Y": 308.0}})
    )
    monkeypatch.setattr(mcc, "compile_row", lambda *_a, **_k: ([dict(cell)], "EXACT_RECIPE"))
    monkeypatch.setattr(mcc, "structurally_untestable_families", dict)
    monkeypatch.setattr(mcc, "expand_axes", lambda rows: rows)
    monkeypatch.setattr(hg, "Graph", _GraphStub)
    monkeypatch.setattr(hg, "record_candidates", lambda *a, **k: 0)
    monkeypatch.setattr(ri, "request_repair", lambda reason, **kw: False)
    assert mcc.main() == 0
    out = json.loads((tmp_path / "out.json").read_text("utf-8"))
    stats = out["per_source"]["seat"]
    assert stats["valid_refusals"] == 1
    assert stats["convertible_rows"] == 0 and stats["candidates"] == 0
    assert out["stale_bars"]["withheld_inputs"] == {"UST10Y": 1}
    deepen = tmp_path / "deepen.json"
    tasks = json.loads(deepen.read_text("utf-8"))["tasks"] if deepen.exists() else []
    assert tasks == []
