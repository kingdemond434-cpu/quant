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
     or the blind seven-day build retry alone;
  4. v1.1 (audit of 9bf6542be): the READMIT_MAX_DAYS backstop fires through `order_docket` and
     the released cell reaches the judge once; readmissions are booked by reason and cause; the
     missing charts join `bars_wanted`; rows are compact; and parking moves no trial charge.
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
    monkeypatch.setattr(jc, "BUILD_INPUT_RELEASED", tmp_path / "build_input_released.json")
    monkeypatch.setattr(jc, "PARKED_TRIAL_ROWS", tmp_path / "build_input_parked_trials.json")
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
    row = named["b"]
    assert row["reason"] == P.REASON == jc.BUILD_INPUT_MISSING
    assert row["missing"] == ["bars:AUDNZD_H1.parquet"]
    assert census["named"] == 2 and census["by_family"] == {"relative_value": 2}
    assert census["top_missing_inputs"] == {"bars:AUDNZD_H1.parquet": 2}


def test_the_reason_is_a_routed_defect_that_stays_in_the_backlog() -> None:
    assert jc.unknown_reason_class(P.REASON) == jc.DEFECT
    assert P.REASON not in jc.NOT_TESTABLE_REASONS
    cls = jc.failure_class(P.REASON)
    assert cls == "input_missing" and jc.FAILURE_ROUTES[cls]["owner"] == "converter"
    got = jc._missing_input(cls, {"sym": "EURGBP", "tf": "H1", "family": "lead_lag",
                                  "missing": ["bars:AUDNZD_H1.parquet"]})
    assert got == {"kind": "inputs", "inputs": ["bars:AUDNZD_H1.parquet"]}


def test_readmission_follows_the_input_not_bar_growth_or_the_build_retry(uni) -> None:
    row = {"reason": P.REASON, "sym": "EURGBP", "family": "lead_lag", "tf": "H1", "days": 0,
           "bar_bytes": 1, "parked_at": (NOW - timedelta(days=30)).isoformat(),
           "missing": ["bars:AUDNZD_H1.parquet"]}
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
    assert len(parked) == 1 and parked[0]["missing"] == ["bars:AUDNZD_H1.parquet"]
    assert doc["build_input_probe"]["named"] == 1
    assert doc["unrunnable_filtered_from_docket"] == 1
    assert doc["totals"]["unjudged_total"] == 3, "parked, still owed: the backlog does not move"
    assert doc["totals"]["judging_failures"]["parked"].get("input_missing") == 1
    # the input appears: the next pass returns the cell to the docket
    _bars().to_parquet(uni / "AUDNZD_H1.parquet")
    out2, doc2 = jc.order_docket([dict(r) for r in rows], publish=False, now=NOW)
    assert len(out2) == 3
    assert not [r for r in jc.unrunnable_bank().values() if r.get("reason") == P.REASON]
    assert doc2["unrunnable"]["readmitted_by_cause"] == {"input_appeared": 1}
    assert doc2["unrunnable"]["readmitted_on_bar_growth"] == 0, "an input is not bar growth"
    assert doc2["build_input_probe"]["readmitted"]["by_cause"] == {"input_appeared": 1}


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


# ------------------------------------------------- 4. v1.1: the audit of 9bf6542be, pinned

def _three_rows() -> list[dict]:
    return [_row("EURGBP", "lead_lag", {"driver_symbol": "AUDNZD"}),
            _row("EURGBP", "lead_lag", {"driver_symbol": "EURUSD"}),
            _row("EURUSD", "carry", {})]


def _age_parked(days: float) -> None:
    bank = json.loads(jc.UNRUNNABLE_BANK.read_text("utf-8"))
    for r in bank.values():
        if r.get("reason") == P.REASON:
            r["parked_at"] = (NOW - timedelta(days=days)).isoformat()
    jc.UNRUNNABLE_BANK.write_text(json.dumps(bank), "utf-8")


def test_the_max_age_backstop_fires_through_order_docket_and_the_judge_gets_one_turn(
        uni, tmp_path) -> None:
    rows = _three_rows()
    out, _ = jc.order_docket([dict(r) for r in rows], publish=False, now=NOW)
    assert len(out) == 2
    _age_parked(100)                                  # parked 100 days ago, input still absent
    out2, doc2 = jc.order_docket([dict(r) for r in rows], publish=False, now=NOW)
    u = doc2["unrunnable"]
    assert u["readmitted_by_reason"].get(P.REASON) == 1, "readmitted 1"
    assert u["readmitted_by_reason_cause"][P.REASON] == {"max_age": 1}
    assert len(out2) == 3, "the released cell goes back to the judge"
    assert doc2["build_input_probe"]["released_max_age"] == 1
    assert doc2["build_input_probe"]["readmitted"] == {
        "total": 1, "by_cause": {"max_age": 1}, "released_max_age": 1}
    assert len(jc.build_input_released()) == 1
    line = json.loads((tmp_path / jc.READMISSION_LOG.name).read_text("utf-8")
                      .splitlines()[-1])
    assert line["all_by_reason"] == {P.REASON: 1} and line["all_by_cause"] == {"max_age": 1}
    assert line["readmitted"] == 0, "not-testable inflow is unchanged: it is a DEFECT class"
    # held until the judge rules: an hour later, and a year later with no ruling, it still ships
    for later in (NOW + timedelta(hours=1), NOW + timedelta(days=400)):
        out3, doc3 = jc.order_docket([dict(r) for r in rows], publish=False, now=later)
        assert len(out3) == 3 and doc3["build_input_probe"]["in_release_grace"] == 1
    assert len(jc.build_input_released()) == 1


def _released_cell() -> str:
    (cell,) = jc.build_input_released()
    return cell


def test_a_stalled_judge_400_day_simulation_keeps_the_released_cell_shipped(uni) -> None:
    """The auditor's simulation (audit of v1.1, MF1): passes every 5 days for 400 days, the input
    never appears, the judge never rules. v1.1 shipped the cell on 28 of 400 days."""
    rows = _three_rows()
    shipped: list[int] = []
    for day in range(0, 401, 5):
        out, _ = jc.order_docket([dict(r) for r in rows], publish=False,
                                 now=NOW + timedelta(days=day))
        if len(out) == 3:
            shipped.append(day)
    assert shipped and shipped[0] == 90, shipped
    assert shipped == list(range(90, 401, 5)), "released once, then shipped until a ruling"
    assert len(jc.build_input_released()) == 1


def test_a_ruling_inside_the_hold_ends_it(uni) -> None:
    rows = _three_rows()
    jc.order_docket([dict(r) for r in rows], publish=False, now=NOW)
    _age_parked(100)
    jc.order_docket([dict(r) for r in rows], publish=False, now=NOW)
    cell = _released_cell()
    # the judge rules: its own build failure, banked a day after the release
    bank = json.loads(jc.UNRUNNABLE_BANK.read_text("utf-8"))
    ruled_at = (NOW + timedelta(days=1)).isoformat(timespec="seconds")
    bank[cell] = {"reason": "build_failed", "sym": "EURGBP", "family": "lead_lag", "tf": "H1",
                  "bar_bytes": 1, "why": "lead_lag driver missing", "parked_at": ruled_at}
    jc.UNRUNNABLE_BANK.write_text(json.dumps(bank), "utf-8")
    out, doc = jc.order_docket([dict(r) for r in rows], publish=False,
                               now=NOW + timedelta(days=2))
    assert doc["build_input_probe"]["release_ended_by_ruling"] == 1
    assert doc["build_input_probe"]["in_release_grace"] == 0
    row = jc.unrunnable_bank()[cell]
    assert row["reason"] == P.REASON and row["parked_at"] == ruled_at, "restated by name"
    assert len(out) == 2 and jc.build_input_released() == {}, "the ruled release is cleared"


def test_a_verdict_inside_the_hold_ends_it(uni, monkeypatch) -> None:
    rows = _three_rows()
    jc.order_docket([dict(r) for r in rows], publish=False, now=NOW)
    _age_parked(100)
    jc.order_docket([dict(r) for r in rows], publish=False, now=NOW)
    cell = _released_cell()
    real = jc.judged_index

    def judged(*a, **k):
        got = real(*a, **k)
        return ({*got[0], cell}, *got[1:])

    monkeypatch.setattr(jc, "judged_index", judged)
    _out, doc = jc.order_docket([dict(r) for r in rows], publish=False,
                                now=NOW + timedelta(days=1))
    assert doc["build_input_probe"]["in_release_grace"] == 0
    assert jc.build_input_released() == {}, "a judged cell's release is cleared"
    assert cell not in jc.unrunnable_bank()


def test_a_failed_release_write_keeps_the_row_parked_on_its_clock(uni, monkeypatch) -> None:
    rows = _three_rows()
    jc.order_docket([dict(r) for r in rows], publish=False, now=NOW)
    _age_parked(100)
    monkeypatch.setattr(jc, "_record_build_input_released", lambda *a, **k: "WRITE_FAILED")
    out, doc = jc.order_docket([dict(r) for r in rows], publish=False, now=NOW)
    u = doc["unrunnable"]
    assert u["build_input_release_write_failed"] == 1 and u["readmitted_total"] == 0
    assert u["build_input_released"] == 0
    parked = [r for r in jc.unrunnable_bank().values() if r.get("reason") == P.REASON]
    assert len(out) == 2 and len(parked) == 1
    assert parked[0]["parked_at"] == (NOW - timedelta(days=100)).isoformat(), "old clock kept"


def test_a_row_younger_than_the_backstop_is_restated_and_keeps_its_clock(uni) -> None:
    rows = _three_rows()
    jc.order_docket([dict(r) for r in rows], publish=False, now=NOW)
    _age_parked(jc.READMIT_MAX_DAYS - 1)
    out, doc = jc.order_docket([dict(r) for r in rows], publish=False, now=NOW)
    assert len(out) == 2 and doc["unrunnable"]["readmitted_total"] == 0
    parked = [r for r in jc.unrunnable_bank().values() if r.get("reason") == P.REASON]
    assert parked[0]["parked_at"] == (NOW - timedelta(days=jc.READMIT_MAX_DAYS - 1)).isoformat()


def test_readmit_cause_names_each_cause(uni) -> None:
    base = {"sym": "EURGBP", "tf": "H1", "family": "carry", "days": 0}
    size = jc._bar_bytes("EURGBP", "H1")
    assert size > 0
    assert jc.readmit_cause({**base, "reason": "build_failed", "bar_bytes": size,
                             "parked_at": (NOW - timedelta(days=8)).isoformat()},
                            now=NOW) == "retry_days"
    assert jc.readmit_cause({**base, "reason": "never_fires", "bar_bytes": size // 2,
                             "parked_at": NOW.isoformat()}, now=NOW) == "bar_growth"
    assert jc.readmit_cause({**base, "reason": "never_fires", "bar_bytes": size,
                             "parked_at": (NOW - timedelta(days=91)).isoformat()},
                            now=NOW) == "max_age"
    assert jc.readmit_cause({**base, "reason": "never_fires", "bar_bytes": size,
                             "parked_at": NOW.isoformat()}, now=NOW) is None


def test_the_missing_charts_join_bars_wanted_and_the_chart_repair_reads_them(
        uni, tmp_path) -> None:
    _out, doc = jc.order_docket([dict(r) for r in _three_rows()], publish=False, now=NOW)
    assert doc["bars_wanted"].get("AUDNZD_H1") == 1
    assert doc["build_input_probe"]["bars_wanted_added"] == 1
    report = tmp_path / "jc_report.json"
    report.write_text(json.dumps({"bars_wanted": doc["bars_wanted"]}), "utf-8")
    from research import hourly_cycle
    assert "AUDNZD" in hourly_cycle.bars_wanted_symbols(report)
    assert P.bar_charts(["bars:AUDNZD_M15.parquet", "surface:X", {"kind": "bars",
                                                                 "file": "USDX_H1.parquet"}]) \
        == ["AUDNZD_M15", "USDX_H1"]


def test_a_parked_row_is_compact(uni) -> None:
    named, _ = P.name([{**_row("EURGBP", "pca_residual",
                               {"factor_symbols": ["USDX", "EURUSD", "UST10Y"]}),
                        "_cell": "x"}], judged=set(), bank={})
    row = named["x"]
    assert set(row) == {"reason", "sym", "family", "tf", "bar_bytes", "missing"}
    assert row["missing"] == ["bars:USDX_H1.parquet", "bars:UST10Y_H1.parquet"]
    assert len(json.dumps(row)) < 180
    # a label and the dict it stands for read the same, and an unknown label fails open
    assert P.present("bars:USDX_H1.parquet") is False
    assert P.present("weird:thing") is True and P.parse_label("nocolon") is None


def test_the_constants_the_two_sides_share_agree() -> None:
    from research import effective_trials as et
    assert P.READMIT_MAX_DAYS == jc.READMIT_MAX_DAYS
    assert et.TRIAL_KEYS == jc.TRIAL_KEYS
    assert et.PARKED_TRIALS_NAME == jc.PARKED_TRIAL_ROWS.name
    assert jc.PARKED_TRIAL_ROWS_MAX == et.MAX_ROWS
    assert jc.PARKED_TRIAL_ROWS.parent == jc.UNRUNNABLE_BANK.parent == et.DOCKET.parent
    assert set(jc.READMIT_CAUSES) >= {"input_appeared", "max_age", "bar_growth"}


def test_trial_keys_are_every_field_the_trial_census_reads() -> None:
    from libs.research.trial_ledger import content_key, grid_key, trial_from_record

    class Seen(dict):
        def __init__(self, *a) -> None:
            super().__init__(*a)
            self.seen: set[str] = set()

        def get(self, k, d=None):
            self.seen.add(k)
            return super().get(k, d)

    rich = {"family": "lead_lag", "symbol": "EURGBP", "timeframe": "M15", "regime": "risk_on",
            "params": {"driver_symbol": "EURUSD", "lag": 3}, "lineage": "L1",
            "claim_selection_trials": 4, "first_seen": "x", "orthogonality": 0.3,
            "source_url": "https://example.invalid", "notes": "long prose " * 20}
    rec = Seen(rich)
    trial_from_record(rec)
    assert rec.seen <= jc.TRIAL_KEYS, rec.seen - jc.TRIAL_KEYS
    trimmed = {k: v for k, v in rich.items() if k in jc.TRIAL_KEYS}
    a, b = trial_from_record(rich), trial_from_record(trimmed)
    assert (grid_key(a), content_key(a), a.group, a.selection_trials) == \
        (grid_key(b), content_key(b), b.group, b.selection_trials)


def test_parking_moves_no_trial_charge(uni, tmp_path, monkeypatch) -> None:
    from research import effective_trials as et
    rows = ([_row("EURUSD", "carry", {"lookback": 20 + i}) for i in range(40)]
            + [_row("EURGBP", "lead_lag", {"driver_symbol": "EURUSD"}),
               _row("EURGBP", "triangle", {"leg_b_symbol": "EURUSD", "leg_c_symbol": "AUDNZD"})])
    probe = jc._build_input_probe
    # A: the docket as it shipped before this probe existed (the probe cannot load)
    monkeypatch.setattr(jc, "_build_input_probe", lambda: None)
    out_a, _ = jc.order_docket([dict(r) for r in rows], publish=False, now=NOW)
    monkeypatch.setattr(jc, "_build_input_probe", probe)
    # B: the probe parks the triangle out of the docket
    out_b, doc_b = jc.order_docket([dict(r) for r in rows], publish=False, now=NOW)
    assert len(out_a) == 42 and len(out_b) == 41
    assert doc_b["build_input_parked_trials"]["rows"] == 1
    (tmp_path / "a").mkdir()
    docket_a = tmp_path / "a" / "external_survivors.json"
    docket_b = tmp_path / "external_survivors.json"          # beside the bank and its sidecar
    docket_a.write_text(json.dumps(out_a), "utf-8")
    docket_b.write_text(json.dumps(out_b), "utf-8")
    rows_a, n_a = et.census_rows(docket_a)
    rows_b, n_b = et.census_rows(docket_b)
    assert (n_a, n_b) == (0, 1)

    def trimmed(rs: list[dict]) -> list[str]:
        return sorted(json.dumps({k: v for k, v in r.items() if k in jc.TRIAL_KEYS},
                                 sort_keys=True, default=str) for r in rs)

    assert trimmed(rows_a) == trimmed(rows_b), "the census reads the same trials"
    charge_a = et.charge(et.measure(rows_a))
    assert et.charge(et.measure(rows_b)) == charge_a, "parking moves no charge"
    # and without the parked rows it WOULD have moved: the test can tell
    assert et.charge(et.measure(et.read_docket(docket_b)))[0] != charge_a[0]


def _parking_pass(uni) -> list[dict]:
    rows = ([_row("EURUSD", "carry", {"lookback": 20 + i}) for i in range(40)]
            + [_row("EURGBP", "lead_lag", {"driver_symbol": "EURUSD"}),
               _row("EURGBP", "triangle", {"leg_b_symbol": "EURUSD", "leg_c_symbol": "AUDNZD"})])
    out, doc = jc.order_docket([dict(r) for r in rows], publish=False, now=NOW)
    assert len(out) == 41 and doc["build_input_parked_trials"]["rows"] == 1
    return rows


@pytest.mark.parametrize("path", ["early_return", "exception"])
def test_the_charge_is_unchanged_across_a_pass_that_ships_unfiltered(uni, tmp_path, monkeypatch,
                                                                     path) -> None:
    """Audit of v1.1, MF2: the early return and the exception path ship the rows unfiltered; a
    parked list left from the pass before counted the parked rows twice (charge 56 -> 49)."""
    from research import effective_trials as et
    rows = _parking_pass(uni)
    sidecar = tmp_path / jc.PARKED_TRIAL_ROWS.name
    assert json.loads(sidecar.read_text("utf-8")), "the parking pass wrote its list"
    if path == "early_return":
        monkeypatch.setattr(jc, "build", lambda *a, **k: {"families": {}})
    else:
        def boom(*a, **k):
            raise RuntimeError("simulated")
        monkeypatch.setattr(jc, "build", boom)
    out, _ = jc.order_docket([dict(r) for r in rows], publish=False, now=NOW)
    assert len(out) == 42, "shipped unfiltered"
    assert json.loads(sidecar.read_text("utf-8")) == [], "rewritten empty on this path"
    docket = tmp_path / "external_survivors.json"
    docket.write_text(json.dumps(out), "utf-8")
    census, n = et.census_rows(docket)
    assert n == 0 and len(census) == 42
    assert et.charge(et.measure(census)) == et.charge(et.measure(rows))


def test_the_census_counts_a_stale_parked_row_once(uni, tmp_path) -> None:
    """Even a list left behind (a crash before the rewrite) never double counts: a parked row the
    docket already holds is matched one-for-one and skipped."""
    from research import effective_trials as et
    rows = _parking_pass(uni)
    sidecar = tmp_path / jc.PARKED_TRIAL_ROWS.name
    stale = json.loads(sidecar.read_text("utf-8"))
    docket = tmp_path / "external_survivors.json"
    docket.write_text(json.dumps(rows), "utf-8")          # the parked row shipped again
    census, n = et.census_rows(docket)
    assert stale and n == 0 and len(census) == len(rows)
    assert et.charge(et.measure(census)) == et.charge(et.measure(rows))


# ------------------------------------------------- 5. v1.3: the audit of v1.2, pinned

def _release_one(rows: list[dict], *, publish: bool = False) -> str:
    jc.order_docket([dict(r) for r in rows], publish=publish, now=NOW)
    _age_parked(100)
    jc.order_docket([dict(r) for r in rows], publish=publish, now=NOW)
    return _released_cell()


@pytest.mark.parametrize("victim", ["bank", "released"])
def test_a_rename_refused_at_commit_recovers_on_the_next_pass(uni, tmp_path, monkeypatch,
                                                              victim) -> None:
    """Audit of v1.2, MF1: the except path wrote the parked list directly over a target named in
    the kept manifest, so every later recovery refused ("changed since the commit point")."""
    monkeypatch.setattr(jc, "_docket_keff", lambda: None)        # keeps every write under tmp
    rows = _three_rows()
    jc.order_docket([dict(r) for r in rows], publish=True, now=NOW)
    if victim == "released":
        _age_parked(100)                                          # this pass writes a release
    target = (jc.UNRUNNABLE_BANK if victim == "bank"
              else tmp_path / jc.BUILD_INPUT_RELEASED.name)
    real = jc._replace_retry

    def refuse(src, dst):
        if Path(dst) == target:
            raise PermissionError("held open by a reader")
        return real(src, dst)

    monkeypatch.setattr(jc, "_replace_retry", refuse)
    out, doc = jc.order_docket([dict(r) for r in rows], publish=True, now=NOW)
    assert doc["verdict"] == "UNMEASURED" and len(out) == 3, "failed pass ships what arrived"
    assert list(tmp_path.glob(f"{jc.TXN_MANIFEST_PREFIX}*")), "the commit point was reached"
    monkeypatch.setattr(jc, "_replace_retry", real)
    _out2, doc2 = jc.order_docket([dict(r) for r in rows], publish=True,
                                  now=NOW + timedelta(hours=1))
    assert doc2.get("verdict") == "COVERED", doc2.get("why")
    assert not list(tmp_path.glob(f"{jc.TXN_MANIFEST_PREFIX}*")), "rolled forward"


@pytest.mark.parametrize("publish", [False, True])
def test_a_fault_after_the_filter_ships_the_rows_as_they_arrived(uni, tmp_path, monkeypatch,
                                                                 publish) -> None:
    """Audit of v1.2, MF2: a fault after the filter returned the FILTERED rows and emptied the
    parked list, so the parked trials were counted nowhere (charge 56 -> 37)."""
    from research import effective_trials as et
    monkeypatch.setattr(jc, "_docket_keff", lambda: None)
    rows = ([_row("EURUSD", "carry", {"lookback": 20 + i}) for i in range(40)]
            + [_row("EURGBP", "lead_lag", {"driver_symbol": "EURUSD"}),
               _row("EURGBP", "triangle", {"leg_b_symbol": "EURUSD", "leg_c_symbol": "AUDNZD"})])
    out0, _ = jc.order_docket([dict(r) for r in rows], publish=publish, now=NOW)
    assert len(out0) == 41

    def boom(*a, **k):
        raise RuntimeError("fireability fault")

    monkeypatch.setattr(jc, "fireability_order", boom)
    out, doc = jc.order_docket([dict(r) for r in rows], publish=publish, now=NOW)
    assert doc["verdict"] == "UNMEASURED" and len(out) == 42, "unfiltered, as they arrived"
    assert not any(k.startswith("_") for r in out for k in r), "no private keys ship"
    docket = tmp_path / "external_survivors.json"
    docket.write_text(json.dumps(out), "utf-8")
    census, n = et.census_rows(docket)
    assert n == 0 and len(census) == 42
    assert et.charge(et.measure(census)) == et.charge(et.measure(rows))


def test_unmeasured_docket_membership_never_drops_a_hold(uni, monkeypatch) -> None:
    """Audit of v1.2: a row with no id made membership UNMEASURED, read as "left the docket"."""
    rows = _three_rows()
    cell = _release_one(rows)
    f = jc.UNRUNNABLE_BANK.parent / jc.BUILD_INPUT_RELEASED.name
    old = (NOW - timedelta(days=95)).isoformat(timespec="seconds")
    f.write_text(json.dumps({"schema": 2, "cells": {cell: old}}), "utf-8")
    seen: list = []
    real_update = jc.update_unrunnable_bank

    def spy(*a, **k):
        seen.append(k.get("docket_cells"))
        return real_update(*a, **k)

    real_fn = jc._cell_id_fn

    def fn_raising_on_carry():
        inner = real_fn()

        def fn(row):
            if row.get("family") == "carry":
                raise ValueError("no identity")
            return inner(row)
        return fn

    monkeypatch.setattr(jc, "update_unrunnable_bank", spy)
    monkeypatch.setattr(jc, "_cell_id_fn", fn_raising_on_carry)
    out, _ = jc.order_docket([dict(r) for r in rows if r["family"] != "lead_lag"
                              or r["params"]["driver_symbol"] != "AUDNZD"],
                             publish=False, now=NOW + timedelta(days=1))
    assert seen == [None], "membership UNMEASURED is passed as None"
    assert jc.build_input_released() == {cell: old}, "the hold stands"
    # measured membership without the cell does drop a 95-day-old release (the file's bound)
    assert jc._record_build_input_released({}, at=NOW.isoformat(), path=f, txn=None,
                                           bank={}, docket_cells=set()) == "WRITTEN"
    assert jc.build_input_released() == {}


def test_a_torn_release_file_is_set_aside_and_read_unmeasured(uni, tmp_path) -> None:
    rows = _three_rows()
    _release_one(rows)
    f = tmp_path / jc.BUILD_INPUT_RELEASED.name
    f.write_text('{"cells": {"tor', "utf-8")
    assert jc.build_input_released() is None
    out, doc = jc.order_docket([dict(r) for r in rows], publish=False,
                               now=NOW + timedelta(days=1))
    assert len(out) == 3, "the held cell is not re-parked on a fresh clock"
    # both never-parked lead_lag rows: which of them is held is unknown, so neither is named
    assert doc["build_input_probe"]["release_file_unmeasured"] == 2
    aside = list(tmp_path.glob(jc.BUILD_INPUT_RELEASED.name + ".torn-*"))
    assert len(aside) == 1 and aside[0].read_text("utf-8") == '{"cells": {"tor', "kept whole"
    assert not f.exists(), "never overwritten"
    # it stays UNMEASURED until resolved by hand, and a release meanwhile stays parked
    assert jc.build_input_released() is None
    jc.order_docket([dict(r) for r in rows], publish=False, now=NOW + timedelta(days=2))
    assert jc.build_input_released() is None and not f.exists()


def test_a_release_is_kept_parked_while_the_release_file_is_unmeasured(uni, tmp_path) -> None:
    rows = _three_rows()
    jc.order_docket([dict(r) for r in rows], publish=False, now=NOW)
    _age_parked(100)
    (tmp_path / jc.BUILD_INPUT_RELEASED.name).write_text("{torn", "utf-8")
    out, doc = jc.order_docket([dict(r) for r in rows], publish=False, now=NOW)
    u = doc["unrunnable"]
    assert u["build_input_released_state"] == "UNMEASURED"
    assert u["build_input_release_write_failed"] == 1 and u["readmitted_total"] == 0
    assert len(out) == 2, "parked on its old clock until the file is resolved"
