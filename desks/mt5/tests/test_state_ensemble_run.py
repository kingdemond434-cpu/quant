"""The state-ensemble organ: what it publishes, what it refuses to claim, and how it counts trials.

Pinned:
  * the state artifact is stamped, carries calibration against the PLAIN base rate, and a symbol
    whose newest day has not moved is carried, not refitted;
  * `promotion.admits` needs all three measured wins -- an absent contract is UNMEASURED, never a
    pass, and nothing here is authority;
  * the allocation conditioning keeps the incumbent's rails (floor 0.08, cap 0.60);
  * NEAR-MISS TRIALS ARE CHARGED ONCE, NEVER INFLATED: a first screen is charged whether or not
    anything survives (donation file OR null-pass ledger, never both), a re-screen costs nothing;
  * the regime-split miner's null pass is now charged where the census reads it;
  * the `regime_split(labeler="ensemble")` cell the gauntlet re-executes partitions its base;
  * the leg is wired: hourly call, department, layer, budget and experiment contract.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import proposer_common as pc  # noqa: E402
import regime_split_miner as rsm  # noqa: E402
import state_ensemble_run as ser  # noqa: E402
from mt5desk import families_orthogonal as fo  # noqa: E402

from libs.regime import control_room as cr  # noqa: E402
from libs.regime import ensemble as E  # noqa: E402

NO_GARCH = tuple(e for e in E.ENGINES if e != "garch")


def _h1(days: int = 720, seed: int = 4) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    vol = np.repeat(np.where(np.arange(days) // 40 % 2, 0.003, 0.0008), 24)
    idx = pd.date_range("2022-01-03", periods=days * 24, freq="h", tz="UTC")
    c = np.exp(np.cumsum(rng.normal(scale=vol))) * 100
    o = np.concatenate([[c[0]], c[:-1]])
    df = pd.DataFrame({"open": o, "high": np.maximum(o, c) * 1.0004,
                       "low": np.minimum(o, c) * 0.9996, "close": c,
                       "spread": np.full(idx.size, 2.0), "tick_volume": np.full(idx.size, 100)},
                      index=idx)
    df.index.name = "time"
    return df


@pytest.fixture()
def sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    uni = tmp_path / "universe"
    uni.mkdir()
    _h1(days=1000).to_parquet(uni / "XAUTST_H1.parquet")
    monkeypatch.setattr(cr, "bar_path", lambda s, dirs=(uni,): (uni / f"{s}_H1.parquet")
                        if (uni / f"{s}_H1.parquet").exists() else None)
    monkeypatch.setattr(cr, "BAR_DIRS", (uni,))
    for name in ("OUT", "CONTRACT", "NEARMISS", "CACHE", "CHARGED", "NULL_TRIALS",
                 "GATES_EXTERNAL", "GATE_LEDGER"):
        monkeypatch.setattr(ser, name, tmp_path / getattr(ser, name).name)
    monkeypatch.setattr(E, "available_engines", lambda: NO_GARCH)
    return tmp_path


def test_state_artifact_is_stamped_scored_and_carried(sandbox: Path) -> None:
    doc = ser.run_state(symbols=["XAUTST", "NOPE"])
    on_disk = json.loads((sandbox / "STATE_ENSEMBLE.json").read_text("utf-8"))
    assert on_disk["schema"] == ser.SCHEMA and on_disk["generated_at"]
    row = doc["symbols"]["XAUTST"]
    assert row["status"] == "MEASURED"
    assert row["now"]["vol"] in ("low", "mid", "high")
    assert set(row["calibration"]) >= {"fused", "climatology"}
    assert row["fused_vs_plain"]["status"] == "MEASURED"
    assert doc["symbols"]["NOPE"]["status"] == "UNMEASURED"
    assert doc["calibration_vs_plain"]["status"] == "MEASURED"
    assert doc["memory"]["total_mb"] > 0
    assert doc["engines_unavailable"] == ["garch"]
    # An absent contract is UNMEASURED and admits nothing.
    assert doc["promotion"]["allocation_contract"] == "UNMEASURED"
    assert doc["promotion"]["admits"] is False
    again = ser.run_state(symbols=["XAUTST"])
    assert again["refit_this_pass"] == 0 and again["carried_unchanged_day"] == 1
    assert again["calibration_vs_plain"]["n_days"] == doc["calibration_vs_plain"]["n_days"]


def test_memory_stand_down_is_unmeasured(sandbox: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ser, "memory", lambda: {"total_mb": 100.0, "available_mb": 10.0})
    doc = ser.run_state(symbols=["XAUTST"])
    assert doc["stood_down"]["status"] == "UNMEASURED"
    assert doc["skipped"]["XAUTST"] == "stood down for memory"
    nm = ser.run_nearmiss()
    assert nm["status"] == "UNMEASURED" and nm["stood_down"] is True


def test_promotion_needs_all_three_wins() -> None:
    win = {"verdict": "WIN"}
    desk = {"verdict": "WIN", "admits": True, "design": {"universe": "desk"}}
    assert ser.promotion(win, win, desk)["admits"] is True
    assert ser.promotion(win, {}, desk)["admits"] is False
    assert ser.promotion(win, win, {"verdict": "WIN", "admits": False})["admits"] is False
    assert ser.promotion({"verdict": "INCONCLUSIVE"}, win, desk)["admits"] is False
    assert "pf_allocator.regime_state" in ser.promotion(win, win, desk)["wiring"]


def test_conditioning_keeps_the_incumbent_rails() -> None:
    days = pd.bdate_range("2020-01-01", periods=900).strftime("%Y-%m-%d")
    rng = np.random.default_rng(2)
    vol = np.repeat(np.where(np.arange(30) % 2, 0.02, 0.005), 30)
    gold = pd.Series(100 * np.exp(np.cumsum(rng.normal(scale=vol))), index=days)
    lab = E.label_days(pd.DataFrame({"close": gold}), NO_GARCH)
    train = list(lab.index[-300:])
    got = ser.ensemble_conditioning(gold, train, 21, lab)
    assert got is not None
    labels, probs = got
    assert len(labels) == len(train)
    p = dict(probs)
    assert abs(sum(p.values()) - 1.0) < 1e-9
    assert min(p.values()) >= ser.REGIME_MIN_SHARE - 1e-9
    assert max(p.values()) <= ser.REGIME_MAX_SHARE + 1e-9
    assert ser.ensemble_conditioning(gold, list(lab.index[:200]), 21, lab) is None


def _near(cands: list[dict[str, Any]]) -> Any:
    return lambda note: [dict(c) for c in cands]


def test_near_miss_trials_charged_once_never_inflated(sandbox: Path,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    d = _h1(days=520)
    monkeypatch.setattr(pc, "bars", lambda s: d)
    monkeypatch.setattr(pc, "cost_frac", lambda s, m, c: 1e-5)
    monkeypatch.setattr(pc, "universe_meta", lambda: {})
    monkeypatch.setattr(pc, "artifact_hours", lambda df: {})
    donated: list[tuple[int, int]] = []

    def fake_donate(source: str, cands: list[dict], tests_run: int, *a: Any, **k: Any) -> Path:
        donated.append((len(cands), tests_run))
        return sandbox / "donation.json"

    monkeypatch.setattr(pc, "donate", fake_donate)
    monkeypatch.setattr(ser, "near_misses", _near([
        {"sym": "XAUTST", "family": "drawdown_conditional", "params": {},
         "params_basis": "family defaults", "cell": "XAUTST.drawdown_conditional.p=x",
         "near": {"near_basis": "dsr within 20%", "ratio": 0.9}, "rank": 0.9},
        {"sym": "XAUTST", "family": "regime_split", "params": {}, "params_basis": "",
         "cell": "c", "near": {}, "rank": 0.8}]))
    first = ser.run_nearmiss()
    assert first["refused"]                       # a regime_split base is never re-nested
    n = first["tests_run"]
    assert first["cells_newly_charged"] == n == first["lifetime_union_cells"]
    null_lines = (sandbox / "null_pass_trials.jsonl").read_text("utf-8").splitlines() \
        if (sandbox / "null_pass_trials.jsonl").exists() else []
    charged_null = sum(json.loads(x)["tests_run"] for x in null_lines)
    charged_don = sum(t for _, t in donated)
    # ONE OR THE OTHER, NEVER BOTH, AND EXACTLY THE NEW CELLS.
    assert charged_null + charged_don == n
    assert not (null_lines and donated)
    again = ser.run_nearmiss()
    assert again["cells_newly_charged"] == 0
    assert again["lifetime_union_cells"] == n
    lines2 = (sandbox / "null_pass_trials.jsonl").read_text("utf-8").splitlines() \
        if (sandbox / "null_pass_trials.jsonl").exists() else []
    assert sum(json.loads(x)["tests_run"] for x in lines2) + sum(t for _, t in donated) == n
    for r in again["all"]:
        assert r["n_tests_sweep"] >= n           # every row pays for the whole union
        assert r["params"]["labeler"] == "ensemble"


def test_regime_split_null_pass_is_charged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    uni = tmp_path / "uni"
    uni.mkdir()
    (uni / "XTST_H1.parquet").write_bytes(b"")
    # The miner holds `research.proposer_common`, a different module object from the top-level
    # import above, so its own reference is the one patched.
    monkeypatch.setattr(rsm.pc, "UNI", uni)
    monkeypatch.setattr(rsm.pc, "universe_meta", lambda: {})
    for name in ("CHARGED", "TRIALS", "NULL_TRIALS", "REPORT"):
        monkeypatch.setattr(rsm, name, tmp_path / getattr(rsm, name).name)
    row = {"cell": "XTST.regime_split.a.low_trend", "symbol": "XTST", "t_gross": 0.4,
           "clears_cost": False, "n_independent": 3, "params": {},
           "walk_forward": {"passed": False, "measured": 0}}
    monkeypatch.setattr(rsm, "sweep_symbol", lambda s, m, dl: ([dict(row)], None))
    rep = rsm.run(["XTST"], budget_s=60)
    assert rep["null_pass_charged"] == 1
    lines = (tmp_path / "null_pass_trials.jsonl").read_text("utf-8").splitlines()
    assert [json.loads(x)["tests_run"] for x in lines] == [1]
    rsm.run(["XTST"], budget_s=60)                 # re-screen of a charged cell: no new charge
    assert len((tmp_path / "null_pass_trials.jsonl").read_text("utf-8").splitlines()) == 1


def test_ensemble_labeler_cell_partitions_its_base(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(E, "available_engines", lambda: NO_GARCH)
    d = _h1(days=520)
    every = fo.family_regime_split(d, base_family="drawdown_conditional", labeler="ensemble")
    parts = [fo.family_regime_split(d, base_family="drawdown_conditional", vol=v,
                                    labeler="ensemble") for v in ser.VOLS]
    base = {s.time for s in fo.ORTHOGONAL_FAMILIES["drawdown_conditional"](d)}
    assert {s.time for s in every} <= base
    assert sum(len(p) for p in parts) == len(every)
    assert fo.family_regime_split(d, base_family="drawdown_conditional", labeler="bogus") == []
    # The default is unchanged: the control room, exactly as every existing cell was minted.
    assert [s.time for s in fo.family_regime_split(d, base_family="drawdown_conditional")] == \
        [s.time for s in fo.family_regime_split(d, base_family="drawdown_conditional",
                                                labeler="")]


def test_leg_is_wired_end_to_end() -> None:
    src = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_costed("state_ensemble"' in src
    assert '"research/state_ensemble_run.py"' in src
    assert '"state_ensemble": sen' in src
    import hourly_cycle as hc
    assert hc.LEG_BUDGET_SEC["state_ensemble"] >= (ser.STATE_BUDGET_S + ser.CONTRACT_BUDGET_S
                                                  + ser.NEARMISS_BUDGET_S)
    from libs.research import layers
    assert layers.LEG_LAYER["state_ensemble"] == "prediction"
    contracts = json.loads((_ROOT / "docs" / "research" / "experiment_contracts.json")
                           .read_text("utf-8"))
    c = contracts["legs"]["state_ensemble"]
    assert c["metric"]["organ"] == "report:STATE_ENSEMBLE.json"
    from libs.tiers.experiment_contract import problems, resolve
    full = resolve("state_ensemble", c, budget_s=hc.LEG_BUDGET_SEC["state_ensemble"],
                   department=hc.LEG_DEPARTMENT["state_ensemble"])
    assert hc.LEG_DEPARTMENT["state_ensemble"] == "forward"
    assert problems(full) == []
