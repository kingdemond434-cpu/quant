"""Every legless triangle row in the docket gets its legs, by the compiler's rule, in place,
idempotently, never deleting a row, and the docket's own writer applies it every pass."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import discovery_compiler as dc  # noqa: E402
from research import merge_hypotheses as mh  # noqa: E402
from research import transformation_miners as TM  # noqa: E402
from research import triangle_leg_backfill as tlb  # noqa: E402

META = {s: {"asset_class": "Forex"} for s in ("EURUSD", "USDJPY", "EURJPY", "GBPUSD")}
META["XAUUSD"] = {"asset_class": "Metals"}


def _ctx(bars: bool = True) -> TM.Context:
    return TM.Context(instruments={"fx": ["EURUSD", "USDJPY", "EURJPY", "GBPUSD"],
                                   "metals": ["XAUUSD"]},
                      bars_available=lambda _s, _c: bars, lane_ok=lambda _s: True)


def _row(sym: str, **params) -> dict:
    return {"symbol": sym, "family": "triangle", "params": dict(params), "producer": "p"}


def test_legless_rows_are_filled_in_place_by_the_compilers_rule() -> None:
    rows = [_row("EURJPY"), _row("XAUUSD"), {"symbol": "EURUSD", "family": "trend", "params": {}}]
    rep = tlb.backfill(rows, identity=mh._identity, ctx=_ctx(), meta=META,
                       now=datetime(2026, 9, 30, tzinfo=UTC))
    assert len(rows) == 3, "a backfill never deletes a row"
    want = dc.complete_inputs({"symbol": "EURJPY", "family": "triangle", "params": {},
                               "chart": "H1"}, _ctx(), META)["params"]
    p = rows[0]["params"]
    assert {k: p[k] for k in want} == want and p["leg_b_symbol"] and p["leg_c_symbol"]
    assert {p["leg_b_symbol"], p["leg_c_symbol"]} == {"EURUSD", "USDJPY"}
    assert rows[0]["legs_backfill"]["status"] == "FILLED"
    assert rows[0]["legs_backfill"]["params_before"] == {}
    assert rows[1]["legs_backfill"] == {"status": "UNFILLED", "why": "not_an_fx_pair",
                                        "chart": "H1", "at": "2026-09-30T00:00:00+00:00",
                                        "by": "triangle_leg_backfill"}
    assert "legs_backfill" not in rows[2]
    assert (rep["legless_before"], rep["filled"], rep["unfilled"], rep["legless_after"]) == \
        (2, 1, 1, 1)
    assert rep["unfilled_by_reason"] == {"not_an_fx_pair": 1}


def test_a_second_pass_changes_nothing() -> None:
    rows = [_row("EURJPY"), _row("XAUUSD")]
    tlb.backfill(rows, identity=mh._identity, ctx=_ctx(), meta=META)
    snap = json.dumps(rows, sort_keys=True)
    rep = tlb.backfill(rows, identity=mh._identity, ctx=_ctx(), meta=META,
                       now=datetime(2027, 1, 1, tzinfo=UTC))
    assert json.dumps(rows, sort_keys=True) == snap, "an unchanged docket is left unchanged"
    assert rep["filled"] == 0 and rep["changed_records"] == 0 and rep["legless_before"] == 1


def test_no_bars_on_the_chart_is_named_and_the_row_kept() -> None:
    rows = [_row("EURJPY", timeframe="M30")]
    rep = tlb.backfill(rows, identity=mh._identity, ctx=_ctx(bars=False), meta=META)
    assert rows[0]["params"] == {"timeframe": "M30"}
    assert rows[0]["legs_backfill"]["why"] == "no_hypothesis_lane_bars_on_M30"
    assert rep["unfilled"] == 1


def test_a_fill_never_duplicates_a_row_already_in_the_docket() -> None:
    filled = _row("EURJPY")
    tlb.backfill([filled], identity=mh._identity, ctx=_ctx(), meta=META)
    rows = [filled, _row("EURJPY")]
    rep = tlb.backfill(rows, identity=mh._identity, ctx=_ctx(), meta=META)
    assert len(rows) == 2 and rows[1]["params"] == {}
    assert rows[1]["legs_backfill"]["why"] == "filled_spec_already_in_docket"
    assert rep["filled"] == 0


def test_the_docket_writer_backfills_banked_rows_every_pass(monkeypatch, tmp_path) -> None:
    hyp = tmp_path / "hypotheses"
    hyp.mkdir()
    target = hyp / "external_survivors.json"
    target.write_text(json.dumps([_row("EURJPY"), _row("XAUUSD")]), "utf-8")
    monkeypatch.setattr(mh, "HYP", hyp)
    monkeypatch.setattr(mh, "TARGET", target)
    monkeypatch.setattr(dc, "build_context", lambda **_k: _ctx())
    monkeypatch.setattr(dc, "_universe_meta", lambda: META)
    monkeypatch.setattr(mh, "tradeable_universe", lambda: {})
    assert mh.main() == 0
    rows = json.loads(target.read_text("utf-8"))
    assert len(rows) == 2
    by = {r["symbol"]: r for r in rows}
    assert by["EURJPY"]["params"]["leg_b_symbol"]
    assert by["XAUUSD"]["legs_backfill"]["why"] == "not_an_fx_pair"
    report = json.loads((hyp / "merge_report.json").read_text("utf-8"))
    assert report["triangle_legs"]["filled"] == 1, report["triangle_legs"]
    assert json.loads((hyp / tlb.OUT.name).read_text("utf-8"))["status"] == "APPLIED"
    # hourly: the merge_docket leg runs the docket's only writer, which runs the backfill
    cycle = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '"merge_hypotheses", "research/merge_hypotheses.py"' in cycle
