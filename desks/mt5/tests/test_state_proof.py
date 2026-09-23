"""The proof is conditional on the market, and so is the target. ProofCertificate(StateCluster).

    python -m pytest desks/mt5/tests/test_state_proof.py -q

ONE GLOBAL CERTIFICATE ANSWERS THE WRONG QUESTION. "The dynamic allocator beat the bench on
average across all worlds" is compatible with it being superb in trends and worse than inverse-vol
in a fused, high-volatility market -- and the desk does not trade the average, it trades the state
it is in. The fixture here is exactly that book: all its heat on one sleeve, which wins in `trend`
and loses in `fused`, and whose GLOBAL verdict is a fail. Per state, the answer is different in
each, and `select` is the meta-allocator that picks it:

    A*_t = argmax_A E[log W | X_t, A]

WHAT MUST NOT REGRESS:

  1. a per-state certificate exists beside the global one and never instead of it;
  2. `select` returns the dynamic book where it won and the winning CHALLENGER where it did not;
  3. a bucket too thin to judge gets NO verdict and falls back to the global one, saying so;
  4. the state id carries only ADMITTED dimensions -- an unjudged dimension may not condition;
  5. the state-conditioned heat target stays inside [floor, ceiling] and may only RAISE it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.heat_policy import (  # noqa: E402
    HEAT_HARD_CEILING,
    HEAT_TARGET,
    MIN_STATE_WORLDS,
    StateCurve,
    resolve,
    state_target,
)

from libs.portfolio import challengers  # noqa: E402
from libs.portfolio.allocator_proof import (  # noqa: E402
    admitted_now,
    buckets_from_worlds,
    certify,
    contest,
    select,
    state_id,
)
from libs.portfolio.robust_elog import SleeveEvidence, WorldConfig, Worlds  # noqa: E402

GOOD = {0.05: 0.0010, 0.10: 0.0018, 0.15: 0.0023, 0.20: 0.0025, 0.25: 0.0025, 0.30: 0.0024}


def _fixture(n_fused: int = 60, seed: int = 3) -> tuple[list[SleeveEvidence], Worlds, WorldConfig]:
    """A book whose edge is real in one regime and inverted in the other.

    `s0` earns in `trend` and bleeds in `fused`; `s1` earns only in `fused`. A dynamic book that
    is all-in on s0 is therefore right half the time and wrong the other half, which is precisely
    the shape a single global average hides.
    """
    rng = np.random.default_rng(seed)
    names = ["s0", "s1", "s2", "s3"]
    n_trend, rows = 60, 80
    mu = {"trend": np.array([0.006, 0.0, 0.0, 0.0]),
          "fused": np.array([-0.006, 0.006, 0.0, 0.0])}
    regimes = ["trend"] * n_trend + ["fused"] * n_fused
    r = np.stack([rng.normal(mu[g], 0.012, size=(rows, len(names))) for g in regimes]
                 ).astype(np.float32)
    worlds = Worlds(r=r, names=tuple(names), crisis=np.zeros(len(regimes), dtype=bool),
                    mu_draws=np.tile(mu["trend"], (len(regimes), 1)),
                    regimes=tuple(regimes), note="fixture population")
    ev = [SleeveEvidence(name=n, daily_r=rng.normal(0.001, 0.012, 300), family=f"f{i}")
          for i, n in enumerate(names)]
    return ev, worlds, WorldConfig(n_worlds=len(regimes), n_rows=rows, seed=seed)


# ------------------------------------------------------- 1 & 2. the per-state certificate
def test_the_certificate_is_per_state_and_selects_the_winner_in_each() -> None:
    ev, worlds, cfg = _fixture()
    out = contest(ev, {"s0": 0.20}, cfg=cfg, worlds=worlds)

    assert set(out["by_state"]) == {"regime=trend", "regime=fused"}
    trend, fused = out["by_state"]["regime=trend"], out["by_state"]["regime=fused"]
    assert trend["n_worlds"] == 60 and fused["n_worlds"] == 60
    assert trend["passed"] is True, trend["why"]
    assert fused["passed"] is False, fused["why"]
    # THE ARGUMENT FOR THE WHOLE MECHANISM: the average verdict is not either state's verdict.
    assert out["passed"] is False, out["why"]

    src, why = select(out, "regime=trend")
    assert src == "dynamic" and "won state" in why
    src, why = select(out, "regime=fused")
    assert src not in ("", "dynamic"), why
    assert src in out["books"], "select named a book the certificate does not carry"
    assert "LOST" in why
    # Every contested book was scored in every bucket, at the same equalised heat.
    assert set(fused["scores"]) == set(out["books"])


def test_the_state_id_prefix_still_matches_on_the_regime_the_worlds_know_about() -> None:
    """The desk's session moves faster than the world population is redrawn. A certificate keyed
    `regime=trend` is still the evidence about a trend in the London session -- but only when the
    match is unambiguous, so a wrong bucket can never be read as the right one."""
    ev, worlds, cfg = _fixture()
    out = contest(ev, {"s0": 0.20}, cfg=cfg, worlds=worlds)
    src, why = select(out, "session=london|event=quiet|regime=trend")
    assert src == "dynamic" and "matched on regime" in why


def test_a_thin_bucket_gets_no_verdict_and_falls_back_to_the_global_one() -> None:
    """Below MIN_STATE_WORLDS the bucket's CVaR is two draws wearing a distribution. No verdict
    is granted there and the reason names the shortfall (L1.28a: absence is never a pass)."""
    ev, worlds, cfg = _fixture(n_fused=MIN_STATE_WORLDS - 4)
    out = contest(ev, {"s0": 0.20}, cfg=cfg, worlds=worlds)
    assert "regime=fused" not in out["by_state"], "a thin bucket must not be judged"
    assert "regime=trend" in out["by_state"]
    src, why = select(out, "regime=fused")
    assert f"no bucket of >= {MIN_STATE_WORLDS} worlds" in why
    # The GLOBAL verdict is what stands in an unjudged state -- which is what the desk had before
    # any of this existed, and never a claim about the state itself.
    assert src == ("dynamic" if out["passed"] else out["best_baseline"]), why


def test_buckets_are_dropped_never_merged() -> None:
    _ev, worlds, _cfg = _fixture(n_fused=5)
    b = buckets_from_worlds(worlds, None)
    assert set(b) == {"regime=trend"}, "a thin bucket must not be folded into a residual state"
    assert len(b["regime=trend"]) == 60
    # An unlabelled population has no states at all, rather than one giant fake one.
    bare = Worlds(r=worlds.r, names=worlds.names, crisis=worlds.crisis,
                  mu_draws=worlds.mu_draws, regimes=(), note="")
    assert buckets_from_worlds(bare, None) == {}


def test_the_certificate_on_disk_carries_the_states_and_the_books(tmp_path) -> None:
    ev, worlds, cfg = _fixture()
    out = contest(ev, {"s0": 0.20}, cfg=cfg, worlds=worlds)
    p = certify(out, root=tmp_path, book={"s0": 0.20})
    doc = json.loads(p.read_text("utf-8"))
    assert doc["min_state_worlds"] == MIN_STATE_WORLDS
    assert set(doc["by_state"]) == {"regime=trend", "regime=fused"}
    assert doc["books"]["equal_weight"], "a selected challenger must be sizable, not just named"
    assert select(doc, "regime=trend")[0] == "dynamic"


def test_no_certificate_grants_no_authority() -> None:
    """Fail closed: the gateway's rule is that an unproven allocator may rank but not size."""
    for cert in (None, {}, "not a dict"):
        src, why = select(cert, "regime=trend")               # type: ignore[arg-type]
        assert src == "" and "no certificate" in why
    # A global pass with no per-state entry is still authority -- that is what the desk had.
    assert select({"passed": True, "why": "beat the bench"}, "regime=x")[0] == "dynamic"
    assert select({"passed": False, "best_baseline": "hrp", "why": "lost"}, None)[0] == "hrp"
    assert select({"passed": False, "best_baseline": "", "why": "lost"}, None)[0] == ""


# ------------------------------------------------------- 4. only admitted dimensions condition
def test_only_admitted_dimensions_reach_the_state_id(tmp_path) -> None:
    """A state dimension takes capital authority by passing `state_admission`, never by being
    plausible. An unreadable report withdraws every dimension rather than letting one through."""
    offered = {"session": "london", "weekday": "Tue"}
    (tmp_path / "desks" / "mt5" / "reports").mkdir(parents=True)
    (tmp_path / "desks" / "mt5" / "reports" / "STATE_ADMISSION.json").write_text(
        json.dumps({"admitted": ["session"], "graveyard": ["weekday"]}), encoding="utf-8")
    kept, why = admitted_now(tmp_path, offered)
    assert kept == {"session": "london"} and "admitted dimensions" in why
    assert state_id(kept, "trend") == "session=london|regime=trend"

    missing, why2 = admitted_now(tmp_path / "nowhere", offered)
    assert missing == {} and "unreadable" in why2
    assert state_id(missing, "trend") == "regime=trend"
    assert state_id(None, "") == "regime=unconditioned"


# ------------------------------------------------------- 5. H*_t inside the band
def _curve(peak: float) -> dict[float, float]:
    return {h: 0.002 - 0.02 * (h - peak) ** 2 for h in
            (0.05, 0.10, 0.15, 0.20, 0.225, 0.25, 0.275, 0.30, 0.35)}


def test_the_state_conditioned_target_is_the_argmax_inside_the_band() -> None:
    curves = {"regime=trend": StateCurve("regime=trend", _curve(0.27), 80),
              "regime=fused": StateCurve("regime=fused", _curve(0.05), 80)}
    hot, why, detail = state_target(curves, "regime=trend", floor=HEAT_TARGET,
                                    ceiling=HEAT_HARD_CEILING, fallback=GOOD)
    assert hot == pytest.approx(0.275) and detail["n_worlds"] == 80
    assert "H*_t" in why and "regime=trend" in why
    cold, _why, _d = state_target(curves, "regime=fused", floor=HEAT_TARGET,
                                  ceiling=HEAT_HARD_CEILING, fallback=GOOD)
    assert cold == pytest.approx(HEAT_TARGET), "a state that wants less still cannot go below 20%"
    for state in ("regime=trend", "regime=fused", None, "regime=unknown"):
        h, _w, _d2 = state_target(curves, state, floor=HEAT_TARGET, ceiling=HEAT_HARD_CEILING,
                                  fallback=GOOD)
        assert HEAT_TARGET - 1e-12 <= h <= HEAT_HARD_CEILING + 1e-12, state


def test_a_thin_state_bucket_uses_the_global_curve_and_says_which() -> None:
    thin = {"regime=trend": StateCurve("regime=trend", _curve(0.27), MIN_STATE_WORLDS - 1)}
    h, why, _d = state_target(thin, "regime=trend", floor=HEAT_TARGET,
                              ceiling=HEAT_HARD_CEILING, fallback=GOOD)
    assert "the global curve stands" in why and f"need {MIN_STATE_WORLDS}" in why
    assert h == pytest.approx(0.20), "GOOD peaks on its flat top at 20-25%; the band starts at 20%"


def test_the_state_may_raise_the_target_and_may_never_cut_it() -> None:
    """Growth governance in one test. Rule 2: a state whose curve says more, gets more. Rule 1: a
    state whose curve says less does NOT get to cut, because a reduction is a rail and this one
    has proved no dE[log W]."""
    up = {"regime=trend": StateCurve("regime=trend", _curve(0.27), 80)}
    down = {"regime=fused": StateCurve("regime=fused", _curve(0.02), 80)}
    v = resolve(0.21, curve=GOOD, state="regime=trend", curves=up)
    assert v.total_heat == pytest.approx(0.275) and v.binding == "state_growth"
    assert v.state == "regime=trend" and v.state_worlds == 80
    held = resolve(0.26, curve=GOOD, state="regime=fused", curves=down)
    assert held.total_heat == pytest.approx(0.26) and held.binding == "growth"
    # And the band is still the band, whatever the curve says.
    assert resolve(0.21, curve=GOOD, state="regime=trend",
                   curves={"regime=trend": StateCurve("regime=trend", _curve(0.9), 80)},
                   ).total_heat == pytest.approx(HEAT_HARD_CEILING)


def test_the_effective_ceiling_binds_the_state_conditioned_target_too() -> None:
    """A state that wants 27% on a book that is one bet still gets the floor: the two mechanisms
    compose in the safe direction, and the artifact names the one that bound."""
    up = {"regime=trend": StateCurve("regime=trend", _curve(0.27), 80)}
    one_bet = {"nominal": 0.28, "covariance": 0.27, "factor": 0.27, "tail": 0.27}
    v = resolve(0.21, curve=GOOD, state="regime=trend", curves=up, effective_heat=one_bet)
    assert v.total_heat == pytest.approx(HEAT_TARGET) and v.binding == "effective_ceiling"


# ------------------------------------------------------- the widened bench
def test_the_missing_challengers_are_on_the_bench_at_the_same_heat() -> None:
    """"Steal every portfolio challenger ... on identical worlds, costs and heat; if yours can't
    beat them it loses authority." NCO, max-diversification and plain mean-variance were the three
    the bench did not have."""
    ev, _worlds, _cfg = _fixture()
    books = challengers.all_books(ev, 0.20)
    for name in ("nco", "max_diversification", "mean_variance"):
        assert name in books, f"{name} could not be built on ordinary evidence"
        b = books[name]
        assert sum(b.values()) == pytest.approx(0.20, abs=1e-9), name
        assert all(v >= 0.0 for v in b.values()), f"{name} is not long-only"
    assert {"nco", "max_diversification", "mean_variance"} <= set(challengers.CHALLENGERS)


def test_mean_variance_is_not_just_kelly_under_another_name() -> None:
    """A duplicate challenger makes the contest look harder without making it harder."""
    rng = np.random.default_rng(5)
    ev = [SleeveEvidence(name=f"s{i}", daily_r=rng.normal(0.002 * (i + 1), 0.01 * (4 - i), 260),
                         family=f"f{i}") for i in range(4)]
    mv = challengers.mean_variance(ev, 0.20)
    k = challengers.kelly(ev, 0.20)
    assert max(abs(mv[n] - k[n]) for n in mv) > 1e-4, "mean-variance collapsed onto Kelly"


def test_a_single_sleeve_does_not_break_any_challenger() -> None:
    rng = np.random.default_rng(9)
    ev = [SleeveEvidence(name="only", daily_r=rng.normal(0.001, 0.01, 200), family="f")]
    for name, book in challengers.all_books(ev, 0.20).items():
        assert book == pytest.approx({"only": 0.20}), name


def test_the_contest_still_works_with_no_worlds_and_says_the_proof_is_global() -> None:
    ev, _worlds, _cfg = _fixture()
    out = contest(ev, {"s0": 0.10, "s1": 0.10}, cfg=WorldConfig(n_worlds=24, n_rows=48, seed=1))
    assert out["by_state"] == {} and "global only" in out["by_state_why"]
    assert isinstance(out["passed"], bool)
