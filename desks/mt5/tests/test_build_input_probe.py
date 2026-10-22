"""A cell whose build must fail for want of a named input is parked by name, and comes back.

    python -m pytest desks/mt5/tests/test_build_input_probe.py -q

`research/build_input_probe.py` names, before the docket ships, the never-judged cells whose
`external_gauntlet.build_cell` refuses because an input it loads by name is absent on this host.
These tests pin:
  1. EXACTNESS against the sealed builder: on the same files, every MISSING answer is a cell the
     sealed `build_cell` refuses for that input, and the input appearing turns the answer PRESENT;
  2. anything the probe cannot prove is UNMEASURED and never named (fail open toward judging);
  3. judge_coverage parks such a cell out of the docket, keeps it in the backlog and in the
     bank with its inputs, and re-admits it the pass the input appears -- never on bar growth
     or the blind seven-day build retry alone.
"""
from __future__ import annotations

import json
import sys
from collections import OrderedDict
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK / "scripts"), str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import external_gauntlet as G  # noqa: E402
from mt5desk import data as cot_data  # noqa: E402

from research import build_input_probe as P  # noqa: E402
from research import judge_coverage as jc  # noqa: E402
from research import orthogonal_sweep as inputs  # noqa: E402

NOW = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)
#: the symbols the tmp registry knows; each gets an H1 parquet unless a test removes it
REGISTRY = ("EURGBP", "EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "EURCZK")


def _bars(n: int = 600) -> pd.DataFrame:
    rng = np.random.default_rng(11)
    idx = pd.date_range("2025-01-01", periods=n, freq="h", tz="UTC")
    close = 1.2 + np.cumsum(rng.normal(0, 0.001, n))
    return pd.DataFrame({"open": close, "high": close + 0.001, "low": close - 0.001,
                         "close": close, "tick_volume": 10, "spread": 1}, index=idx)


@pytest.fixture
def uni(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """One tmp bar store read by BOTH the judge's own-chart loader and the input loader."""
    root = tmp_path / "universe"
    root.mkdir()
    for sym in REGISTRY:
        _bars().to_parquet(root / f"{sym}_H1.parquet")
    _bars().to_parquet(root / "EURGBP_M15.parquet")       # one intraday own chart
    (root / "universe.json").write_text(json.dumps(
        {s: {"point": 0.0001, "spread_median_pts": 10} for s in REGISTRY}), "utf-8")
    monkeypatch.setattr(G, "UNI", root)
    monkeypatch.setattr(inputs, "UNIVERSE", root)
    monkeypatch.setattr(G, "_FRAME_CACHE", OrderedDict())
    monkeypatch.setattr(inputs, "_BAR_CACHE", OrderedDict())
    monkeypatch.setattr(inputs, "_surfaces", lambda: {"EURGBP": {"spread": [1.0]}})
    cot_dir = tmp_path / "cot"
    cot_dir.mkdir()
    monkeypatch.setattr(cot_data, "_COT", cot_dir)
    # bank, ratchet, report and priors are desk state: kept under tmp (audit of PR #290)
    from libs.research import research_priors
    monkeypatch.setattr(jc, "UNRUNNABLE_BANK", tmp_path / "unrunnable_specs.json")
    monkeypatch.setattr(jc, "RATCHET", tmp_path / "judge_backlog_ratchet.json")
    monkeypatch.setattr(jc, "REPORT", tmp_path / "JUDGE_COVERAGE.json")
    monkeypatch.setattr(jc, "CONVERSION_HANDOFF", tmp_path / "conversion_handoff.json")
    monkeypatch.setattr(research_priors, "STATE_DIR", tmp_path / "research_priors")
    return root


def _row(sym: str, family: str, params: dict) -> dict:
    return {"symbol": sym, "family": family, "params": params,
            "first_seen": (NOW - timedelta(hours=3)).isoformat()}


#: (docket row, the missing input's label, the substring the sealed builder's refusal names)
MISSING_CASES = [
    (_row("EURGBP", "relative_value", {"peer_symbol": "AUDNZD"}),
     "bars:AUDNZD_H1.parquet", "no H1 bars for peer AUDNZD"),
    (_row("EURGBP", "correlation_regime", {"peer_symbol": "AUDNZD", "timeframe": "M15"}),
     "bars:AUDNZD_M15.parquet", "no M15 bars for peer AUDNZD"),
    (_row("EURGBP", "cross_asset_residual", {"factor_symbols": ["EURUSD", "UST10Y"]}),
     "bars:UST10Y_H1.parquet", "factor basket incomplete: no H1 bars for UST10Y"),
    (_row("EURGBP", "pca_residual", {"factor_symbols": ["USDX", "EURUSD", "UST10Y"]}),
     "bars:USDX_H1.parquet", "factor basket incomplete: no H1 bars for USDX, UST10Y"),
    (_row("EURGBP", "triangle", {"leg_b_symbol": "EURUSD", "leg_c_symbol": "AUDNZD"}),
     "bars:AUDNZD_H1.parquet", "triangle leg missing: no H1 bars for AUDNZD"),
    (_row("EURGBP", "lead_lag", {"driver_symbol": "AUDNZD"}),
     "bars:AUDNZD_H1.parquet", "lead_lag driver missing: no H1 bars for AUDNZD"),
    (_row("GBPUSD", "execution_state", {}),
     "surface:GBPUSD", "execution_state: no microstructure surface for GBPUSD"),
    (_row("EURGBP", "usd_session_shock", {"fx": "AUDNZD"}),
     "bars:AUDNZD_H1.parquet", "insufficient H1 FX driver bars for AUDNZD"),
    (_row("EURCZK", "cot_net_fade", {}),
     "cot_mapping:EURCZK", "raw COT for EURCZK: KeyError"),
    (_row("EURUSD", "cot_change_fade", {}),
     "cot_file:eur.parquet", "raw COT for EURUSD"),
]


@pytest.mark.parametrize("row,lab,refusal", MISSING_CASES,
                         ids=[c[0]["family"] for c in MISSING_CASES])
def test_every_missing_answer_is_a_refusal_of_the_sealed_builder(uni, row, lab,
                                                                  refusal) -> None:
    ctx = P._Pass()
    got = P.probe_row(ctx, row)
    assert got["status"] == P.MISSING, got
    assert lab in [P.label(i) for i in got["missing"]]
    cell = ctx.docket_cell(row)
    assert G.build_cell(cell["sym"], cell["family"], cell["params"], {}) is None
    assert refusal in str(G.LAST_BUILD_FAILURE), G.LAST_BUILD_FAILURE


@pytest.mark.parametrize("row,lab,refusal", MISSING_CASES,
                         ids=[c[0]["family"] for c in MISSING_CASES])
def test_the_input_appearing_turns_the_answer_present(uni, monkeypatch, row, lab,
                                                       refusal) -> None:
    ctx0 = P._Pass()
    first = P.probe_row(ctx0, row)
    assert first["status"] == P.MISSING
    for item in first["missing"]:
        assert P.present(item, P._Pass()) is False
        kind = item["kind"]
        if kind == "bars":
            _bars().to_parquet(uni / item["file"])
        elif kind == "surface":
            monkeypatch.setattr(inputs, "_surfaces",
                                lambda s=item["symbol"]: {"EURGBP": {"x": 1}, s: {"x": 1}})
        elif kind == "cot_mapping":
            monkeypatch.setitem(cot_data._SYMBOL_SLUG, item["symbol"], "czk")
        elif kind == "cot_file":
            (cot_data._COT / item["file"]).write_bytes(b"x")
    ctx = P._Pass()
    assert all(P.present(i, ctx) for i in first["missing"])
    again = P.probe_row(ctx, row)
    if again["status"] == P.MISSING:          # a raw-COT mapping can now point at a file
        assert all(i["kind"] == "cot_file" for i in again["missing"])
    else:
        assert again["status"] == P.PRESENT, again


# --------------------------------------------------------------- 2. fail open toward judging

@pytest.mark.parametrize("row,why", [
    (_row("EURGBP", "carry", {}), "family not probed"),
    (_row("EURGBP", "relative_value", {}), "cannot settle"),               # preflight's case
    (_row("EURGBP", "triangle", {"leg_b_symbol": "EURUSD"}), "cannot settle"),
    (_row("NOTREG", "relative_value", {"peer_symbol": "AUDNZD"}), "gate 0"),
    (_row("EURGBP", "relative_value", {"peer_symbol": "AUDNZD", "timeframe": "M5"}), "gate 0"),
    ({**_row("EURGBP", "lead_lag", {"driver_symbol": "AUDNZD"}),
      "mechanism_status": "STATISTICAL_ONLY"}, "gate 0"),
    (_row("EURGBP", "lead_lag", {"driver_symbol": "AUDNZD", "regime": "risk_on"}),
     "preflight conserves"),
])
def test_what_the_probe_cannot_prove_is_unmeasured(uni, row, why) -> None:
    got = P.probe_row(P._Pass(), row)
    assert got["status"] == P.UNMEASURED and why in got["why"], got


def test_an_absent_own_h1_file_is_unmeasured_never_named(uni) -> None:
    (uni / "EURGBP_H1.parquet").unlink()           # the judge may still reach the terminal
    got = P.probe_row(P._Pass(), _row("EURGBP", "relative_value", {"peer_symbol": "AUDNZD"}))
    assert got["status"] == P.UNMEASURED


def test_an_empty_surface_map_is_unmeasured_not_every_symbol_missing(uni, monkeypatch) -> None:
    monkeypatch.setattr(inputs, "_surfaces", lambda: {})
    ctx = P._Pass()
    assert P.probe_row(ctx, _row("GBPUSD", "execution_state", {}))["status"] == P.UNMEASURED
    assert P.present({"kind": "surface", "symbol": "GBPUSD"}, ctx) is True


def test_an_unreadable_registry_names_nothing(uni) -> None:
    (uni / "universe.json").write_text("{torn", "utf-8")
    named, census = P.name([{**_row("EURGBP", "lead_lag", {"driver_symbol": "AUDNZD"}),
                             "_cell": "c1"}], judged=set(), bank={})
    assert named == {} and census["unmeasured"] == 1


# ------------------------------------------------------------- 3. naming, parking, readmitting

def test_name_skips_judged_rows_and_the_judges_own_reasons(uni) -> None:
    rv = {"peer_symbol": "AUDNZD"}
    rows = [{**_row("EURGBP", "relative_value", rv), "_cell": c} for c in ("a", "b", "c", "d")]
    bank = {"c": {"reason": "never_fires"},
            "d": {"reason": "build_failed", "why": "no H1 bars for peer AUDNZD"}}
    named, census = P.name(rows, judged={"a"}, bank=bank)
    assert set(named) == {"b", "d"}
    assert named["d"]["judge_why"] == "no H1 bars for peer AUDNZD"
    row = named["b"]
    assert row["reason"] == P.REASON == jc.BUILD_INPUT_MISSING
    assert row["missing"] == [{"kind": "bars", "symbol": "AUDNZD", "timeframe": "H1",
                               "file": "AUDNZD_H1.parquet"}]
    assert census["named"] == 2 and census["by_family"] == {"relative_value": 2}
    assert census["top_missing_inputs"] == {"bars:AUDNZD_H1.parquet": 2}


def test_the_reason_is_a_routed_defect_that_stays_in_the_backlog() -> None:
    assert jc.unknown_reason_class(P.REASON) == jc.DEFECT
    assert P.REASON not in jc.NOT_TESTABLE_REASONS
    cls = jc.failure_class(P.REASON)
    assert cls == "input_missing" and jc.FAILURE_ROUTES[cls]["owner"] == "converter"
    got = jc._missing_input(cls, {"sym": "EURGBP", "tf": "H1", "family": "lead_lag",
                                  "missing": [{"kind": "bars", "file": "AUDNZD_H1.parquet"}]})
    assert got["inputs"] == [{"kind": "bars", "file": "AUDNZD_H1.parquet"}]


def test_readmission_follows_the_input_not_bar_growth_or_the_build_retry(uni) -> None:
    row = {"reason": P.REASON, "sym": "EURGBP", "family": "lead_lag", "tf": "H1", "days": 0,
           "bar_bytes": 1, "parked_at": (NOW - timedelta(days=30)).isoformat(),
           "missing": [{"kind": "bars", "symbol": "AUDNZD", "timeframe": "H1",
                        "file": "AUDNZD_H1.parquet"}]}
    # bars grew enormously and 30 days passed: neither is the cause, so it stays parked
    assert jc.readmit_due(row, now=NOW) is False
    old = {**row, "parked_at": (NOW - timedelta(days=jc.READMIT_MAX_DAYS)).isoformat()}
    assert jc.readmit_due(old, now=NOW) is True
    _bars().to_parquet(uni / "AUDNZD_H1.parquet")
    assert jc.readmit_due(row, now=NOW) is True


def test_order_docket_parks_the_cell_keeps_it_owed_and_readmits_it(uni) -> None:
    rows = [_row("EURGBP", "lead_lag", {"driver_symbol": "AUDNZD"}),
            _row("EURGBP", "lead_lag", {"driver_symbol": "EURUSD"}),
            _row("EURUSD", "carry", {})]
    out, doc = jc.order_docket([dict(r) for r in rows], publish=False, now=NOW)
    assert {r["params"].get("driver_symbol") for r in out if r["family"] == "lead_lag"} == \
        {"EURUSD"}, "the unbuildable cell leaves the docket"
    assert len(out) == 2
    bank = jc.unrunnable_bank()
    parked = [r for r in bank.values() if r.get("reason") == P.REASON]
    assert len(parked) == 1 and parked[0]["missing_input"] == "bars:AUDNZD_H1.parquet"
    assert doc["build_input_probe"]["named"] == 1
    assert doc["unrunnable_filtered_from_docket"] == 1
    assert doc["totals"]["unjudged_total"] == 3, "parked, still owed: the backlog does not move"
    assert doc["totals"]["judging_failures"]["parked"].get("input_missing") == 1
    # the input appears: the next pass returns the cell to the docket
    _bars().to_parquet(uni / "AUDNZD_H1.parquet")
    out2, doc2 = jc.order_docket([dict(r) for r in rows], publish=False, now=NOW)
    assert len(out2) == 3
    assert not [r for r in jc.unrunnable_bank().values() if r.get("reason") == P.REASON]
    assert doc2["unrunnable"]["readmitted_on_bar_growth"] == 1


def test_a_probe_that_cannot_load_names_nothing_and_says_so(uni, monkeypatch) -> None:
    monkeypatch.setattr(jc, "_build_input_probe", lambda: None)
    named, census = jc.probe_build_inputs([{"family": "lead_lag", "_cell": "x"}], set(), {},
                                          frozenset())
    assert named == {} and census["status"] == "UNMEASURED"
    row = {"reason": P.REASON, "missing": [{"kind": "bars", "file": "NOPE_H1.parquet"}]}
    assert jc.readmit_due(row, now=NOW) is True, "fail open toward judging"


def test_the_census_reads_the_docket_and_writes_nothing(uni, tmp_path) -> None:
    docket = tmp_path / "docket.json"
    docket.write_text(json.dumps([_row("EURGBP", "lead_lag", {"driver_symbol": "AUDNZD"}),
                                  _row("EURUSD", "carry", {})]), "utf-8")
    before = sorted(p.name for p in tmp_path.rglob("*"))
    out = P.census(docket, echo=False)
    assert out["named"] == 1 and out["docket_rows"] == 2
    assert out["by_missing_kind"] == {"bars": 1}
    assert sorted(p.name for p in tmp_path.rglob("*")) == before, "the census is read-only"
