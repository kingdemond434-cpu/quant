"""The counterfactual-world organ: ledgers in, a versioned dataset and a signed report out.

Pinned here:

  * with no gateway ledger on the box the pass is UNMEASURED with the reason, `main()` exits 0,
    the YIELD line is all zeros and NO dataset and NO watermark are created -- but the report IS
    written, because "this host cannot measure it" is a finding and a missing file is not;
  * with the ledgers and the box's own bars it joins the decision minutes, prices every arm,
    appends the rows to `data/decision_dataset.jsonl` and writes the five alphas with their n;
  * a re-run over unchanged ledgers appends NOTHING and moves nothing -- the watermark and the
    row fingerprint are two independent guards and both are exercised here;
  * a ledger that grows appends exactly the new row;
  * the report names the cost model that priced each symbol, and off-box that is the registry
    baseline, never a fabricated one;
  * a symbol-filtered run is a probe and moves no watermark.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import counterfactual_replay as cr  # noqa: E402

from libs.research import decision_dataset as dd  # noqa: E402

T0 = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)
SYM = "XAUUSD"


def _iso(minutes: float = 0.0) -> str:
    return (T0 + timedelta(minutes=minutes)).isoformat()


@pytest.fixture
def box(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Every path the organ touches, under tmp_path. No real ledger is read or appended."""
    data, reports = tmp_path / "data", tmp_path / "reports"
    (data / "universe").mkdir(parents=True)
    reports.mkdir()
    monkeypatch.setattr(cr, "DESK", tmp_path)
    monkeypatch.setattr(cr, "DATASET", data / "decision_dataset.jsonl")
    monkeypatch.setattr(cr, "WATERMARK", data / "decision_dataset_watermark.json")
    monkeypatch.setattr(cr, "REPORT", reports / "COUNTERFACTUAL_WORLD.json")
    monkeypatch.setattr(cr, "TWIN", reports / "EXECUTION_TWIN.json")
    monkeypatch.setattr(cr, "SURFACE", reports / "FILL_SURFACE.json")
    monkeypatch.setattr(cr, "UNIVERSE", data / "universe" / "universe.json")
    (data / "universe" / "universe.json").write_text(json.dumps({
        SYM: {"contract_size": 100.0, "tick_size": 0.01, "tick_value": 1.0,
              "median_spread_pts": 15.0, "digits": 2}}), "utf-8")

    # The bars the pricer runs on: one tape that triggers the 2000 bracket and prints the
    # 2020 target, handed to the organ through the desk's one bar reader.
    seq = [(1995.0, 1996.0, 1994.0, 1995.0), (1996.0, 1999.5, 1995.5, 1999.0),
           (1999.0, 2002.0, 2000.2, 2001.5)]
    px = 2001.5
    for _ in range(40):
        seq.append((px, px + 2.0, px - 0.5, px + 1.5))
        px += 1.5
    tape = [(T0 + timedelta(hours=i), *row) for i, row in enumerate(seq)]
    monkeypatch.setattr(cr, "_bars_for", lambda symbol, cache: (
        cache.setdefault(symbol, cr.cw.bars_from_rows(tape) if symbol == SYM else [])))

    class Box:
        @staticmethod
        def decisions(rows: list[dict[str, Any]]) -> None:
            p = data / "decision_ledger.jsonl"
            with p.open("a", encoding="utf-8") as fh:
                for r in rows:
                    fh.write(json.dumps(r) + "\n")

        @staticmethod
        def report() -> dict[str, Any]:
            return json.loads(cr.REPORT.read_text("utf-8"))

        @staticmethod
        def dataset() -> list[dict[str, Any]]:
            if not cr.DATASET.exists():
                return []
            return [json.loads(ln) for ln in cr.DATASET.read_text("utf-8").splitlines() if ln]

        @staticmethod
        def watermark() -> dict[str, Any]:
            return json.loads(cr.WATERMARK.read_text("utf-8"))

    return Box()


def _vetoed(minute: float, reason: str = "regime_hibernate") -> dict[str, Any]:
    return {"time": _iso(minute), "sleeve": "gold_break", "symbol": SYM, "side": "buy_stop",
            "lot": 0.1, "price": 2000.0, "sl": 1990.0, "tp": 2020.0, "taken": False,
            "reason": reason, "state_vector_id": "sv1", "release_id": "rel1"}


# ------------------------------------------------------------------ off the box

def test_absent_ledgers_are_unmeasured_and_no_dataset_is_created(box, capsys) -> None:
    d = cr.run()
    assert d["status"] == "UNMEASURED"
    assert "no decision or intent ledger" in d["why"]
    assert d["rows_joined"] == 0 and d["rows_written"] == 0 and d["rows_priced"] == 0
    assert not cr.DATASET.exists() and not cr.WATERMARK.exists()
    # the report IS written: "this host cannot measure it" is a finding, not a missing file
    assert box.report()["status"] == "UNMEASURED"
    assert all(v["status"] == "UNMEASURED" for v in box.report()["alphas"].values())

    assert cr.main([]) == 0
    out = capsys.readouterr().out
    assert "UNMEASURED" in out
    line = next(ln for ln in out.splitlines() if ln.startswith(cr.YIELD_PREFIX))
    assert json.loads(line[len(cr.YIELD_PREFIX):]) == dict.fromkeys(cr.YIELD_KEYS, 0)


# ------------------------------------------------------------------ on the box

def test_a_pass_joins_prices_appends_and_reports(box) -> None:
    box.decisions([_vetoed(i) for i in range(12)])
    d = cr.run()
    assert d["status"] == "MEASURED"
    ds = d["dataset"]
    assert ds["rows_joined"] == ds["rows_written"] == ds["rows_priced"] == 12
    assert ds["schema_version"] == dd.SCHEMA_VERSION

    rows = box.dataset()
    assert len(rows) == 12
    assert all(r["counterfactual_outcomes"]["status"] == "PRICED" for r in rows)
    assert all(r["provenance"]["source"] == "decision_ledger" for r in rows)

    # the five classes are all present, and the two that a skipped-decision box can measure read
    alphas = d["alphas"]
    assert set(cr.cw.ALPHA_CLASSES) <= set(alphas)
    assert alphas["MISSED_TRADE_ALPHA"]["status"] == "MEASURED"
    assert alphas["MISSED_TRADE_ALPHA"]["alpha"] > 0          # a +2R bracket the desk refused
    assert alphas["SIZING_ALPHA"]["status"] == "UNMEASURED"   # nothing was taken, so no size
    assert d["classes_measured"] >= 1
    # every alpha carries its n, and the sign convention is printed with them
    assert "ALTERNATIVE minus the DESK" in d["rule"]
    assert d["headline_by_class"]["MISSED_TRADE_ALPHA"]["n"] == 12

    # the cost model that priced the symbol is named, and off-box it is the registry baseline
    assert d["cost_models"]["resolved"][SYM]["source"] == "costs_baseline"
    assert d["cost_models"]["census"] == {"costs_baseline": 12}
    assert d["top_decisions"] and d["top_decisions"][0]["symbol"] == SYM
    # the join rules travel with the report, so a reader can audit any row's provenance
    assert set(d["join_rules"]) == set(dd.LEDGER_NAMES)

    wm = box.watermark()
    assert wm["ledger_lines"]["decision_ledger"] == 12 and wm["runs"] == 1


def test_a_rerun_over_unchanged_ledgers_appends_nothing(box) -> None:
    box.decisions([_vetoed(i) for i in range(12)])
    first = cr.run()
    before = box.dataset()
    again = cr.run()
    assert again["status"] == "UNCHANGED" and again["rows_written"] == 0
    assert box.dataset() == before
    assert box.watermark()["runs"] == 1

    # and even with the watermark deliberately rewound, the fingerprint guard holds the line
    cr.WATERMARK.unlink()
    third = cr.run()
    assert third["dataset"]["rows_joined"] == 12
    assert third["dataset"]["rows_written"] == 0
    assert box.dataset() == before
    assert first["alphas"]["MISSED_TRADE_ALPHA"]["n"] == \
        third["alphas"]["MISSED_TRADE_ALPHA"]["n"]


def test_a_ledger_that_grows_appends_exactly_the_new_row(box) -> None:
    box.decisions([_vetoed(i) for i in range(12)])
    cr.run()
    box.decisions([_vetoed(99, reason="margin_guard")])
    d = cr.run()
    assert d["dataset"]["rows_joined"] == 1 and d["dataset"]["rows_written"] == 1
    assert len(box.dataset()) == 13
    assert "margin_guard" in d["alphas"]["VETO_ALPHA"]["arms"]
    assert box.watermark()["ledger_lines"]["decision_ledger"] == 13


def test_a_symbol_filtered_run_is_a_probe_and_moves_no_watermark(box) -> None:
    box.decisions([_vetoed(i) for i in range(12)])
    d = cr.run(symbols=["EURUSD"])
    assert d["symbols_filter"] == ["EURUSD"] and d["dataset"]["rows_joined"] == 0
    assert not cr.WATERMARK.exists()
    assert box.report()["symbols_filter"] == ["EURUSD"]


def test_no_write_touches_nothing(box) -> None:
    box.decisions([_vetoed(i) for i in range(12)])
    d = cr.run(write=False)
    assert d["dataset"]["rows_priced"] == 12 and d["dataset"]["rows_written"] == 0
    assert not cr.REPORT.exists() and not cr.DATASET.exists() and not cr.WATERMARK.exists()


def test_main_prints_the_headline_per_class_and_the_yield_line(box, capsys) -> None:
    box.decisions([_vetoed(i) for i in range(12)])
    assert cr.main([]) == 0
    out = capsys.readouterr().out
    for cls in cr.cw.ALPHA_CLASSES:
        assert cls in out
    line = next(ln for ln in out.splitlines() if ln.startswith(cr.YIELD_PREFIX))
    counters = json.loads(line[len(cr.YIELD_PREFIX):])
    assert set(counters) == set(cr.YIELD_KEYS)
    assert counters["rows_priced"] == 12
