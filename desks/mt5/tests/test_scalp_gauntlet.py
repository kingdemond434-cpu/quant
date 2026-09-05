"""The scalp lane has a backtest gauntlet: the same ten gates, on the executor's own bracket.

Principal 2026-09-05: "backtest-equivalent gauntlets should exist for all types of sleeves --
this is cheap; a lane with no gauntlet is third-world behaviour in our quant." Until now the four
gold scalp candidates could only mature on a forward clock, because the gauntlet built H1 cells
alone; no ten-gate certificate could exist for them and the promoter called the clock one.

What is pinned:

  * the adapter (`mt5desk.scalp_families.family_scalp`) replays the lane's economics through the
    desk engine within a MEASURED tolerance of `scalp_reverse_engineering.simulate`, and every
    signal it emits is the bracket `scalp_exec.plan_entry` would place at that bar's open;
  * the gauntlet builds one cell per declared candidate, prices it by the sanctioned constructor
    at the honest 2x baseline, and hands it to the ONE validator -- the real ten gates run once
    here on tiny bars and every verdict carries exactly the canonical stage list;
  * absent bars or an absent cost basis are UNMEASURED with the reason and a non-zero exit --
    never a pass; the multiplicity census is the lane's FULL swept grid and an undercharge
    withholds certificates rather than loosening anything;
  * a certificate, once in the canon under `scalp.<candidate>`, reaches `authorized_specs` in the
    promoter's own tuple shape and `authorized_runs` with the executable recipe -- and never as an
    H1 run.
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
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK / "scripts"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import scalp_gauntlet as sg  # noqa: E402
import shadow_admission as sa  # noqa: E402
from desks.mt5.research import scalp_family_expansion as fam  # noqa: E402
from desks.mt5.research import scalp_reverse_engineering as core  # noqa: E402
from desks.mt5.research import scalp_shadow  # noqa: E402
from gate_policy import ATTESTATION, GATES, all_ten_pass, charged_trial_count  # noqa: E402

from mt5desk import scalp_exec as sx  # noqa: E402
from mt5desk import scalp_families as sf  # noqa: E402
from mt5desk.engine import Costs, Signal, run_backtest  # noqa: E402

SPREAD_PTS = 14.5
#: An XAUUSD registry row in the live shape (contract 100 oz, tick 0.01, EUR-account tick value).
META = {"XAUUSD": {"contract_size": 100.0, "tick_size": 0.01, "tick_value": 0.862,
                   "median_spread_pts": SPREAD_PTS}}
M15_BREAKOUT = fam.Choice("anti_donchian_breakout", "all", 1.0, 1.5, 6)
M15_MOMENTUM = fam.Choice("anti_three_bar_momentum", "all", 1.0, 1.5, 6)


def _bars(freq: str = "15min", n: int = 6000, seed: int = 0) -> pd.DataFrame:
    """A gold-like random walk with a constant recorded spread, so the replay's per-bar cost and
    the engine's registry cost can be made identical and the comparison isolates the mechanics."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2026-01-05", periods=n, freq=freq, tz="UTC")
    close = 2000.0 + np.cumsum(rng.normal(0, 0.9, n))
    opn = np.r_[close[0], close[:-1]]
    high = np.maximum(opn, close) + np.abs(rng.normal(0, 0.6, n))
    low = np.minimum(opn, close) - np.abs(rng.normal(0, 0.6, n))
    return pd.DataFrame({"open": opn, "high": high, "low": low, "close": close,
                         "tick_volume": rng.integers(50, 200, n).astype(float),
                         "spread": np.full(n, SPREAD_PTS)}, index=idx)


def _ten(passed: bool = True) -> dict[str, dict[str, Any]]:
    return {g: {"passed": passed} for g in GATES}


def _matched_costs() -> Costs:
    """The engine's cost per unit equals `simulate`'s spread*point + FUSION_COMMISSION_PRICE."""
    return Costs(spread_per_lot=SPREAD_PTS * 0.01 * 100.0, commission_per_lot=2.25,
                 contract_oz=100.0, quote_per_account=1.0)


@pytest.fixture
def desk(tmp_path: Path):
    data = tmp_path / "universe"
    data.mkdir()
    (data / "universe.json").write_text(json.dumps(META), "utf-8")
    reports = tmp_path / "reports"
    reports.mkdir()

    class Desk:
        data_dir = data
        out = reports / "SCALP_GAUNTLET.json"
        base = tmp_path

        def bars(self, tf: str, n: int, seed: int = 0) -> pd.DataFrame:
            freq = {"M5": "5min", "M15": "15min"}[tf]
            df = _bars(freq, n, seed)
            df.to_parquet(data / f"XAUUSD_{tf}.parquet")
            return df

        def canon(self, rows: dict) -> None:
            (reports / "UNIVERSAL_SURVIVORS.json").write_text(json.dumps({
                "n": len(rows), "gate_policy": ATTESTATION, "survivors": rows}), "utf-8")

    return Desk()


class FakeGauntlet:
    """Captures the cells and answers with canned verdicts keyed by candidate name."""

    def __init__(self, outcomes: dict[str, str], n_trials: int = 597) -> None:
        self.outcomes, self.n_trials, self.cells = outcomes, n_trials, []

    def __call__(self, cells: list[dict], hunt: str, meta: dict) -> dict:
        self.cells = list(cells)
        verdicts = []
        for c in cells:
            name = c["_scalp"]["name"]
            kind = self.outcomes.get(name, "fail")
            row: dict[str, Any] = {"cell": c["_scalp"]["cell"], "sym": c["sym"],
                                   "family": c["family"], "days": 120}
            if kind == "unmeasured":
                row.update({"passed": False, "unmeasured": True, "days": 12, "stages": {
                    "observations": {"passed": False, "days": 12, "required": 60,
                                     "why": "only 12 daily observations"}}})
            else:
                row.update({"passed": kind == "pass", "stages": _ten(kind == "pass")})
            verdicts.append(row)
        return {"hunt": hunt, "n_cells": len(cells), "n_trials": self.n_trials,
                "trial_count_basis": f"fixed_campaign_trials({self.n_trials})",
                "program_level": {"pbo": 0.1, "spa_p": 0.01}, "verdicts": verdicts}


# ------------------------------------------------------------------------------- the adapter
@pytest.mark.parametrize("choice", [M15_BREAKOUT, M15_MOMENTUM], ids=lambda c: c.family)
@pytest.mark.parametrize("seed", [0, 1, 2])
def test_adapter_tracks_the_replay_within_the_stated_tolerance(choice, seed: int) -> None:
    """MEASURED 2026-09-05 on 6,000 synthetic M15 bars, three seeds, both candidate families:
    the engine takes 6-9% MORE trades than `simulate` (a stop the fill bar runs through frees the
    position, which the study never examines) and its mean R per trade sits within 0.04R of the
    study's (within 0.03R once the study is given the same last-closed ATR). The bar pinned
    here is 12% on trade count and 0.06R per trade on total R. Both arms carry identical costs,
    so the difference is the stated mechanics and nothing else."""
    df = _bars(seed=seed)
    sig = sf.masked_signal(df, choice.family, choice.session)
    cfg = fam._cfg(choice, "single")
    study = np.asarray(core.simulate(df, cfg, signal_override=sig), dtype=float)
    aligned = np.asarray(core.simulate(df, cfg, signal_override=sig,
                                       atr_override=np.roll(core._atr(df), 1)), dtype=float)
    sigs = sf.family_scalp(df, family=choice.family, session=choice.session,
                           stop_atr=choice.stop_atr, target_atr=choice.target_atr,
                           max_hold=choice.max_hold)
    engine = np.array([t.r_multiple for t in run_backtest(df, sigs, _matched_costs()).trades])
    assert len(study) > 150 and len(engine) > 150           # positive control: not vacuous
    assert abs(len(engine) - len(study)) <= 0.12 * len(study)
    assert abs(engine.sum() - study.sum()) <= 0.06 * max(len(engine), len(study))
    assert abs(engine.mean() - aligned.mean()) <= 0.05


def test_each_signal_is_the_bracket_plan_entry_would_place() -> None:
    """Side, stop and target equal the executor's plan at that bar's open, and the engine's TTL
    exit lands on the very instant `ttl_deadline` names (the close of bar i + max_hold)."""
    df = _bars(n=3000)
    c = M15_BREAKOUT
    sigs = sf.family_scalp(df, family=c.family, session=c.session, stop_atr=c.stop_atr,
                           target_atr=c.target_atr, max_hold=c.max_hold, tag="cand")
    assert sigs and all(isinstance(s, Signal) and s.tag == "cand" for s in sigs)
    checked = 0
    # The executor refuses to plan on fewer than `MIN_BARS` closed bars (live it always holds
    # 400); the replay's warm-up is shorter, so compare on the signals the executor could see.
    live = [s for s in sigs if df.index.get_loc(s.time) + 1 >= sx.MIN_BARS]
    for s in live[:8]:
        i = df.index.get_loc(s.time) + 1                    # the engine fills at bar i's open
        px = float(df["open"].iloc[i])
        plan = sx.plan_entry(df.iloc[:i], tf="M15", family=c.family, session=c.session,
                             stop_atr=c.stop_atr, target_atr=c.target_atr, max_hold=c.max_hold,
                             bid=px, ask=px, forming_time=df.index[i])
        assert plan is not None and plan.side == s.side
        assert plan.stop == pytest.approx(s.stop) and plan.target == pytest.approx(s.target)
        assert s.ttl_bars == c.max_hold + 1
        assert df.index[i + s.ttl_bars].isoformat() == plan.ttl_until
        checked += 1
    assert checked == 8


def test_adapter_refuses_what_the_replay_refuses() -> None:
    df = _bars(n=2000)
    with pytest.raises(KeyError):
        sf.family_scalp(df, family="not_a_family", session="all", stop_atr=1.0, target_atr=1.5,
                        max_hold=6)
    with pytest.raises(ValueError):
        sf.family_scalp(df, family="anti_donchian_breakout", session="all", stop_atr=0.0,
                        target_atr=1.5, max_hold=6)
    assert sf.family_scalp(df.iloc[:30], family="anti_donchian_breakout", session="all",
                           stop_atr=1.0, target_atr=1.5, max_hold=6) == []
    both = sf.family_scalp(df, family="anti_donchian_breakout", session="all", stop_atr=1.0,
                           target_atr=1.5, max_hold=6)
    longs = sf.family_scalp(df, family="anti_donchian_breakout", session="all", stop_atr=1.0,
                            target_atr=1.5, max_hold=6, side_mode="long")
    assert {s.side for s in both} == {1, -1} and all(s.side == 1 for s in longs)
    assert all(s.time >= df.index[sf.WARMUP_BARS - 1] for s in both)


# ------------------------------------------------------------------------------ the gauntlet
def test_the_gauntlet_judges_exactly_the_lanes_declaration() -> None:
    assert sg.CANDIDATES is scalp_shadow.CANDIDATES


def test_one_cell_per_candidate_priced_at_the_honest_baseline(desk) -> None:
    desk.bars("M5", 3000)
    desk.bars("M15", 3000)
    fake = FakeGauntlet({})
    report = sg.run(data_dir=desk.data_dir, out=desk.out, gauntlet=fake, meta=META)
    names = [c["_scalp"]["name"] for c in fake.cells]
    assert names == list(sg.CANDIDATES)
    for c in fake.cells:
        tf, choice = sg.CANDIDATES[c["_scalp"]["name"]]
        # `Costs.from_symbol` at mult 2.0: pts x tick x contract x 2, commission untouched.
        assert c["costs"].spread_per_lot == pytest.approx(SPREAD_PTS * 0.01 * 100.0 * 2.0)
        assert c["costs"].commission_per_lot == 2.25 and c["costs"].contract_oz == 100.0
        assert c["mechanism_status"] == "NAMED" and c["family"] == choice.family
        assert c["params"] == sg.recipe(tf, choice)
        assert c["_scalp"]["timeframe"] == tf
    assert set(report["candidates"]) == set(sg.CANDIDATES)
    assert report["gate_policy"] == ATTESTATION and report["status"] == "MEASURED"
    assert report["rc"] == 0 and report["certificates"] == {}
    assert json.loads(desk.out.read_text("utf-8"))["hunt"] == "scalp_gauntlet"


def test_a_ten_gate_pass_becomes_a_certificate_with_the_whole_recipe(desk) -> None:
    desk.bars("M5", 3000)
    desk.bars("M15", 3000)
    fake = FakeGauntlet({"xau_m15_anti_breakout": "pass", "xau_m5_anti_momentum_ny": "unmeasured"})
    report = sg.run(data_dir=desk.data_dir, out=desk.out, gauntlet=fake, meta=META)
    assert list(report["certificates"]) == ["xau_m15_anti_breakout"]
    cert = report["certificates"]["xau_m15_anti_breakout"]
    assert all_ten_pass(cert["gates"]) and cert["sym"] == "XAUUSD" and cert["n_trials"] == 597
    spec = cert["shadow_spec"]
    assert {k: spec[k] for k in ("symbol", "timeframe", "family", "session", "stop_atr",
                                 "target_atr", "max_hold", "side")} == {
        "symbol": "XAUUSD", "timeframe": "M15", "family": "anti_donchian_breakout",
        "session": "all", "stop_atr": 1.0, "target_atr": 1.5, "max_hold": 6, "side": "BOTH"}
    assert spec["exec"] == "scalp_market" and spec["selector"] == "xau_m15_anti_breakout"
    # One candidate the gates could not judge: the run is PARTIAL, the exit non-zero, and the
    # reason travels with the name. A measured FAIL, by contrast, is a verdict (rc 0 above).
    assert report["status"] == "PARTIAL" and report["rc"] == 2
    assert "12 daily observations" in report["unmeasured"]["xau_m5_anti_momentum_ny"]["why"]
    assert {v["candidate"] for v in report["verdicts"]} == set(sg.CANDIDATES)


def test_the_real_ten_gates_judge_scalp_cells(desk, monkeypatch) -> None:
    """The one validator, run for real on 100 days of bars: every verdict carries exactly the
    canonical stage list, and the charge is the sealed fixed campaign count."""
    desk.bars("M15", 96 * 100)
    monkeypatch.setattr(sg, "CANDIDATES", {"xau_m15_anti_breakout": ("M15", M15_BREAKOUT),
                                            "xau_m15_anti_momentum": ("M15", M15_MOMENTUM)})
    report = sg.run(data_dir=desk.data_dir, out=desk.out, meta=META)
    assert report["status"] == "MEASURED" and report["rc"] == 0 and report["n_judged"] == 2
    for v in report["verdicts"]:
        assert tuple(v["stages"]) == GATES and v["days"] >= 60
        assert v["stages"]["economic_prior"]["passed"] is True
        assert v["stages"]["deflated_sharpe"]["n_trials"] == report["gauntlet"]["n_trials"]
    expected, basis = charged_trial_count(2, None, None)
    assert report["multiplicity"]["charged_n_trials"] == expected
    assert report["multiplicity"]["charged_basis"] == basis
    assert set(report["gauntlet"]["program_level"]) == {"pbo", "spa_p"}
    # A pass here would be a certificate; random-walk bars must not produce one (never a fake).
    assert all(v["passed"] is False for v in report["verdicts"]) or report["certificates"]


def test_absent_bars_are_unmeasured_and_the_exit_is_non_zero(desk, monkeypatch) -> None:
    def never(*_a: Any, **_k: Any) -> dict:
        pytest.fail("the gauntlet must not run on a docket with no bars")

    report = sg.run(data_dir=desk.data_dir, out=desk.out, gauntlet=never, meta=META)
    assert report["status"] == "UNMEASURED" and report["rc"] == 2
    assert set(report["unmeasured"]) == set(sg.CANDIDATES) and report["certificates"] == {}
    for name, (tf, _c) in sg.CANDIDATES.items():
        assert f"XAUUSD_{tf}.parquet" in report["unmeasured"][name]["why"]
    monkeypatch.setattr(sg, "UNI", desk.data_dir)
    monkeypatch.setattr(sg, "OUT", desk.out)
    monkeypatch.setattr(sg.eg, "run_gauntlet", never)
    assert sg.main() == 2
    assert json.loads(desk.out.read_text("utf-8"))["status"] == "UNMEASURED"


def test_an_absent_cost_basis_is_unmeasured_never_free(desk) -> None:
    """`Costs.from_symbol({})` prices at the constructor's floor -- the silent undercharge the
    sealed sweep documents. No registry row, no price, no verdict."""
    desk.bars("M15", 3000)
    fake = FakeGauntlet({"xau_m15_anti_breakout": "pass"})
    for meta in ({}, {"EURUSD": META["XAUUSD"]}, {"XAUUSD": {"contract_size": 100.0}},
                 {"XAUUSD": {**META["XAUUSD"], "tradeable": False}}):
        report = sg.run(data_dir=desk.data_dir, out=desk.out, gauntlet=fake, meta=meta)
        assert report["rc"] == 2 and report["certificates"] == {} and fake.cells == []
        assert all("XAUUSD" in r["why"] or "registry" in r["why"]
                   for r in report["unmeasured"].values())


def test_multiplicity_is_the_lanes_full_swept_grid_and_an_undercharge_withholds(desk) -> None:
    grid = sf.swept_grid()
    tfs = ("M1", "M5", "M15")
    assert grid["reverse_engineering"]["total"] == sum(len(core._configs(tf)) for tf in tfs)
    assert grid["family_expansion"]["families"] == 14 and grid["family_expansion"]["sessions"] == 4
    selection = 14 * 4 * sum(len(fam._geometry(tf)) for tf in tfs)
    assert grid["family_expansion"]["total"] == selection + 14 * len(tfs)
    assert grid["total"] == grid["reverse_engineering"]["total"] + grid["family_expansion"]["total"]
    assert grid["total"] == 570
    # The sealed charge covers the grid today; the certificate is minted only while it does.
    charge, _ = charged_trial_count(4, None, None)
    assert charge >= grid["total"]
    desk.bars("M15", 3000)
    short = FakeGauntlet({"xau_m15_anti_breakout": "pass"}, n_trials=grid["total"] - 1)
    report = sg.run(data_dir=desk.data_dir, out=desk.out, gauntlet=short, meta=META)
    assert report["certificates"] == {}
    assert "xau_m15_anti_breakout" in report["certificates_withheld"]
    assert report["multiplicity"]["covered_by_charge"] is False
    exact = FakeGauntlet({"xau_m15_anti_breakout": "pass"}, n_trials=grid["total"])
    report = sg.run(data_dir=desk.data_dir, out=desk.out, gauntlet=exact, meta=META)
    assert "xau_m15_anti_breakout" in report["certificates"]
    assert report["multiplicity"]["covered_by_charge"] is True


# ----------------------------------------------------------------------------- the admission
def test_a_scalp_certificate_in_the_canon_reaches_admission_in_the_promoters_shape(desk) -> None:
    desk.bars("M15", 3000)
    fake = FakeGauntlet({"xau_m15_anti_breakout": "pass", "xau_m15_anti_momentum": "fail"})
    sg.run(data_dir=desk.data_dir, out=desk.out, gauntlet=fake, meta=META)
    rows = sg.canon_rows(desk.out)
    assert list(rows) == ["scalp.xau_m15_anti_breakout"]
    row = rows["scalp.xau_m15_anti_breakout"]
    assert row["hunt"] == "scalp_gauntlet" and row["sym"] == "XAUUSD" and all_ten_pass(row["gates"])
    desk.canon(rows)

    specs = sa.authorized_specs(desk.base)
    # promoter.promote_scalp's own construction: ("XAUUSD", name, None, "gold_scalp", False)
    assert ("XAUUSD", "xau_m15_anti_breakout", None, "gold_scalp", False) in specs
    assert sa.scalp_spec("XAUUSD", "xau_m15_anti_breakout") in specs
    assert not any(s[3] == "anti_donchian_breakout" for s in specs)   # never the generic tuple

    runs = sa.authorized_runs(desk.base)
    (run,) = runs
    assert run["certificate"] == "scalp.xau_m15_anti_breakout" and run["exec"] == "scalp_market"
    assert run["family"] == "anti_donchian_breakout" and run["selector"] == "xau_m15_anti_breakout"
    assert tuple(run["params"]) == sa.SCALP_RECIPE_KEYS and run["side"] == "BOTH"
    assert run["params"]["max_hold"] == 6 and run["timeframe"] == "M15"
    assert sa.authorized_runs(desk.base, lanes=("h1",)) == []          # never an H1 run


def test_admission_fails_closed_on_anything_but_an_exact_scalp_pass(desk) -> None:
    good = {"symbol": "XAUUSD", "selector": "c", "timeframe": "M15",
            "family": "anti_donchian_breakout", "session": "all", "stop_atr": 1.0,
            "target_atr": 1.5, "max_hold": 6, "side": "BOTH", "exec": "scalp_market",
            "is_universe": False, "hunt": "scalp_gauntlet", "condition": None}
    failing = {**_ten(), "lockbox": {"passed": False}}
    desk.canon({"scalp.c": {"gates": failing, "shadow_spec": good},
                "scalp.d": {"gates": _ten(), "shadow_spec": {k: v for k, v in good.items()
                                                              if k != "max_hold"}},
                "scalp.e": {"gates": _ten()}})
    assert not any(s[3] == "gold_scalp" for s in sa.authorized_specs(desk.base))
    assert sa.authorized_runs(desk.base) == []
    # and a report without the exact attestation hands the canon writer nothing to merge
    doc = json.loads(desk.out.read_text("utf-8")) if desk.out.exists() else {}
    doc.update({"gate_policy": {**ATTESTATION, "dsr_threshold": 0.5},
                "certificates": {"c": {"gates": _ten(), "shadow_spec": good, "cell": "x"}}})
    desk.out.write_text(json.dumps(doc), "utf-8")
    assert sg.canon_rows(desk.out) == {}
