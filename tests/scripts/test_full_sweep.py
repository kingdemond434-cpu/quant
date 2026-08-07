"""THE FULL-UNIVERSE SWEEP -- fencing the numbers that decide whether a survivor is real.

At 898,560 cells nothing here is individually small. The hurdle is derived from the universe size,
so a silent change to the feature list buys a weaker significance bar; the trial count is kept at
898,560 by pooling, so a change to pooling silently multiplies the search by the symbol count; and
the per-bar horizon normalisation is the only reason the weekly arm is not favoured for purely
arithmetic reasons. Each of those is one line of code and a whole false discovery.

So this file tests ACCOUNTING, REFUSAL and ALIGNMENT. The arithmetic of an IC is the evaluator's
problem and is fenced there.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import scripts.run_full_sweep as FS

from libs.alpha_factory.combination_engine import HORIZONS, REGIMES, TRANSFORMS
from libs.alpha_factory.hypothesis_engine import _TEMPLATES

ROOT = Path(__file__).resolve().parents[2]


def _bars(tmp: Path, n: int = 900, symbols: tuple[str, ...] = ("BTCUSDT", "ETHUSDT", "SOLUSDT"),
          *, spread: bool = True, volume: bool = True) -> Path:
    """Synthetic bars. LEGITIMATE HERE AND NOWHERE NEAR A VERDICT: these fence the harness's
    plumbing, and the script itself refuses to synthesise when asked for a result."""
    d = tmp / "bars"
    d.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(11)
    ts = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    for i, sym in enumerate(symbols):
        cols: dict[str, object] = {
            "timestamp": ts,
            "close": 100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, n))),
        }
        if volume:
            cols["volume"] = rng.lognormal(10, 1, n)
        if spread:
            cols["spread_bp"] = rng.lognormal(i - 1, 0.3, n)
        pd.DataFrame(cols).to_csv(d / f"{sym}.csv", index=False)
    return d


# --------------------------------------------------------------- the declared universe


def test_THE_DECLARED_FEATURES_STILL_MATCH_THE_TEMPLATES() -> None:
    """The 13 features are written out rather than derived, so this is what catches the drift.

    Deriving them would let a template edit change the universe size silently -- and the universe
    size IS the hurdle, so the edit would buy a weaker significance bar without anyone deciding to.
    """
    templated = {f for rows in _TEMPLATES.values() for _s, feats in rows for f in feats}
    assert set(FS.DECLARED_FEATURES) == templated, (
        "the template feature set moved. That changes the declared universe and therefore the "
        "hurdle -- re-declare it in a NEW pre-registration rather than editing this tuple.")
    assert len(FS.DECLARED_FEATURES) == 13


def test_THE_ENUMERATED_UNIVERSE_IS_EXACTLY_THE_PREREGISTERED_ONE() -> None:
    n, ok = FS.universe_check()
    assert (n, ok) == (898_560, True)
    assert n == len(HORIZONS) * len(REGIMES) * 702 * len(TRANSFORMS) ** 2


def test_THE_HURDLE_COMES_FROM_THE_DECLARED_COUNT_NOT_THE_MEASURABLE_ONE() -> None:
    """Deflating on the survivors' denominator would shrink the bar in exact proportion to how many
    cells failed -- the most flattering possible accounting, and the one this design exists to
    forbid."""
    assert FS.hurdle() == pytest.approx(5.236, abs=5e-4)
    assert FS.hurdle() == pytest.approx(float(np.sqrt(2 * np.log(898_560))))


def test_A_CHANGED_UNIVERSE_REFUSES_TO_RUN(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """If the code and the pre-registration disagree about the search size, the run is not a
    smaller version of the study -- it is a different study with a borrowed hurdle."""
    monkeypatch.setattr(FS, "DECLARED_FEATURES", FS.DECLARED_FEATURES[:5])
    monkeypatch.setattr(sys, "argv", ["run_full_sweep.py", "--bars", str(tmp_path)])
    assert FS.main() == 1


def test_EVERY_GROUP_ENUMERATES_AND_THE_GROUPS_SUM_TO_THE_UNIVERSE() -> None:
    """The sweep runs per (horizon, regime). If the groups do not tile the declared space, the run
    reports a denominator it did not actually search."""
    one = len(FS.group_space(HORIZONS[0], REGIMES[0]))
    assert one * len(HORIZONS) * len(REGIMES) == FS.PREREGISTERED_UNIVERSE


def test_REMAPPING_TO_PRECOMPUTED_TRANSFORMS_PRESERVES_THE_CANDIDATE_IDENTITY() -> None:
    """Transforms are applied once and pooled, so candidates are rewritten to name their already-
    transformed inputs. If that rewrite changed the key, 898,560 results would carry identities
    that do not match the space that was declared."""
    from libs.alpha_factory.combination_engine import enumerate_space

    space = enumerate_space(FS.DECLARED_FEATURES[:4], horizons=["1d"], regimes=["all"],
                            transforms=TRANSFORMS)
    for c in space.combinations[:400]:
        assert FS._remap(c).key == c.key


# ------------------------------------------------------------------ trial accounting


def test_POOLING_KEEPS_ONE_CANDIDATE_AT_ONE_TRIAL() -> None:
    """Evaluating each candidate once per symbol would be 898,560 x S trials against a hurdle
    declared for 898,560 -- the same error as testing a sample and deflating for it."""
    parts = [pd.Series(np.arange(10, dtype=float)) for _ in range(3)]
    out = FS.pool(parts)
    assert len(out) == 3 * 10 + FS._POOL_GAP * 2
    assert int(out.isna().sum()) == FS._POOL_GAP * 2


def test_THE_POOL_GAP_STOPS_ONE_SYMBOL_PREDICTING_THE_NEXT() -> None:
    """Without the NaN gap the first bar of ETH is predicted by the last bar of BTC -- a leak
    across a boundary that does not exist in time, repeated once per symbol per cell."""
    a = pd.Series([1.0, 2.0, 3.0])
    b = pd.Series([10.0, 20.0, 30.0])
    pooled = FS.pool([a, b])
    shifted = pooled.shift(1)
    first_b = len(a) + FS._POOL_GAP
    assert bool(np.isnan(shifted.iloc[first_b])), "BTC's last bar reached ETH's first bar"


def test_FAMILY_COLLAPSES_TRANSFORM_HORIZON_AND_REGIME() -> None:
    """L1.52(a): FORMULA and FAMILY are inventory. If FAMILY did not collapse the knobs, a single
    idea would report as up to 1,280 discoveries."""
    a = FS.family_of(["cat", "ratio", "1h", "high_vol", "rank(funding)", "delta(oi)"])
    b = FS.family_of(["cat", "ratio", "1d", "all", "zscore(funding)", "ts_rank(oi)"])
    assert a == b == ("ratio", "funding", "oi")
    # and the pair is order-insensitive, so (oi, funding) is the same family as (funding, oi)
    assert FS.family_of(["cat", "lead", "1h", "all", "oi", "funding"]) == ("lead", "funding", "oi")


def test_BASE_FEATURE_UNWRAPS_ONLY_A_TRANSFORM() -> None:
    assert FS.base_feature("rank(funding)") == "funding"
    assert FS.base_feature("funding") == "funding"


# ----------------------------------------------------------------- alignment and bias


def test_FORWARD_RETURNS_ARE_EXPRESSED_PER_BAR() -> None:
    """A raw weekly return charged a per-bar cost makes the 1w arm look 168x more profitable for
    arithmetic reasons alone, and a sweep this wide would find every survivor there."""
    close = pd.DataFrame({"X": np.exp(np.arange(50) * 0.01)})
    one, ten = FS.forward(close, 1), FS.forward(close, 10)
    # The residual 5% gap is COMPOUNDING, not scaling. Undivided, the 10-bar figure would be ~10x
    # the 1-bar one, which is the bias this normalisation removes.
    assert one["X"].iloc[0] == pytest.approx(ten["X"].iloc[0], rel=0.06)
    assert (close["X"].shift(-10) / close["X"] - 1.0).iloc[0] > 9 * one["X"].iloc[0]


def test_OVERLAPPING_RETURNS_ARE_DISCOUNTED_IN_THE_T_STATISTIC() -> None:
    """An h-bar return sampled every bar reuses each observation h times, inflating t by ~sqrt(h).
    At the weekly horizon on hourly bars that is a factor of 13 -- enough to manufacture the entire
    survivor set."""
    assert abs(FS.t_stat(0.1, 10_000, 168)) < abs(FS.t_stat(0.1, 10_000, 1))
    assert FS.t_stat(0.1, 10_000, 1) / FS.t_stat(0.1, 10_000, 100) == pytest.approx(10.0, rel=0.02)
    assert FS.t_stat(0.5, 2, 1) == 0.0, "a sample at or below the degrees of freedom must score 0"
    assert FS.t_stat(0.5, 100, 168) == 0.0, "an effective sample under 2 must score 0"
    assert FS.t_stat(float("nan"), 5000, 1) == 0.0


def test_REGIME_THRESHOLDS_NEVER_SEE_THEIR_OWN_FUTURE() -> None:
    """A full-sample percentile used as a regime threshold encodes the answer in the threshold.
    An expanding median only ever looks backwards."""
    rng = np.random.default_rng(3)
    ret = pd.DataFrame({"X": rng.normal(0, 0.01, 600)})
    head = FS.regime_masks(ret)["high_vol"]["X"].to_numpy()[:400].copy()
    ret_ext = pd.DataFrame({"X": np.concatenate([ret["X"].to_numpy()[:400],
                                                 rng.normal(0, 0.5, 200)])})
    assert np.array_equal(head, FS.regime_masks(ret_ext)["high_vol"]["X"].to_numpy()[:400]), (
        "a later volatility explosion changed an earlier bar's regime -- the threshold is "
        "looking forward")


def test_AN_UNDETERMINED_REGIME_BELONGS_TO_NEITHER_ARM() -> None:
    """Forcing early bars into an arm puts the least-contextualised tape wherever the comparison
    operator happens to point, which is a choice nobody made deliberately."""
    rng = np.random.default_rng(4)
    ret = pd.DataFrame({"X": rng.normal(0, 0.01, 600)})
    m = FS.regime_masks(ret)
    both = (m["high_vol"]["X"] | m["low_vol"]["X"]).to_numpy()
    assert not both.all(), "every bar was assigned a volatility regime, including bars with no "\
                           "expanding reference yet"
    assert bool(m["all"]["X"].all())


# ------------------------------------------------------------------- honest refusal


def test_WITH_NO_BARS_IT_BLOCKS_AND_STILL_RECORDS_THE_BUDGET(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """BLOCKED is a result. The declared universe and hurdle go into the artifact either way, so
    the pre-registration is on the record even when the run cannot happen."""
    out = tmp_path / "rep.json"
    monkeypatch.setattr(sys, "argv", ["run_full_sweep.py", "--bars", str(tmp_path / "nope"),
                                      "--out", str(out)])
    assert FS.main() == 0
    rep = json.loads(out.read_text())
    assert rep["verdict"].startswith("BLOCKED")
    assert rep["declared_universe"] == 898_560
    assert rep["hurdle"] == pytest.approx(5.236, abs=5e-4)
    assert "SYNTHESIS" in rep["note"].upper()


def test_IT_REFUSES_A_RUN_IT_CANNOT_FINISH(tmp_path: Path,
                                           monkeypatch: pytest.MonkeyPatch) -> None:
    """This box collects tape that cannot be re-acquired at any price. An unprojected multi-hour
    single-core job competing with the recorders is how the desk loses the one asset it cannot
    rebuild -- so the projection happens BEFORE the sweep, not after it."""
    out = tmp_path / "rep.json"
    monkeypatch.setattr(sys, "argv", ["run_full_sweep.py", "--bars", str(_bars(tmp_path)),
                                      "--out", str(out), "--max-minutes", "0.001"])
    assert FS.main() == 0
    rep = json.loads(out.read_text())
    assert rep["verdict"].startswith("BLOCKED")
    assert rep["projected_minutes"] > 0 and rep["suggested_tail_bars"] > 0
    assert "nothing was swept" in rep["reason"]


def test_A_FEATURE_THAT_CANNOT_BE_BUILT_IS_ABSENT_WITH_A_REASON(tmp_path: Path) -> None:
    """A zero-filled feature is not a missing feature, it is a constant one -- and a constant
    consumes 69,120 trials while testing nothing (L1.28a)."""
    frames = FS.discover(None, _bars(tmp_path, volume=False))
    _idx, aligned = FS.align(frames, 0)
    panels, absent = FS.feature_panels(aligned)
    assert "liquidity" in absent and "volume" in absent["liquidity"]
    assert "carry" in absent and "funding" in absent["carry"]
    assert "liquidity" not in panels and "carry" not in panels
    assert set(panels) | set(absent) == set(FS.DECLARED_FEATURES)


def test_CROSS_SECTIONAL_FEATURES_ARE_REFUSED_ON_ONE_SYMBOL(tmp_path: Path) -> None:
    """rel_strength against a one-symbol cross-section is identically zero. Computed rather than
    refused, it would be a flat line consuming a fifth of the universe."""
    frames = FS.discover(None, _bars(tmp_path, symbols=("BTCUSDT",)))
    _idx, aligned = FS.align(frames, 0)
    panels, absent = FS.feature_panels(aligned)
    for name in ("rel_strength", "dispersion", "lead_lag"):
        assert name in absent and name not in panels


def test_THE_LIQUIDITY_DISCLOSURE_IS_UNMEASURED_WITHOUT_A_SPREAD_COLUMN(tmp_path: Path) -> None:
    """F8. Reporting 'no concentration detected' from an absent column is WS-005 exactly, and it
    is the reading that flatters every survivor."""
    frames = FS.discover(None, _bars(tmp_path, spread=False))
    _idx, aligned = FS.align(frames, 0)
    import argparse

    args = argparse.Namespace(max_detail=10, cost_bp=10.0, min_obs=200)
    rep = FS._liquidity_disclosure(aligned, [], {}, pd.DataFrame(), {}, sorted(frames), args,
                                   3600.0)
    assert rep["verdict"] == "UNMEASURED"
    assert "NOT an absence" in str(rep["reason"])


def test_AN_UNMEASURABLE_CELL_IS_CLASSIFIED_BY_CAUSE() -> None:
    """Pooling pre-applies the transforms, so a cross-sectional transform that could not be built
    reaches the evaluator as a MISSING FEATURE. Unclassified, the report would blame the feature
    for the panel's absence."""
    unavailable = {"rank(momentum)": "needs 2+ symbols"}
    absent = {"carry": "no funding column"}
    assert "cross-sectional" in FS._reason_class(
        "feature missing: rank(momentum)/trend", unavailable, absent)
    assert "could not be built" in FS._reason_class(
        "feature missing: delta(carry)/trend", unavailable, absent)
    assert FS._reason_class("UNMEASURED: 12 usable obs", unavailable, absent) == "UNMEASURED"


# --------------------------------------------------------------------- end to end


def test_THE_WHOLE_PIPELINE_RUNS_AND_NOISE_PRODUCES_NO_SURVIVORS(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NEGATIVE CONTROL ON THE FULL PIPELINE, run over a reduced universe so it fits in a test.

    If random walks yield survivors, every number this harness produces about the real tape is
    worthless -- and it would be worthless in the most convincing possible direction.
    """
    out = tmp_path / "rep.json"
    monkeypatch.setattr(FS, "PREREGISTERED_UNIVERSE",
                        FS.space_size(4, n_transforms=len(TRANSFORMS)))
    monkeypatch.setattr(FS, "DECLARED_FEATURES", ("momentum", "trend", "zscore", "breakout"))
    monkeypatch.setattr(FS, "HORIZONS", ("1h",), raising=False)
    monkeypatch.setattr(sys, "argv",
                        ["run_full_sweep.py", "--bars", str(_bars(tmp_path, n=900)),
                         "--out", str(out), "--min-obs", "200", "--max-minutes", "30"])
    assert FS.main() == 0
    rep = json.loads(out.read_text())
    assert rep["counts"]["evaluated"] > 0
    assert rep["counts"]["measurable"] > 0
    assert rep["counts"]["FORMULA"] == 0, (
        f"noise produced {rep['counts']['FORMULA']} survivor(s): {rep['survivors'][:2]}")
    assert rep["counts"]["PORTFOLIO_CONTRIBUTING"] is None, (
        "an unbuilt portfolio test must report null, never 0 -- UNMEASURED is not zero")
    assert rep["liquidity_disclosure_F8"]["verdict"] in {"MEASURED", "UNMEASURED"}


def test_THE_SCRIPT_IS_EXECUTABLE_AND_ITS_HELP_WORKS() -> None:
    """A study nobody can start is a gate that never ran (L1.49)."""
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "run_full_sweep.py"), "--help"],
                       capture_output=True, text=True, timeout=120, check=False)
    assert r.returncode == 0 and "--tail-bars" in r.stdout


def test_THE_PREREGISTRATION_EXISTS_AND_BINDS_THE_SAME_NUMBERS() -> None:
    """Kill criteria chosen after seeing a result are not kill criteria. If the document and the
    code disagree on a threshold, the code is running an unregistered study."""
    text = (ROOT / "docs" / "research" / "FULL_SWEEP_PREREGISTRATION.md").read_text("utf-8")
    assert "898,560" in text and "5.236" in text
    assert "70/30" in text, "the walk-forward split must be declared, not chosen in code"
    for token in ("25%", "10bp", "200", "0.7"):
        assert token in text, f"threshold {token} is in the code but not in the pre-registration"


def test_THE_RUNTIME_PROJECTION_SAMPLES_ACROSS_OPERATORS_NOT_THE_HEAD(tmp_path: Path) -> None:
    """The guard exists to stop an unprojected multi-hour job starving the recorders, so an
    under-projection defeats it entirely.

    Enumeration walks operators in order: the first 300 cells are all `interaction`, one multiply.
    `divergence` ranks both sides and costs several times more. A head sample would therefore
    price the sweep at its cheapest operator and wave through a run several times longer than
    promised -- which is exactly what happened on the first measured run of this script.
    """
    group = FS.group_space("1h", "all")
    head = {c.operator for c in group[:300]}
    strided = {c.operator for c in group[:: max(1, len(group) // 300)][:300]}
    assert len(head) == 1, "the head of the enumeration is no longer single-operator"
    assert len(strided) >= 4, f"the strided calibration batch still misses operators: {strided}"


def test_A_PLANTED_EDGE_SURVIVES_THE_WHOLE_PIPELINE(tmp_path: Path,
                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    """POSITIVE CONTROL ON THE FULL PIPELINE, and the counterpart the negative control needs.

    A harness that returns zero survivors on noise and zero on a real edge is indistinguishable
    from a broken one -- and it would be WRONG IN THE MOST REASSURING DIRECTION, reporting "the
    expression space is bounded" while measuring nothing. This plants strongly autocorrelated
    returns, which `momentum` must find, and then exercises the code that only runs when the desk
    actually has something: F3-F6, independence clustering, and the F8 disclosure.
    """
    d = tmp_path / "bars"
    d.mkdir(parents=True)
    rng = np.random.default_rng(19)
    n, phi = 1400, 0.6
    ts = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    for i, sym in enumerate(("BTCUSDT", "ETHUSDT", "SOLUSDT")):
        r = np.zeros(n)
        eps = rng.normal(0, 0.01, n)
        for t in range(1, n):
            r[t] = phi * r[t - 1] + eps[t]          # momentum is REAL in this tape, by construction
        pd.DataFrame({"timestamp": ts, "close": 100.0 * np.exp(np.cumsum(r)),
                      "volume": rng.lognormal(10, 1, n),
                      "spread_bp": rng.lognormal(i - 1, 0.3, n)}).to_csv(d / f"{sym}.csv",
                                                                        index=False)
    out = tmp_path / "rep.json"
    monkeypatch.setattr(FS, "PREREGISTERED_UNIVERSE",
                        FS.space_size(4, n_transforms=len(TRANSFORMS)))
    monkeypatch.setattr(FS, "DECLARED_FEATURES", ("momentum", "trend", "zscore", "breakout"))
    monkeypatch.setattr(FS, "HORIZONS", ("1h",), raising=False)
    monkeypatch.setattr(sys, "argv", ["run_full_sweep.py", "--bars", str(d), "--out", str(out),
                                      "--max-minutes", "30", "--max-cluster", "40"])
    assert FS.main() == 0
    rep = json.loads(out.read_text())
    assert rep["counts"]["FORMULA"] > 0, (
        "a planted, strongly autocorrelated edge did not survive -- the harness cannot "
        f"distinguish signal from noise. kills: {rep['kill_criteria_fired']}")

    # the survivor record has to carry the evidence, not just the verdict
    s = rep["survivors"][0]
    assert s["oos_net_bps"] > 0 and s["is_net_bps"] > 0, "F3 admitted a non-positive arm"
    assert abs(s["t"]) >= rep["hurdle"]

    # FORMULA >= FAMILY >= INDEPENDENT MECHANISM: inventory can only collapse, never expand
    c = rep["counts"]
    assert c["FORMULA"] >= c["FAMILY"] >= c["INDEPENDENT_MECHANISM"] >= 1, c
    ind = rep["independence"]
    assert ind is not None and ind["clusters"]
    # F7's cap: clustering is O(k^2) and must never hang the study precisely when it found
    # something. When the cap binds, the mechanism count must be labelled a LOWER bound.
    assert ind["clustered"] <= 40
    if ind["capped_at"]:
        assert "LOWER bound" in ind["cap_note"]
    assert rep["liquidity_disclosure_F8"]["verdict"] == "MEASURED"
    assert rep["liquidity_disclosure_F8"]["median_spread_by_symbol"]


def test_AN_EMPTY_SURVIVOR_LIST_DOES_NOT_BECOME_A_CLAIM_ABOUT_THE_SPACE() -> None:
    """WS-005, caught in the desk's own harness. The first version of this headline said "the
    expression space is bounded" whenever the survivor list was empty -- the same list a run
    produces when nothing reached the screen at all, or when a quarter of the universe was never
    measurable. Only one of those bounds anything."""
    exercised = FS.verdict(0, 12, 1000, 1000)
    never = FS.verdict(0, 0, 1000, 800)
    assert "kill criteria killed every one" in exercised
    assert "NOT ONE CELL" in never and "never exercised" in never
    assert "20.0% UNMEASURED" in never and "not 'no edge'" in never
    assert "not a statement about alpha" in never
    assert FS.verdict(3, 9, 1000, 1000).startswith("3 STAGE-A SURVIVOR(S)")
    assert "bounds the expression language" not in FS.verdict(3, 9, 1000, 1000)
