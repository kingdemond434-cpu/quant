"""A state dimension conditions capital only until it is MEASURED worse.

The principal's rule: "no new regime variable gets capital authority merely because it sounds
sensible. It enters as information, gets PIT-tested, must improve forecast calibration or marginal
E[log W], and otherwise goes to the graveyard." Without a test, a state vector is an invitation to
overfit -- every dimension sounds sensible and every one slices the same finite evidence thinner.

The load-bearing properties: an informative dimension is found, a noise dimension is NOT admitted,
in-sample fit alone never passes, and a graveyard verdict actually removes access in the allocator
rather than appearing in a report nobody reads.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.regime.state_admission import (  # noqa: E402
    ADMIT,
    GRAVEYARD,
    MIN_TEST_TRADES,
    RETAIN_SHRUNK,
    UNJUDGED,
    Trade,
    admitted,
    build_labeller,
    judge,
    judge_all,
)
from research import state_admission_run as runner  # noqa: E402


def _trades(n: int, effect: float, noise: float = 1.0, seed: int = 0,
            n_sleeves: int = 4, dim: str = "d") -> list[Trade]:
    """`effect` is how much the bucket genuinely shifts the mean. 0.0 means the label is noise."""
    rng = np.random.default_rng(seed)
    buckets = ["a", "b", "c"]
    out = []
    for i in range(n):
        b = buckets[i % len(buckets)]
        sleeve = f"S{i % n_sleeves}"
        # A per-sleeve level the dimension must NOT be credited for explaining.
        base = 0.3 * (i % n_sleeves)
        shift = effect * (1.0 if b == "a" else -0.5)
        out.append(Trade(sleeve=sleeve, when=f"2026-01-{1 + i % 28:02d}T{i % 24:02d}:00:00+00:00",
                         r=base + shift + rng.normal(scale=noise), buckets={dim: b}))
    return out


def test_a_genuinely_informative_dimension_is_admitted():
    v = judge(_trades(2400, effect=1.2, noise=1.0, seed=1), "d")
    assert v.verdict == ADMIT, v
    assert v.mse_gain > 0
    assert v.t_deflated >= 2.0


def test_a_pure_noise_label_is_not_admitted():
    """The label carries nothing. Admitting it would be the whole failure mode."""
    v = judge(_trades(2400, effect=0.0, noise=1.0, seed=2), "d")
    assert v.verdict != ADMIT, v


def test_sleeve_effects_cannot_be_credited_to_the_dimension():
    """One profitable sleeve concentrated in one bucket must not make the label look informative."""
    rng = np.random.default_rng(3)
    out = []
    for i in range(2400):
        # Sleeve identity and bucket are perfectly confounded: the label adds NOTHING beyond it.
        k = i % 3
        out.append(Trade(sleeve=f"S{k}", when=f"2026-01-{1 + i % 28:02d}T00:00:00+00:00",
                         r=2.0 * k + rng.normal(scale=1.0), buckets={"d": "abc"[k]}))
    v = judge(out, "d")
    assert v.verdict != ADMIT, "the dimension was credited for the sleeve's own level"


def test_a_dimension_measured_worse_goes_to_the_graveyard():
    """A label anti-correlated with the outcome degrades prediction and must be removed."""
    rng = np.random.default_rng(4)
    out = []
    for i in range(3000):
        b = "ab"[i % 2]
        # The bucket mean FLIPS halfway through the record, so a mean fitted on the past
        # actively mispredicts the future. That is what a decayed state dimension looks like.
        sign = 1.0 if i < 1500 else -1.0
        shift = sign * (1.5 if b == "a" else -1.5)
        out.append(Trade(sleeve="S0", when=f"2026-{1 + i // 300:02d}-01T00:00:00+00:00",
                         r=shift + rng.normal(scale=0.6), buckets={"d": b}))
    v = judge(out, "d")
    assert v.verdict == GRAVEYARD, v
    assert v.t_paired <= -2.0


def test_thin_evidence_is_underpowered_and_says_so_rather_than_passing():
    v = judge(_trades(120, effect=2.0, seed=5), "d")
    assert v.verdict == RETAIN_SHRUNK
    assert "UNDERPOWERED" in v.why
    assert v.n_test < MIN_TEST_TRADES


def test_a_dimension_no_trade_carries_is_unjudged_not_passed():
    v = judge(_trades(500, effect=1.0, seed=6, dim="other"), "absent")
    assert v.verdict == UNJUDGED


def test_the_search_is_deflated_across_the_dimensions_tried():
    trades = _trades(2400, effect=0.35, noise=1.0, seed=7)
    alone = judge(trades, "d", dimensions_tried=1)
    among_many = judge(trades, "d", dimensions_tried=40)
    assert among_many.t_paired == pytest.approx(alone.t_paired)
    assert among_many.t_deflated < alone.t_deflated, "testing forty dimensions must cost something"


def test_every_dimension_is_charged_for_the_whole_search():
    trades = _trades(1800, effect=0.8, seed=8)
    for d in ("d",):
        trades = [Trade(t.sleeve, t.when, t.r, {**t.buckets, "e": t.buckets["d"]})
                  for t in trades]
    vs = judge_all(trades, ["d", "e"])
    assert all(v.dimensions_tried == 2 for v in vs.values())


def test_only_a_measured_failure_removes_access():
    vs = judge_all(_trades(2400, effect=0.0, seed=9), ["d"])
    # RETAIN_SHRUNK keeps its access: withdrawing it on a test with no power would swap one
    # unmeasured decision for another.
    assert "d" in admitted(vs)
    graveyarded = {"d": judge(_trades(200, 0.0, seed=1), "d")}
    object.__setattr__(graveyarded["d"], "verdict", GRAVEYARD)
    assert "d" not in admitted(graveyarded)


# ------------------------------------------------------------------------------------------
# The runner and the wiring
# ------------------------------------------------------------------------------------------

def test_the_desks_own_trades_produce_a_verdict():
    trades = runner.load_trades("shadow")
    assert trades, "no shadow ledger rows found at all"
    labelled, gaps = runner.label(trades, runner.DEFAULT_DIMENSIONS)
    assert labelled
    # `session` legitimately has no labeller off the trading box (no broker clock), and that must
    # be a recorded gap rather than a silent omission.
    assert set(gaps) <= set(runner.DEFAULT_DIMENSIONS)


def test_shadow_and_live_evidence_are_never_pooled():
    """A shadow trade paid the modelled cost; a live one paid a real spread."""
    import inspect
    src = inspect.getsource(runner.load_trades)
    assert "basis" in src
    assert "NEVER MIXED" in src


def test_the_report_names_what_is_barred_and_what_is_allowed(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "OUT", tmp_path / "adm.json")
    doc = runner.run()
    assert set(doc) >= {"verdicts", "admitted", "graveyard", "gaps", "rule", "n_trades"}
    written = json.loads((tmp_path / "adm.json").read_text("utf-8"))
    assert written["admitted"] == doc["admitted"]


def test_read_graveyard_fails_open_and_says_so(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "OUT", tmp_path / "missing.json")
    barred, why = runner.read_graveyard()
    assert barred == frozenset()
    assert "nothing is barred" in why


def test_read_graveyard_returns_what_the_report_barred(tmp_path, monkeypatch):
    p = tmp_path / "adm.json"
    p.write_text(json.dumps({"generated_utc": "t", "graveyard": ["session"], "admitted": []}),
                 "utf-8")
    monkeypatch.setattr(runner, "OUT", p)
    barred, _why = runner.read_graveyard()
    assert barred == frozenset({"session"})


def test_the_allocator_actually_obeys_the_graveyard():
    """A verdict that only appears in a report is not a verdict."""
    import inspect

    from research import pf_allocator

    src = inspect.getsource(pf_allocator._live_state)
    assert "read_graveyard" in src
    assert 'if "session" in barred' in src
    assert "return None, {}, off" in src


def test_the_daily_cycle_refreshes_the_verdicts_before_shadow_runs():
    from research import daily_cycle

    names = [n for n, _ in daily_cycle.STEPS]
    assert "state_admission" in names
    assert names.index("state_admission") < names.index("shadow")


def test_a_labeller_exists_for_every_default_dimension_or_the_gap_is_named():
    probe = Trade(sleeve="XAUUSD_session_range_breakout_asia",
                  when="2026-09-04T13:00:00+00:00", r=0.0)
    for d in runner.DEFAULT_DIMENSIONS:
        fn = build_labeller(d)
        if fn is None:
            continue
        assert isinstance(fn(probe), str)


def test_a_labeller_takes_the_trade_because_scope_needs_the_symbol():
    """`event` must know WHICH instrument, or a GBP release becomes AUDJPY's event too."""
    import inspect
    src = inspect.getsource(build_labeller)
    assert "Callable[[Trade], str]" in inspect.getsource(build_labeller).splitlines()[0] \
        or "t: Trade" in src


def test_a_dimension_with_one_bucket_is_unjudged_not_a_null_result():
    """t = 0.00 from a constant label reads as 'measured, no effect'. Nothing was measured.

    Seen live: `event` scored t=+0.00 over 336 predictions with buckets=1, because the calendar
    vintages the miner keeps span days while the shadow ledgers span months, so every trade was
    labelled NORMAL. Conditioning on a constant is arithmetically identical to not conditioning.
    """
    flat = [Trade(sleeve=f"S{i % 3}", when=f"2026-01-{1 + i % 28:02d}T00:00:00+00:00",
                  r=float(i % 5), buckets={"d": "always_the_same"}) for i in range(2400)]
    v = judge(flat, "d")
    assert v.verdict == UNJUDGED
    assert v.n_buckets < 2
    assert "does not cover the trades" in v.why


def test_the_event_dimension_is_reconstructed_at_the_trades_own_moment():
    """Labelling a January trade with today's calendar would test whether the present predicts
    the past, which every dimension would pass."""
    fn = build_labeller("event")
    if fn is None:
        pytest.skip("no calendar vintages on this host")
    old = Trade(sleeve="XAUUSD_session_range_breakout_asia", when="2020-01-02T03:00:00+00:00",
                r=0.1)
    label = fn(old)
    assert isinstance(label, str)
    # A trade from 2020 cannot be inside a 2026 release's shock window.
    assert label in {"", "NORMAL"}, label
