"""Every live family with no docket cell gets a measured cause, and first cells where it can.

THE DEFECT THESE PIN (JUDGE_COVERAGE.json, 2026-11-17). Twenty registered families sat in
`unmined_live_families` with `mined: 0` and no reason: no judge could ever reach them, and
nothing said whether that was a missing input, a producer that never enumerates them, or a
pre-screen that forwards nothing.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK.parents[1]), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import zero_cell_families as zcf  # noqa: E402


def _coverage(tmp: Path, doc: dict[str, Any]) -> Path:
    p = tmp / "JUDGE_COVERAGE.json"
    p.write_text(json.dumps(doc), "utf-8")
    return p


def test_the_list_is_the_judges_own_artifact(tmp_path: Path) -> None:
    p = _coverage(tmp_path, {"at": "2026-11-17T13:10:52+00:00",
                             "unmined_live_families": ["sig_path", "ae_latent"]})
    fams, src = zcf.unmined(p)
    assert fams == ["ae_latent", "sig_path"]
    assert src["status"] == "MEASURED" and src["basis"] == "unmined_live_families"


def test_without_the_list_it_reads_mined_zero_rows(tmp_path: Path) -> None:
    p = _coverage(tmp_path, {"families": {"a": {"mined": 0}, "b": {"mined": 3}}})
    fams, src = zcf.unmined(p)
    assert fams == ["a"] and src["basis"].startswith("families")


def test_an_absent_report_is_unmeasured_never_an_empty_verdict(tmp_path: Path) -> None:
    fams, src = zcf.unmined(tmp_path / "missing.json")
    assert fams == [] and src["status"] == zcf.UNMEASURED


def test_learned_families_are_seeded_because_their_prescreen_forwards_none() -> None:
    learned = zcf.learned_family_models()
    assert set(learned) == {"gnn_propagation", "attention_ts", "rocket_ts", "sig_path",
                            "ae_latent"}
    v = zcf.probe("sig_path", learned)
    assert v["cause"] == zcf.PRESCREEN_FORWARDS_NONE and v["action"] == "SEED"


def test_class_carry_without_its_series_is_blocked_input(tmp_path: Path,
                                                         monkeypatch: pytest.MonkeyPatch) -> None:
    from mt5desk import families_cross_sectional as xs
    monkeypatch.setattr(xs, "CARRY_DIR", tmp_path)
    v = zcf.probe("cross_sectional_class_carry", {})
    assert v["cause"] == zcf.BLOCKED_INPUT
    assert "FRED" in v["why"] and v["input_files"] == 0
    (tmp_path / f"{xs.CARRY_SOURCE}_eurusd.parquet").write_bytes(b"x")
    assert zcf.probe("cross_sectional_class_carry", {})["cause"] == \
        zcf.INPUT_PRESENT_PRODUCER_OWES


def test_analyst_families_without_a_store_are_blocked_input(tmp_path: Path,
                                                            monkeypatch: pytest.MonkeyPatch
                                                            ) -> None:
    monkeypatch.setattr(zcf, "BASE", tmp_path)
    for fam in ("analyst_revision_drift", "analyst_cross_market_lead"):
        v = zcf.probe(fam, {})
        assert v["cause"] == zcf.BLOCKED_INPUT and v["input_rows"] == 0
    store = tmp_path / "data" / "alpha_capture" / "analyst_views.jsonl"
    store.parent.mkdir(parents=True)
    store.write_text('{"symbol": "NVIDIA"}\n', "utf-8")
    assert zcf.probe("analyst_revision_drift", {})["cause"] == zcf.INPUT_PRESENT_PRODUCER_OWES


def test_alt_release_without_lake_series_is_blocked_input(tmp_path: Path,
                                                          monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(zcf, "BASE", tmp_path)
    monkeypatch.setattr(zcf, "LAKE", tmp_path / "lake")
    dig = tmp_path / "data" / "digests" / "alt_proxies_equity_handoff.json"
    dig.parent.mkdir(parents=True)
    dig.write_text(json.dumps({"rows": [{"lake_file": "alt_x__y", "usable": True}]}), "utf-8")
    assert zcf.probe("alt_release_drift", {})["cause"] == zcf.BLOCKED_INPUT
    (tmp_path / "lake").mkdir()
    (tmp_path / "lake" / "alt_x__y.csv").write_text("a\n", "utf-8")
    assert zcf.probe("alt_release_drift", {})["cause"] == zcf.INPUT_PRESENT_PRODUCER_OWES


def test_month_end_without_a_bond_proxy_is_blocked_input(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(zcf, "_bars_present", lambda s: s != "UST10Y")
    v = zcf.probe("month_end_rebalance", {})
    assert v["cause"] == zcf.BLOCKED_INPUT and v["input"] == ["UST10Y"]


def test_hunt16_cell_is_an_operator_never_minted_blind() -> None:
    v = zcf.probe("hunt16_cell", {})
    assert v["cause"] == zcf.OPERATOR_NEEDS_BASE and v["action"] == "NONE_HERE"


def test_an_unknown_family_is_named_unmeasured() -> None:
    v = zcf.probe("not_a_family_xyz", {})
    assert v["cause"] == zcf.NO_PROBE and v["action"] == "NONE_HERE"


def test_learned_picks_clear_cost_one_per_symbol_best_first() -> None:
    rows = [
        {"symbol": "A", "clears_cost": True, "t_gross": 1.0, "n_independent": 100,
         "t_deflated_sweep": 0.5},
        {"symbol": "A", "clears_cost": True, "t_gross": 1.2, "n_independent": 100,
         "t_deflated_sweep": 0.9},
        {"symbol": "B", "clears_cost": False, "t_gross": 3.0, "n_independent": 100,
         "t_deflated_sweep": 2.5},
        {"symbol": "C", "clears_cost": True, "t_gross": 1.0, "n_independent": 5,
         "t_deflated_sweep": 1.5},
        {"symbol": "D", "clears_cost": True, "t_gross": 0.8, "n_independent": 80,
         "t_deflated_sweep": 0.1},
    ]
    got = zcf.pick_learned(rows, k=3)
    assert [(r["symbol"], r["t_deflated_sweep"]) for r in got] == [("A", 0.9), ("D", 0.1)]


def test_mass_screen_picks_are_positive_net_and_at_three_times_spread() -> None:
    import numpy as np
    def c(sym: str, p: float, r: float, r3: float, d: int = 1) -> dict[str, Any]:
        start = 100 * (ord(sym) - ord("A"))          # disjoint days: nothing is a duplicate
        return {"grammar": "lead", "symbol": sym, "direction": d, "p": p, "t": 1 / p,
                "mean_r": r, "mean_r_x3": r3, "days": np.arange(start, start + 10)}

    got = zcf.pick_mass_screen([c("A", 1e-4, 0.1, 0.05), c("B", 1e-5, 0.1, -0.01),
                                c("C", 1e-3, -0.1, 0.1), c("D", 2e-4, 0.2, 0.1),
                                {**c("E", 1e-6, 0.1, 0.1), "grammar": "cond"}], k=3)
    assert [x["symbol"] for x in got] == ["A", "D"]


def _run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, dry_run: bool,
         state: dict[str, Any] | None = None) -> tuple[dict[str, Any], list[str], Path]:
    cov = _coverage(tmp_path, {"unmined_live_families": ["fam_seed", "fam_block"]})
    calls: list[str] = []

    def fake_probe(fam: str, learned: Any = None) -> dict[str, Any]:
        if fam == "fam_seed":
            return zcf._verdict(zcf.PRESCREEN_FORWARDS_NONE, "x", action="SEED")
        return zcf._verdict(zcf.BLOCKED_INPUT, "no series")

    def fake_seed(budget_s: float, dry_run: bool) -> dict[str, Any]:
        calls.append("fam_seed")
        return {"status": "DRY_RUN" if dry_run else "DONATED"}

    monkeypatch.setattr(zcf, "probe", fake_probe)
    monkeypatch.setattr(zcf, "learned_family_models", lambda: {})
    monkeypatch.setattr(zcf, "seeders", lambda learned: {"fam_seed": fake_seed})
    sp = tmp_path / "state.json"
    if state is not None:
        sp.write_text(json.dumps(state), "utf-8")
    doc = zcf.run(budget_s=100, dry_run=dry_run, coverage=cov, out=tmp_path / "out.json",
                  state_path=sp)
    return doc, calls, sp


def test_a_dry_run_seeds_nothing_and_writes_no_state(tmp_path: Path,
                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    doc, calls, sp = _run(tmp_path, monkeypatch, dry_run=True)
    assert calls == ["fam_seed"] and not sp.exists()
    assert doc["seeded_this_pass"] == [] and doc["blocked_input"] == {"fam_block": "no series"}
    assert json.loads((tmp_path / "out.json").read_text("utf-8"))["n_unmined"] == 2


def test_a_seeded_family_is_not_seeded_again_inside_the_window(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    doc, calls, sp = _run(tmp_path, monkeypatch, dry_run=False)
    assert doc["seeded_this_pass"] == ["fam_seed"] and "fam_seed" in json.loads(
        sp.read_text("utf-8"))["seeded_at"]
    recent = (datetime.now(tz=UTC) - timedelta(hours=1)).isoformat()
    doc, calls, _ = _run(tmp_path, monkeypatch, dry_run=False,
                         state={"seeded_at": {"fam_seed": recent}})
    assert calls == [] and doc["families"]["fam_seed"]["seed"]["status"] == "SEEDED_RECENTLY"
    old = (datetime.now(tz=UTC) - timedelta(hours=zcf.RESEED_AFTER_H + 1)).isoformat()
    _, calls, _ = _run(tmp_path, monkeypatch, dry_run=False, state={"seeded_at": {"fam_seed": old}})
    assert calls == ["fam_seed"]


def test_reasons_publish_cause_per_family(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _run(tmp_path, monkeypatch, dry_run=True)
    got = zcf.reasons(tmp_path / "out.json")
    assert got["fam_block"]["cause"] == zcf.BLOCKED_INPUT
    assert got["fam_seed"]["action"] == "SEED"
    assert zcf.reasons(tmp_path / "missing.json") == {}


def test_wired_as_an_hourly_leg_with_a_layer() -> None:
    import hourly_cycle as hc

    from libs.research.layers import LEG_LAYER
    assert hc.LEG_BUDGET_SEC["zero_cell_families"] > 600
    assert hc.LEG_DEPARTMENT["zero_cell_families"] == "discovery"
    assert LEG_LAYER["zero_cell_families"] == "prediction"
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '"research/zero_cell_families.py", "--once", "--budget-s", "600"' in src
