"""Decision replay: freeze -> thaw is exact, replay reproduces, every channel reaches the book.

The fixture is a five-sleeve synthetic book on a deliberately small population (48 worlds x 128
rows) so the whole file runs in seconds. Each sleeve is FLAT most days, like every real one (see
`test_robust_elog._sleeve`): a sleeve that trades every day makes a 30% book ruinous and the test
measures the fixture, not the allocator.

THE TWO STRICT XFAILS ARE FINDINGS, NOT GAPS IN THE HARNESS. They pin two places where
`robust_elog` turns a MISSING critical input into a favourable number today. When that is fixed
they XPASS, the run goes red, and whoever fixed it turns them into plain tests.
"""
from __future__ import annotations

import dataclasses
from pathlib import Path

import numpy as np
import pytest

from libs.portfolio import decision_replay as dr
from libs.portfolio.robust_elog import (
    SleeveEvidence,
    WorldConfig,
    optimise,
    sample_worlds,
    score_book,
)

N_DAYS = 600
#: Odd days are "storm", even days "calm"; sleeve A is three times as volatile in a storm.
LABELS = tuple("storm" if i % 2 else "calm" for i in range(N_DAYS))


def _sleeve(name: str, mu: float, sd: float, seed: int, activity: float = 0.2,
            storm_vol: float = 1.0, **kw: object) -> SleeveEvidence:
    rng = np.random.default_rng(seed)
    r = rng.normal(mu / activity, sd, N_DAYS) * (rng.random(N_DAYS) < activity)
    if storm_vol != 1.0:
        storm = np.array([lab == "storm" for lab in LABELS]) & (r != 0.0)
        m = float(r[storm].mean())
        r[storm] = m + (r[storm] - m) * storm_vol
    return SleeveEvidence(name=name, daily_r=r, **kw)  # type: ignore[arg-type]


def _book() -> list[SleeveEvidence]:
    return [
        _sleeve("A", 0.08, 1.0, 1, symbol="XAUUSD", family="trend", cost_bias_r=0.01,
                decay_prob_i=0.6, macro_w=np.linspace(0.0, 1.0, N_DAYS),
                factor_load=(0.3, 0.1), factor_resid_var=0.5, storm_vol=1.8),
        _sleeve("B", 0.07, 1.0, 2, family="carry"),
        _sleeve("C", 0.08, 1.2, 3, family="mr"),
        _sleeve("D", 0.05, 0.8, 4, family="brk", factor_load=(0.2, 0.3), factor_resid_var=0.5),
        _sleeve("E", 0.06, 1.0, 5, family="sess"),
    ]


CFG = WorldConfig(n_worlds=48, n_rows=128, seed=3, crisis_prob=0.15, regime_labels=LABELS,
                  regime_probs=(("calm", 0.5), ("storm", 0.5)))
HELD = {"A": 0.05, "B": 0.05}


def _freeze(dir_: Path, *, warm: bool = False, decision_id: str = "d1",
            **kw: object) -> Path:
    ev = _book()
    worlds = sample_worlds(ev, CFG)
    solve: dict[str, object] = {"hard_cap": 0.3}
    if warm:
        # THE PRODUCTION CONFIGURATION: pf_allocator warm-starts every solve from the held book.
        solve["warm_start"] = optimise(ev, cfg=CFG, worlds=worlds, hard_cap=0.3).heat
    res = optimise(ev, cfg=CFG, worlds=worlds, **solve)  # type: ignore[arg-type]
    return dr.freeze(dir_, ev=ev, cfg=CFG, worlds=worlds, held_book=HELD, solve_kwargs=solve,
                     decision_id=decision_id, meta={"mode": "test", "fingerprint": "abc"},
                     result=res, **kw)  # type: ignore[arg-type]


@pytest.fixture(scope="module")
def snap(tmp_path_factory: pytest.TempPathFactory) -> dr.Snapshot:
    return dr.thaw(_freeze(tmp_path_factory.mktemp("snap")))


@pytest.fixture(scope="module")
def warm_snap(tmp_path_factory: pytest.TempPathFactory) -> dr.Snapshot:
    return dr.thaw(_freeze(tmp_path_factory.mktemp("warm"), warm=True, decision_id="w1"))


# ------------------------------------------------------------------------------ freeze / thaw

def test_round_trip_is_byte_equal(snap: dr.Snapshot, tmp_path: Path) -> None:
    ev = _book()
    assert len(snap.ev) == len(ev)
    for a, b in zip(ev, snap.ev, strict=True):
        for f in dataclasses.fields(a):
            va, vb = getattr(a, f.name), getattr(b, f.name)
            if isinstance(va, np.ndarray):
                assert va.dtype == vb.dtype and va.shape == vb.shape
                assert va.tobytes() == vb.tobytes(), f.name
            else:
                assert va == vb and type(va) is type(vb), f.name
    assert snap.cfg == CFG
    w = sample_worlds(ev, CFG)
    assert snap.worlds.r.tobytes() == w.r.tobytes() and snap.worlds.r.dtype == w.r.dtype
    assert snap.worlds.crisis.tobytes() == w.crisis.tobytes()
    assert snap.worlds.mu_draws.tobytes() == w.mu_draws.tobytes()
    assert snap.worlds.names == w.names and snap.worlds.regimes == w.regimes
    assert snap.held_book == HELD and snap.solve_kwargs == {"hard_cap": 0.3}
    assert snap.meta == {"mode": "test", "fingerprint": "abc"}
    # Re-freezing what was thawed is the SAME decision: identical digest.
    again = dr.thaw(dr.freeze(tmp_path, ev=snap.ev, cfg=snap.cfg, worlds=snap.worlds,
                              held_book=snap.held_book, solve_kwargs=snap.solve_kwargs,
                              decision_id=snap.decision_id, meta=snap.meta,
                              result=snap.recorded))
    assert again.sha256 == snap.sha256 and len(snap.sha256) == 64


def test_a_tampered_snapshot_is_refused(tmp_path: Path) -> None:
    p = _freeze(tmp_path)
    with np.load(p, allow_pickle=False) as z:
        raw = {k: np.array(z[k]) for k in z.files}
    raw["ev1__daily_r"] = raw["ev1__daily_r"] * 1.01          # one sleeve's history, edited
    with p.open("wb") as fh:
        np.savez(fh, **raw)  # type: ignore[arg-type]
    with pytest.raises(dr.SnapshotCorrupt):
        dr.thaw(p)


def test_disk_is_bounded_and_the_newest_survives(tmp_path: Path) -> None:
    ev = _book()[:2]
    cfg = dataclasses.replace(CFG, regime_labels=(), regime_probs=())
    w = sample_worlds(ev, cfg)
    last = None
    for i in range(5):
        last = dr.freeze(tmp_path, ev=ev, cfg=cfg, worlds=w, held_book={},
                         solve_kwargs={"hard_cap": 0.3}, decision_id=f"x{i}", keep=3)
    left = sorted(tmp_path.glob("decision-*.npz"))
    assert len(left) == 3 and last in left
    # A byte bound smaller than one snapshot still keeps the decision just made.
    newest = dr.freeze(tmp_path, ev=ev, cfg=cfg, worlds=w, held_book={},
                       solve_kwargs={"hard_cap": 0.3}, decision_id="tiny", max_bytes=1)
    assert sorted(tmp_path.glob("decision-*.npz")) == [newest]


def test_solve_kwargs_are_validated(tmp_path: Path) -> None:
    ev = _book()[:2]
    w = sample_worlds(ev, CFG)
    with pytest.raises(ValueError, match="unknown solve kwargs"):
        dr.freeze(tmp_path, ev=ev, cfg=CFG, worlds=w, held_book={},
                  solve_kwargs={"hard_cap": 0.3, "stepsize": 1}, decision_id="bad")
    s = dr.thaw(dr.freeze(tmp_path, ev=ev, cfg=CFG, worlds=w, held_book={},
                          solve_kwargs={"hard_cap": 0.3, "deadline": 1.0}, decision_id="dl"))
    assert "deadline" not in s.solve_kwargs                  # the clock is not replayed


# ------------------------------------------------------------------------------------- replay

def test_replay_reproduces_the_recorded_decision(snap: dr.Snapshot) -> None:
    out = dr.replay(snap)
    assert out["basis"] == "recorded"
    assert out["identical"] and out["equivalent"]
    assert out["total_heat_replayed"] > 0.05                  # a funded book, not a vacuous one


def test_replay_scores_holding_on_the_same_worlds(snap: dr.Snapshot) -> None:
    out = dr.replay(snap)
    direct = score_book(snap.ev, HELD, cfg=snap.cfg, worlds=snap.worlds)
    assert out["hold"]["robust_score"] == direct["robust_score"]
    assert out["decision_minus_hold"] == pytest.approx(
        out["score_recorded"] - direct["robust_score"])
    # Optimal against a feasible book on the same worlds: the decision must not lose to holding.
    assert out["decision_beats_hold"]


def test_replay_catches_a_book_that_was_not_what_the_inputs_decide(snap: dr.Snapshot) -> None:
    rec = dict(snap.recorded or {})
    heat = dict(rec["heat"])
    heat["B"] = heat["B"] + 0.01
    out = dr.replay(dataclasses.replace(snap, recorded={**rec, "heat": heat}))
    assert not out["equivalent"] and out["heat_l1"] == pytest.approx(0.01)


def test_replay_without_a_recorded_book_proves_determinism(snap: dr.Snapshot) -> None:
    out = dr.replay(dataclasses.replace(snap, recorded=None))
    assert out["basis"] == "rerun" and out["identical"]


# ------------------------------------------------------------------------------- perturbations

@pytest.mark.parametrize(("channel", "size", "sleeve"), [
    ("mean", 0.10, "B"),          # better posterior mean -> more heat on that sleeve
    ("volatility", 0.50, "B"),    # higher dispersion (GARCH) -> less
    ("decay", 0.30, "B"),         # higher decay probability -> less
    ("cost", 0.05, "B"),          # worse measured cost -> less
    ("crisis", 0.40, None),       # crisis worlds more fused -> less total heat
    ("dependence", 0.50, None),   # a common factor across sleeves -> less total heat
])
def test_each_channel_moves_the_book_the_expected_way(snap: dr.Snapshot, channel: str,
                                                      size: float, sleeve: str | None) -> None:
    out = dr.perturb(snap, channel, size, sleeve=sleeve)
    assert out["frozen_worlds_reproduce"]
    assert out["moved"], f"{channel} did not reach the decision: {out['per_sleeve_delta']}"
    assert out["direction_ok"], f"{channel} moved the wrong way: {out['focus_delta']:+.5f}"
    assert out["expected_sign"] * out["focus_delta"] > dr.MATERIAL_TURNOVER


def test_regime_mass_toward_a_storm_cuts_the_storm_sensitive_sleeve(snap: dr.Snapshot) -> None:
    out = dr.perturb(snap, "regime", 0.8, regime="storm")
    assert out["moved"]
    assert out["per_sleeve_delta"]["A"] < -dr.MATERIAL_TURNOVER


def test_noise_does_not_churn_the_warm_started_book(warm_snap: dr.Snapshot) -> None:
    """ALLOC-19 in the production configuration (warm start from the held book). The COLD-start
    solve on this fixture does churn -- 0.7% heat L1 on 1e-6 noise, a multistart tie flipping on
    a 2e-7 score difference inside a 6e-4 certificate gap -- see the module report."""
    for seed in (1, 2, 3):
        out = dr.perturb(warm_snap, "noise", 1e-6, seed=seed)
        assert out["heat_l1"] <= dr.MATERIAL_TURNOVER and out["direction_ok"]


def test_unknown_channel_is_refused(snap: dr.Snapshot) -> None:
    with pytest.raises(KeyError):
        dr.perturb(snap, "vibes", 0.1)


# --------------------------------------------------------------------------------- missingness

#: (input, sleeve) pairs where missing IS handled safely today. `cost_r` fails CLOSED and
#: book-wide: one NaN cost poisons every world (nan P&L reads as ruin), so the whole book goes to
#: zero -- safe, but a one-sleeve fault standing the desk down is its own finding. `macro_w` and
#: `regime_probs` fall back to NEUTRAL (no tilt, uniform regimes), which holds here and would
#: not where the frozen tilt or regime mix was unfavourable to the sleeve.
HOLDS = (("cost_r", "A"), ("cost_r", "B"), ("macro_w", "A"), ("regime_probs", "A"))


@pytest.fixture(scope="module")
def missing(snap: dr.Snapshot) -> dict[tuple[str, str], dict[str, object]]:
    out: dict[tuple[str, str], dict[str, object]] = {}
    for sleeve in ("A", "B", "D"):
        for r in dr.missing_is_not_zero(snap, sleeve=sleeve)["rows"]:
            out[(str(r["input"]), sleeve)] = r
    return out


@pytest.mark.parametrize(("inp", "sleeve"), HOLDS)
def test_missing_input_never_adds_heat(missing: dict[tuple[str, str], dict[str, object]],
                                       inp: str, sleeve: str) -> None:
    row = missing[(inp, sleeve)]
    assert row["applicable"], f"{inp} was vacuous on this fixture"
    assert not row["raised_heat"], row


def test_harness_reports_violations(snap: dr.Snapshot) -> None:
    out = dr.missing_is_not_zero(snap, sleeve="A")
    assert out["violations"] == [r["input"] for r in out["rows"]
                                 if r["applicable"] and r["raised_heat"]]
    assert out["ok"] is (not out["violations"])


# THE FINDINGS. Each is a place where robust_elog turns a missing critical input into a favourable
# number today, measured on this fixture. Strict: a fix makes them XPASS and the run goes red.

@pytest.mark.xfail(strict=True, reason=(
    "FINDING: sample_worlds reads cost_bias_r through max(0.0, x), and max(0.0, nan) is 0.0 -- "
    "an unmeasured fill cost becomes a FREE fill and the sleeve gains heat"))
def test_missing_cost_bias_is_not_a_free_fill(
        missing: dict[tuple[str, str], dict[str, object]]) -> None:
    assert not missing[("cost_bias_r", "A")]["raised_heat"]


@pytest.mark.xfail(strict=True, reason=(
    "FINDING: decay_prob_of maps a non-finite decay_prob_i to the BLANKET; for a sleeve measured "
    "above the blanket (0.6 vs 0.3) a corrupt value is relief and the sleeve gains heat"))
def test_missing_decay_is_not_relief(missing: dict[tuple[str, str], dict[str, object]]) -> None:
    assert not missing[("decay_prob_i", "A")]["raised_heat"]


def test_wholly_missing_history_is_not_riskless(
        missing: dict[tuple[str, str], dict[str, object]]) -> None:
    assert not missing[("daily_r_missing", "B")]["raised_heat"]


@pytest.mark.xfail(strict=True, reason=(
    "FINDING: a STALE tail (feed stopped, last 25% NaN) is zero-filled as FLAT days in the joint "
    "bootstrap, understating the sleeve's world variance; nothing in robust_elog knows the "
    "difference between not-yet-born and not-reported (D: 4.3% -> 10.0% heat)"))
def test_stale_history_does_not_buy_heat(
        missing: dict[tuple[str, str], dict[str, object]]) -> None:
    assert not missing[("daily_r_stale", "D")]["raised_heat"]


@pytest.mark.xfail(strict=False, reason=(
    "FINDING (small): NaN factor loadings make _structured_corr's target 0 for the pair, i.e. "
    "independent -- the redundancy charge drops and the sleeve gains ~2e-4 heat here"))
def test_missing_loadings_are_not_independence(
        missing: dict[tuple[str, str], dict[str, object]]) -> None:
    assert not missing[("factor_load", "A")]["raised_heat"]
