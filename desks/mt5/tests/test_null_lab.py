"""THE NULL LAB: each family's own pipeline on data where no edge can exist, and the price it pays.

    python -m pytest desks/mt5/tests/test_null_lab.py -q

WHAT MUST NOT REGRESS:

  1. each null destroys what it claims and keeps what it claims (block shuffle keeps the bars'
     own moves and timestamps; the walk keeps the volatility; sign permutation keeps the timing
     and mirrors the bracket)
  2. the gate statistics are the gauntlet's own, at the gauntlet's own bar
  3. on pure noise the deflated-Sharpe gate passes near its nominal 5% (the lab is calibrated)
  4. a family whose null passes above nominal is NAMED and CHARGED; one at nominal is not
  5. the online FDR charge multiplies that family's p (and only that family's), can only
     tighten, and turns an affordable certificate into an over-budget one
  6. the organ runs a budgeted pass through a gauntlet stand-in, appends every draw, records a
     draw that could not run as NOT_RUN with its reason, and publishes the report
  7. it is wired: an hourly leg before tier_s, a department, a layer, a budget
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for p in (str(ROOT), str(DESK / "research"), str(DESK)):
    if p not in sys.path:
        sys.path.insert(0, p)

import null_lab as organ  # noqa: E402

from libs.research import null_lab as nl  # noqa: E402
from libs.tiers import online_fdr  # noqa: E402


def _bars(n: int = 3000, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    c = 1.1 * np.exp(np.cumsum(rng.normal(0, 0.001, n)))
    o = np.concatenate([[1.1], c[:-1]])
    h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 0.0005, n)))
    lo = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 0.0005, n)))
    return pd.DataFrame({"open": o, "high": h, "low": lo, "close": c,
                         "tick_volume": rng.integers(1, 100, n)}, index=idx)


# ------------------------------------------------------------------------------ 1. the nulls
def test_block_shuffle_keeps_the_moves_and_the_clock() -> None:
    df = _bars()
    out = nl.block_shuffle(df, np.random.default_rng(3))
    assert out.index.equals(df.index)
    # a permutation of the same close-to-close moves ends where the original ended
    assert out["close"].iloc[-1] == pytest.approx(df["close"].iloc[-1], rel=1e-9)
    assert not np.allclose(out["close"].to_numpy(), df["close"].to_numpy())
    assert (out["high"] >= out[["open", "close"]].max(axis=1) - 1e-12).all()
    assert (out["low"] <= out[["open", "close"]].min(axis=1) + 1e-12).all()
    # the per-bar moves are the same multiset
    a = np.sort(np.diff(np.log(df["close"].to_numpy())))
    b = np.sort(np.diff(np.log(out["close"].to_numpy())))
    assert np.abs(a - b).max() < 0.01


def test_random_walk_matches_volatility() -> None:
    df = _bars()
    out = nl.random_walk(df, np.random.default_rng(4))
    s0 = np.std(np.diff(np.log(df["close"].to_numpy())))
    s1 = np.std(np.diff(np.log(out["close"].to_numpy())))
    assert s1 == pytest.approx(s0, rel=0.1)
    assert out.index.equals(df.index)
    assert (out["high"] >= out[["open", "close"]].max(axis=1)).all()


def test_sign_permute_flips_half_and_mirrors_the_bracket() -> None:
    from mt5desk.engine import Signal
    df = _bars(400)
    sigs = [Signal(time=df.index[i], side=1, stop=float(df["close"].iloc[i]) - 0.01,
                   target=float(df["close"].iloc[i]) + 0.02, ttl_bars=5, tag="t")
            for i in range(10, 390, 2)]
    out = nl.sign_permute(sigs, df, np.random.default_rng(5))
    flipped = [(a, b) for a, b in zip(sigs, out, strict=True) if b.side != a.side]
    assert 0.3 * len(sigs) < len(flipped) < 0.7 * len(sigs)
    for a, b in flipped:
        ref = float(df["close"].loc[a.time])
        assert b.stop - ref == pytest.approx(ref - a.stop)
        assert b.target - ref == pytest.approx(ref - a.target)
        assert b.time == a.time


# ------------------------------------------------------------------------------ 2-3. gates
def test_dsr_bar_is_the_gauntlets() -> None:
    src = (DESK / "scripts" / "external_gauntlet.py").read_text("utf-8")
    m = re.search(r"^DSR_THRESHOLD = ([0-9.]+)", src, re.M)
    assert m and float(m.group(1)) == nl.DSR_THRESHOLD


def test_noise_passes_near_nominal() -> None:
    rng = np.random.default_rng(7)
    passes = n = 0
    for _ in range(400):
        daily = rng.normal(0, 1, 250)
        st = nl.gate_stats(list(rng.normal(0, 1, 50)), list(daily))
        g = st["deflated_sharpe_1trial"]
        n += 1
        passes += bool(g["passed"])
    assert 0.02 < passes / n < 0.09


def test_unjudgeable_draw_is_unmeasured_not_a_fail() -> None:
    st = nl.gate_stats([0.1] * 5, [0.1] * 10)
    assert st["deflated_sharpe_1trial"]["passed"] is None
    assert st["screen_t"]["passed"] is None


# ------------------------------------------------------------------------------ 4. the charge
def _draws(family: str, k: int, n: int) -> list[dict[str, Any]]:
    out = []
    for i in range(n):
        ok = i < k
        out.append({"family": family, "arm": nl.ARMS[i % 3], "status": "RUN",
                    "stats": {"deflated_sharpe_1trial": {"stat": 0.97 if ok else 0.4,
                                                         "passed": ok},
                              "screen_t": {"stat": 2.5 if ok else 0.1, "passed": ok},
                              "in_sample_screen": {"stat": 0.1, "passed": True}}})
    return out


def test_easy_family_is_named_and_charged_nominal_family_is_not() -> None:
    fams = nl.summarise(_draws("easy", 30, 100) + _draws("fair", 5, 100)
                        + [{"family": "broken", "arm": "random_walk", "status": "NOT_RUN",
                            "why": "no bars"}])
    assert fams["easy"]["gates"][nl.CHARGED_GATE]["exceeds_nominal"] is True
    assert fams["easy"]["fpr_charge"] > 4.0
    assert fams["fair"]["gates"][nl.CHARGED_GATE]["exceeds_nominal"] is False
    assert fams["fair"]["fpr_charge"] == 1.0
    assert fams["broken"]["status"] == nl.UNMEASURED
    assert fams["broken"]["fpr_charge"] is None
    ch = nl.charges({"families": fams})
    assert set(ch) == {"easy"}


def test_few_draws_are_not_repriced_on_luck() -> None:
    assert nl.charge(1, 2, 0.05) < 1.6          # 1 of 2 is 50%, but the prior holds it near 5%
    assert nl.charge(0, 0, 0.05) == 1.0


# ------------------------------------------------------------------------------ 5. online FDR
def test_fdr_charge_multiplies_only_the_named_family() -> None:
    tests = [online_fdr.Test("a", "2026-01-01", p=0.01, family="easy", certified=True),
             online_fdr.Test("b", "2026-01-02", p=0.01, family="fair", certified=True),
             online_fdr.Test("c", "2026-01-03", p=0.4, family="easy"),
             online_fdr.Test("d", "2026-01-04", e=40.0, family="easy")]
    out, rec = online_fdr.charge_null_fpr(tests, {"easy": 3.0})
    by = {t.test_id: t for t in out}
    assert by["a"].p == pytest.approx(0.03)
    assert by["b"].p == pytest.approx(0.01)
    assert by["c"].p == 1.0
    assert by["d"].e == pytest.approx(40.0 / 3.0)
    assert rec["tests_charged"] == 3 and rec["families_charged"] == {"easy": 3}
    # never loosens: a charge at or below 1 changes nothing
    same, rec0 = online_fdr.charge_null_fpr(tests, {"easy": 0.5, "fair": 1.0})
    assert same == tests and rec0["tests_charged"] == 0


def test_the_charge_can_put_a_certificate_over_budget() -> None:
    tests = [online_fdr.Test(f"f{i}", f"2026-01-{i + 1:02d}", p=1.0, family="x")
             for i in range(5)]
    tests.append(online_fdr.Test("cert", "2026-01-10", p=0.0004, family="easy",
                                 certified=True))
    before = online_fdr.replay(tests)
    charged, _ = online_fdr.charge_null_fpr(tests, {"easy": 50.0})
    after = online_fdr.replay(charged)
    assert before["over_budget"] == 0
    assert after["over_budget"] == 1


def test_tier_s_online_fdr_reads_the_null_lab() -> None:
    src = (DESK / "research" / "tier_s.py").read_text("utf-8")
    body = src[src.index("def organ_online_fdr"):src.index("def _sleeve_descriptors")]
    assert "NULL_LAB.json" in body and "charge_null_fpr" in body
    assert body.index("charge_null_fpr") < body.index("online_fdr.replay(tests)")


# ------------------------------------------------------------------------------ 6. the organ
def _stub_gauntlet(fail_family: str) -> SimpleNamespace:
    from mt5desk.engine import Costs, Signal

    def build_cell(sym: str, family: str, params: dict, meta: dict,
                   h1_override: pd.DataFrame | None = None) -> dict[str, Any] | None:
        if family == fail_family:
            stub.LAST_BUILD_FAILURE = "input load failed: stub"
            return None
        df = h1_override
        assert df is not None
        sigs = [Signal(time=df.index[i], side=1, stop=float(df["close"].iloc[i]) * 0.998,
                       target=float(df["close"].iloc[i]) * 1.003, ttl_bars=6, tag="s")
                for i in range(30, len(df) - 10, 24)]
        return {"df": df, "sigs": sigs, "costs": Costs()}

    stub = SimpleNamespace(build_cell=build_cell, LAST_BUILD_FAILURE=None,
                           timeframe_of=lambda params, family="": "H1")
    return stub


def test_organ_runs_a_budgeted_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    uni = tmp_path / "universe"
    uni.mkdir()
    _bars(4000).to_parquet(uni / "EURUSD_H1.parquet")
    (uni / "universe.json").write_text(json.dumps({"EURUSD": {"contract_size": 100000}}),
                                       "utf-8")
    docket = tmp_path / "external_survivors.json"
    docket.write_text(json.dumps([
        {"symbol": "EURUSD", "family": "good_fam", "params": {"a": 1}},
        {"symbol": "EURUSD", "family": "bad_fam", "params": {}},
        {"symbol": "GBPUSD", "family": "nochart_fam", "params": {}}]), "utf-8")
    monkeypatch.setattr(organ, "UNI", uni)
    monkeypatch.setattr(organ, "DOCKET", docket)
    monkeypatch.setattr(organ, "REPORT", tmp_path / "NULL_LAB.json")
    monkeypatch.setitem(sys.modules, "external_gauntlet", _stub_gauntlet("bad_fam"))
    ledger = tmp_path / "draws.jsonl"
    doc = organ.run(60.0, ledger_path=ledger)
    assert doc["status"] == "MEASURED"
    rows = [json.loads(x) for x in ledger.read_text("utf-8").splitlines()]
    assert len(rows) == doc["draws_this_pass"] >= 9           # 3 families x 3 arms at least
    assert {r["arm"] for r in rows} == set(nl.ARMS)
    bad = [r for r in rows if r["family"] == "bad_fam"]
    assert bad and all(r["status"] == "NOT_RUN" and "stub" in r["why"] for r in bad)
    nochart = [r for r in rows if r["family"] == "nochart_fam"]
    assert nochart and all(r["status"] == "NOT_RUN" for r in nochart)
    good = [r for r in rows if r["family"] == "good_fam"]
    assert good and all(r["status"] == "RUN" for r in good)
    assert set(doc["unmeasured_families"]) >= {"bad_fam", "nochart_fam"}
    rep = json.loads((tmp_path / "NULL_LAB.json").read_text("utf-8"))
    assert rep["families"]["good_fam"]["run"] == len(good)
    assert "online_fdr" in rep["consumer"]
    # a second pass continues from the ledger instead of starting again
    doc2 = organ.run(30.0, ledger_path=ledger)
    assert doc2["ledger_draws"] > doc["ledger_draws"]


def test_organ_without_a_docket_is_unmeasured(tmp_path: Path,
                                              monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(organ, "DOCKET", tmp_path / "absent.json")
    monkeypatch.setattr(organ, "REPORT", tmp_path / "NULL_LAB.json")
    doc = organ.run(5.0, ledger_path=tmp_path / "d.jsonl")
    assert doc["status"].startswith("UNMEASURED")
    assert doc["families_measured"] == 0


# ------------------------------------------------------------------------------ 7. wiring
def test_null_lab_is_an_hourly_leg_before_tier_s() -> None:
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_producer("null_lab", "research/null_lab.py", "--budget-s", "600")' in src
    assert src.index('_costed("null_lab", null_lab)') < src.index('_costed("tier_s", tier_s)')
    import hourly_cycle as hc
    assert hc.LEG_BUDGET_SEC["null_lab"] > 600
    assert hc.department_of("null_lab") == "validate"
    from libs.research.layers import LEG_LAYER
    assert LEG_LAYER["null_lab"] == "meta"
