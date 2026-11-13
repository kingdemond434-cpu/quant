"""THE CONVERSION HANDOFF HAS A READER -- every parked cell leaves a pass with one booked outcome.

The load-bearing pins:
  * `test_build_bug_*` -- each builder bug the consumer repairs is REPRODUCED through the judge's
    own call shape (`fire_days` = resolve + strip + modifiers + family call) and shown fixed;
  * `test_coevolution_grammar_names_are_family_names` -- every grammar op the producer emits now
    lands on keywords the family accepts;
  * `test_pass_books_balance_and_charge_children` -- in == re_emitted + fixed + deferred +
    abandoned per reason, and every child is donated with tests_run = children (never hidden);
  * `test_judge_readmits_on_a_request_only_after_parking` -- the other end of the requeue file;
  * `test_leg_is_wired` -- an hourly leg with a cap and a layer.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "desks" / "mt5"
for p in (str(ROOT), str(BASE), str(BASE / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)

import conversion_handoff_consumer as chc  # noqa: E402
import grammar_param_names as gpn  # noqa: E402


def _bars(n: int = 24 * 400, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    close = 1.1 + np.cumsum(rng.normal(0, 0.002, n))
    hi = close + np.abs(rng.normal(0, 0.002, n))
    lo = close - np.abs(rng.normal(0, 0.002, n))
    op = np.r_[close[0], close[:-1]]
    return pd.DataFrame({"open": op, "high": np.maximum(hi, op), "low": np.minimum(lo, op),
                         "close": close, "tick_volume": rng.integers(50, 500, n),
                         "spread": 10, "real_volume": 0}, index=idx.rename("time"))


# ------------------------------------------------------------------------------ build bugs
def test_build_bug_coevolution_window_name_reproduced_and_fixed() -> None:
    bars = _bars()
    raw = {"representation": "external_engine", "w": 48}
    n, why = chc.fire_days("range_reversion", "EURUSD", bars, raw)
    assert n is None and why == "raised TypeError"          # the judge's build raises the same
    verdict, fixed, _ = chc.repair(
        "range_reversion", raw, "range_reversion raised TypeError: family_range_reversion() got "
        "an unexpected keyword argument 'w'")
    assert verdict == "FIXED" and fixed == {"representation": "external_engine", "range_n": 48}
    n, why = chc.fire_days("range_reversion", "EURUSD", bars, fixed)
    assert why == "ok" and n is not None


def test_build_bug_lower_turnover_label_reproduced_and_fixed() -> None:
    bars = _bars()
    raw = {"lower_turnover": True}
    assert chc.fire_days("overnight_gap_decay", "EURUSD", bars, raw) == (None, "raised TypeError")
    verdict, fixed, _ = chc.repair("overnight_gap_decay", {"timeframe": "H4", **raw},
                                   "overnight_gap_decay raised TypeError: family_overnight_gap_"
                                   "decay() got an unexpected keyword argument 'lower_turnover'")
    assert verdict == "FIXED" and fixed == {"timeframe": "H4"}
    assert chc.fire_days("overnight_gap_decay", "EURUSD", bars, {})[1] == "ok"


def test_build_bug_narrative_only_params_are_abandoned_by_name() -> None:
    verdict, fixed, why = chc.repair(
        "carry", {"mechanism_genome": {"actor": "x"}, "crossed_slot": "trigger"},
        "carry raised TypeError: family_carry() got an unexpected keyword argument "
        "'mechanism_genome'")
    assert verdict == "ABANDONED" and fixed is None and "parent cell" in why


def test_build_bug_string_side_is_mapped() -> None:
    verdict, fixed, _ = chc.repair("dav_range_filter_adx", {"side": "SHORT", "timeframe": "D1"},
                                   "dav_range_filter_adx raised TypeError: '>' not supported "
                                   "between instances of 'str' and 'int'")
    assert verdict == "FIXED" and fixed == {"side": -1, "timeframe": "D1"}


def test_unrepaired_signature_is_no_repair() -> None:
    assert chc.repair("lead_lag", {}, "lead_lag driver missing: no H1 bars for X")[0] == \
        "NO_REPAIR"


def test_coevolution_grammar_names_are_family_names() -> None:
    import inspect

    from research.sandboxes import coevolution_cell as cc

    from libs.research import family_firing as ff
    assert cc.FAMILY_OF_OP == gpn.FAMILY_OF_OP
    for op, keys in cc.GRAMMAR:
        fam = cc.FAMILY_OF_OP[op]
        sample = {k: v[-1] for k, v in keys.items()}
        if fam == gpn.VOL_RATIO_FAMILY:
            sample = {"w1": 24, "w2": 96}
        out, _ = gpn.translate(fam, sample)
        assert out is not None, op
        accepted = set(inspect.signature(ff.family_fn(fam)).parameters)
        assert set(out) <= accepted, (op, out)
    assert gpn.translate("vol_mean_reversion", {"w1": 12, "w2": 96})[0] is None


def test_signatures_aggregate_across_symbols() -> None:
    a = chc.build_signature("x raised ValueError: bad window 48 for 'EURUSD'")
    b = chc.build_signature("x raised ValueError: bad window 96 for 'GBPJPY'")
    assert a == b


# ------------------------------------------------------------------------------ stream + depth
def test_iter_handoff_streams_in_small_chunks(tmp_path: Path) -> None:
    rows = [{"cell": f"C{i}", "reason": "never_fires", "why": "x" * 50} for i in range(500)]
    p = tmp_path / "h.json"
    p.write_text(json.dumps({"schema_version": 2, "generated_utc": "t", "n": 500, "rows": rows},
                            indent=1), "utf-8")
    got = list(chc.iter_handoff(p, chunk_chars=97))
    assert [r["cell"] for r in got] == [r["cell"] for r in rows]
    assert chc.handoff_header(p)["n"] == 500


def test_depth_need_is_the_judges_rule_in_days() -> None:
    assert chc.depth_factor(0) == 1.25 and chc.depth_factor(30) == 2.0
    assert chc.depth_factor(5) == 3.0 and chc.depth_factor(59) == 1.25
    snaps = [["2026-11-01T00:00:00+00:00", 100], ["2026-11-05T00:00:00+00:00", 120]]
    assert chc.baseline_for(snaps, "2026-11-03T00:00:00+00:00") == 100
    assert chc.baseline_for(snaps, "2026-11-06T00:00:00+00:00") == 120


def test_memory_bounds_are_derived() -> None:
    assert chc.workers_for(None) == 1
    assert chc.workers_for(64 * 2**30, cpus=18) == 17
    assert chc.workers_for(1 * 2**30, cpus=4) == 1
    assert chc.parents_cap(None) == chc.PARENTS_FLOOR
    assert chc.parents_cap(32 * 2**30) > chc.parents_cap(1 * 2**30)


# ------------------------------------------------------------------------------ one pass
@pytest.fixture
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    from research.frontier_identity import docket_cell_id

    from libs.research import family_firing as ff
    uni = tmp_path / "universe"
    uni.mkdir()
    _bars().to_parquet(uni / "EURUSD_H1.parquet")
    monkeypatch.setattr(ff, "UNIVERSE", uni)
    monkeypatch.setattr(chc, "UNIVERSE", uni)
    docket_rows = [
        {"symbol": "EURUSD", "family": "range_reversion", "params": {"w": 48}},
        {"symbol": "EURUSD", "family": "range_reversion", "params": {"range_n": 20}},
        {"symbol": "EURUSD", "family": "range_reversion",
         "params": {"threshold_pct": 5.0, "session": "asia"}},
    ]
    (tmp_path / "docket.json").write_text(json.dumps(docket_rows), "utf-8")
    ids = [docket_cell_id(r) for r in docket_rows]
    handoff = {"schema_version": 2, "generated_utc": "2026-11-13T00:00:00+00:00", "n": 5, "rows": [
        {"cell": ids[0], "family": "range_reversion", "symbol": "EURUSD", "timeframe": "H1",
         "reason": "build_failed", "class": "build_fail",
         "why": "range_reversion raised TypeError: family_range_reversion() got an unexpected "
                "keyword argument 'w'", "first_parked_utc": "2026-11-01T00:00:00+00:00"},
        {"cell": ids[1], "family": "range_reversion", "symbol": "EURUSD", "timeframe": "H1",
         "reason": "never_fires", "class": "untestable_as_specified",
         "first_parked_utc": "2026-11-01T00:00:00+00:00", "days": 0},
        {"cell": ids[2], "family": "range_reversion", "symbol": "EURUSD", "timeframe": "H1",
         "reason": "too_rare", "class": "untestable_as_specified",
         "first_parked_utc": "2026-11-01T00:00:00+00:00", "days": 4},
        {"cell": "EURUSD.carry.p=x", "family": "carry", "symbol": "EURUSD", "timeframe": "H1",
         "reason": "short_history_after_cut", "class": "short_history",
         "first_parked_utc": "2026-11-01T00:00:00+00:00", "days": 30},
        {"cell": "EURUSD.cot.p=y", "family": "cot_positioning", "symbol": "EURUSD",
         "reason": "build_input_missing", "class": "input_missing"},
    ]}
    (tmp_path / "handoff.json").write_text(json.dumps(handoff, indent=1), "utf-8")
    donated: list[tuple[list[dict[str, Any]], int]] = []

    def fake_donate(rows: list[dict[str, Any]], *, dry_run: bool) -> dict[str, Any]:
        donated.append((rows, len(rows)))
        return {"donated": len(rows), "tests_run": len(rows)}
    monkeypatch.setattr(chc, "donate", fake_donate)
    kw = {"handoff": tmp_path / "handoff.json", "docket": tmp_path / "docket.json",
          "out": tmp_path / "out.json", "state_path": tmp_path / "state.json",
          "requeue_path": tmp_path / "req.json", "depth_path": tmp_path / "depth.json",
          "workers": 1, "budget_s": 120.0}
    return {"kw": kw, "ids": ids, "donated": donated, "tmp": tmp_path}


def test_pass_books_balance_and_charge_children(desk: dict[str, Any]) -> None:
    doc = chc.run(**desk["kw"])
    assert doc["status"] == "MEASURED"
    for reason, b in doc["books"].items():
        assert b["balanced"], reason
    assert doc["totals"]["in"] == 5
    assert doc["books"]["build_failed"]["fixed"] == 1
    assert doc["books"]["build_input_missing"]["deferred"] == 1
    assert doc["books"]["short_history_after_cut"]["deferred"] == 1
    rows, charged = desk["donated"][0]
    assert charged == len(rows) == doc["children_emitted"] == doc["trials"]["charged"]
    assert all(r["parent_cell"] and r["trial_family"] == r["family"] for r in rows)
    repaired = [r for r in rows if r["parent_cell"] == desk["ids"][0]]
    assert repaired and repaired[0]["params"] == {"range_n": 48}
    assert (desk["tmp"] / "req.json").exists() and (desk["tmp"] / "depth.json").exists()
    # A second pass never re-emits the repaired parent and the cursor has wrapped once.
    again = chc.run(**desk["kw"])
    assert again["books"]["build_failed"]["by_why"]["fixed"] == {
        "repaired_child_already_emitted": 1}


def test_requeued_fires_now_is_never_looped(desk: dict[str, Any]) -> None:
    doc = chc.run(**desk["kw"])
    req = json.loads((desk["tmp"] / "req.json").read_text("utf-8"))["requests"]
    fired = [c for c, r in req.items() if r.get("cause") == "fires_now"]
    assert fired == [desk["ids"][1]]
    st = json.loads((desk["tmp"] / "state.json").read_text("utf-8"))
    assert set(fired) <= set(st["fires_now_requeued"])
    st["cursor"] = -1
    (desk["tmp"] / "state.json").write_text(json.dumps(st), "utf-8")
    again = chc.run(**desk["kw"])
    whys = again["books"]["never_fires"]["by_why"].get("deferred", {})
    assert doc and "probe_disagrees_with_judge:requeued_before" in whys


def test_absent_handoff_is_unmeasured(tmp_path: Path) -> None:
    doc = chc.run(handoff=tmp_path / "none.json", out=tmp_path / "o.json", budget_s=5)
    assert doc["status"] == chc.UNMEASURED


# ------------------------------------------------------------------------------ the judge's end
def test_judge_readmits_on_a_request_only_after_parking() -> None:
    import judge_coverage as jc
    row = {"reason": "short_history_after_cut", "parked_at": "2026-11-01T00:00:00+00:00"}
    assert jc.requeue_due(row, {"at": "2026-11-02T00:00:00+00:00"})
    assert not jc.requeue_due(row, {"at": "2026-10-30T00:00:00+00:00"})
    assert not jc.requeue_due({**row, "reason": "needs_data"}, {"at": "2026-11-02T00:00:00Z"})
    assert "consumer_requeue" in jc.READMIT_CAUSES
    assert jc.CONSUMER_REQUEUE.name == chc.REQUEUE.name


def test_bank_update_reads_the_requeue_file(tmp_path: Path) -> None:
    import judge_coverage as jc
    bank = tmp_path / "unrunnable_specs.json"
    bank.write_text(json.dumps({"A.carry.p=1": {"reason": "never_fires", "sym": "ZZZ", "tf": "H1",
                                                "days": 0, "bar_bytes": 10,
                                                "parked_at": "2026-11-01T00:00:00+00:00"}}),
                    "utf-8")
    (tmp_path / jc.CONSUMER_REQUEUE.name).write_text(json.dumps(
        {"requests": {"A.carry.p=1": {"at": "2026-11-02T00:00:00+00:00", "cause": "fires_now"}}}),
        "utf-8")
    out = jc.update_unrunnable_bank({}, at="2026-11-03T00:00:00+00:00", path=bank)
    assert out["readmitted_by_cause"] == {"consumer_requeue": 1}
    assert json.loads(bank.read_text("utf-8")) == {}


def test_handoff_rows_carry_days_and_bytes(tmp_path: Path) -> None:
    import judge_coverage as jc
    out = tmp_path / "h.json"
    bank = {"A.x.p=1": {"reason": "short_history_after_cut", "sym": "A", "tf": "H1", "days": 30,
                        "bar_bytes": 99, "parked_at": "t"}}
    assert jc.write_conversion_handoff(bank, at="t", path=out) == 1
    row = json.loads(out.read_text("utf-8"))["rows"][0]
    assert row["days"] == 30 and row["bar_bytes"] == 99
    assert chc.lane_of(row) == "depth"


# ------------------------------------------------------------------------------ wiring
def test_leg_is_wired() -> None:
    from libs.research.layers import LEG_LAYER
    assert LEG_LAYER["conversion_handoff_consumer"] == "prediction"
    src = (BASE / "research" / "hourly_cycle.py").read_text(encoding="utf-8")
    assert '_costed("conversion_handoff_consumer"' in src
    assert '"conversion_handoff_consumer": 540' in src
    assert "depth_symbols()" in src


def test_depth_symbols_feed_bars_wanted(tmp_path: Path) -> None:
    p = tmp_path / "d.json"
    p.write_text(json.dumps({"charts": {
        "XAUUSD_M5": {"cells_waiting": 9, "extendable": True},
        "EURUSD_H1": {"cells_waiting": 50, "extendable": False},
        "GBPJPY_M15": {"cells_waiting": 3, "extendable": True}}}), "utf-8")
    assert chc.depth_symbols(p) == ["XAUUSD", "GBPJPY"]


def test_burndown_reads_the_consumer_report(tmp_path: Path) -> None:
    import judging_burndown as jb
    assert jb.consumer_outflow(tmp_path / "none.json")["status"] == chc.UNMEASURED
    p = tmp_path / jb.CONSUMER_REPORT
    p.write_text(json.dumps({"status": "MEASURED", "generated_utc": "t", "children_emitted": 3,
                             "totals": {"in": 9, "re_emitted": 2, "fixed": 1, "deferred": 5,
                                        "abandoned": 1}}), "utf-8")
    got = jb.consumer_outflow(p)
    assert got["status"] == "MEASURED" and got["in"] == 9 and got["children_emitted"] == 3
    assert chc.OUT.name == jb.CONSUMER_REPORT
