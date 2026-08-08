"""GATE POWER — a validator that has never been measured against a KNOWN edge is uncalibrated.

WHY THIS IS URGENT RATHER THAN TIDY. The first complete sweep killed 750 of 762 screen-clearing
cells at one gate, F3 WALK-FORWARD SIGN. Read from the implementation rather than the docs, F3's
rule is:

    a cell dies unless BOTH walk-forward arms are net-positive

That is a strong rule and it is strong for a good reason: two NEGATIVE arms share a sign and would
pass a naive sign test while describing a cell that loses money in both halves. But the same rule
makes a genuinely REGIME-CONDITIONAL mechanism -- positive in one half, absent in the other --
indistinguishable from noise. If conditional alpha exists in crypto, and the desk's own funding /
liquidation / regime research assumes it does, then this gate has a false-negative rate that
matters economically and nobody has ever measured it.

**FALSE POSITIVES AND FALSE NEGATIVES ARE NOT SYMMETRIC IN HOW THEY ANNOUNCE THEMSELVES.** A gate
that is too loose ships a phantom edge, and the rails, the forward clock and the P&L all eventually
say so. A gate that is too tight destroys real alpha silently, with every board green, forever. The
desk measures the first continuously and has never measured the second.

MEASURED, 2026-08-08, 300 trials x 1,200 observations per point::

    planted effect      0.0    0.01   0.02   0.05   0.10   0.20   0.40
    STABLE edge kept   0.23   0.37   0.45   0.78   1.00   1.00   1.00
    CONDITIONAL kept   0.24   0.32   0.35   0.44   0.50   0.55   0.51

**THE CONDITIONAL ROW PLATEAUS AT ~50% AND NO EFFECT SIZE FIXES IT.** That is not a power problem
that more data would solve -- it is arithmetic. A conditional edge has NO effect in its second arm,
so that arm is pure noise and lands positive by chance about half the time. F3 therefore discards
roughly half of all conditional mechanisms however strong they are, and the desk cannot buy its way
out with a longer tape. A stable edge of the same size is kept 100% of the time.

TWO CAVEATS, because this number is easy to misquote. The 23% at effect 0 is F3's false-positive
rate IN ISOLATION, not the sweep's -- in the pipeline F3 runs only on cells that already cleared
the deflated F1/F2 screen, and the deflation is what carries multiplicity control. And a 50% keep
rate on conditional edges is a statement about this SHAPE of truth, not a claim that half the 750
kills were conditional; what fraction of them are is an empirical question the kill audit answers
from the retained cells.

SO THIS PLANTS KNOWN EDGES AND COUNTS HOW MANY SURVIVE. Power is not an opinion about a threshold;
it is the fraction of edges of a KNOWN size that a gate lets through, and it is measurable in
minutes against synthetic series whose ground truth is constructed rather than inferred.

**MEASURING A GATE IS NOT LICENCE TO LOOSEN IT, and the module refuses to make that easy.** No
function here returns a recommended threshold. A gate changes only when a controlled experiment
shows a DIFFERENT rule has better expected survivor quality -- never because a lot of cells died,
which is the argument this evidence will be most tempting to use for.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

__all__ = [
    "GateResult",
    "PowerCurve",
    "f3_both_arms_positive",
    "plant",
    "power_curve",
    "run_controls",
    "summarise",
]

#: Edge sizes swept when no explicit grid is given, in units of per-observation Sharpe. Spans
#: "indistinguishable from noise" to "obvious", because the interesting region is where a real but
#: modest edge sits -- which is where most genuine crypto alpha lives after costs.
DEFAULT_EFFECTS: tuple[float, ...] = (0.0, 0.01, 0.02, 0.05, 0.10, 0.20, 0.40)


@dataclass(frozen=True)
class GateResult:
    """One gate's verdict on one series pair. `passed` is the gate's own answer, nothing more."""

    passed: bool
    detail: str = ""


@dataclass(frozen=True)
class PowerCurve:
    """A gate's pass rate as a function of TRUE effect size, with the null at effect 0."""

    gate: str
    effects: tuple[float, ...]
    pass_rates: tuple[float, ...]
    n_trials: int
    n_obs: int
    #: Pass rate at effect 0 -- the false-POSITIVE rate. A gate with 0.0 here is not necessarily
    #: good; it may simply reject everything.
    false_positive_rate: float
    kind: str = "stable"

    @property
    def half_power_effect(self) -> float | None:
        """Smallest planted effect the gate passes at least half the time. None if never.

        None is the finding, not a formatting problem: a gate that never reaches 50% power over
        the swept range cannot detect any edge in that range, and its kill counts say nothing
        about whether alpha was present.
        """
        for e, p in zip(self.effects, self.pass_rates, strict=True):
            if e > 0 and p >= 0.5:
                return e
        return None

    def false_negative_rate(self, effect: float) -> float | None:
        """1 - power at a given planted effect. None when that effect was not swept."""
        for e, p in zip(self.effects, self.pass_rates, strict=True):
            if abs(e - effect) < 1e-12:
                return 1.0 - p
        return None


def plant(rng: np.random.Generator, n: int, effect: float, *, kind: str = "stable",
          ) -> tuple[np.ndarray, np.ndarray]:
    """(in-sample arm, out-of-sample arm) with a KNOWN planted effect.

    `kind` is the shape of the truth, and the shapes are the point:

      stable       the effect is present in both halves -- what F3 is designed to keep
      conditional  present in the FIRST half only, absent (not reversed) in the second. A real
                   regime-dependent mechanism, and precisely what "both arms positive" refuses
      transient    present early and decaying to nothing -- a decaying-but-real edge
      null         no effect anywhere, the false-positive control
    """
    half = max(1, n // 2)
    noise_a = rng.normal(0.0, 1.0, half)
    noise_b = rng.normal(0.0, 1.0, half)
    if kind == "null" or effect <= 0:
        return noise_a, noise_b
    if kind == "stable":
        return noise_a + effect, noise_b + effect
    if kind == "conditional":
        # ABSENT in the second arm, not reversed. A reversed arm would be a different claim --
        # that the mechanism inverts -- and conflating the two would flatter the gate, because
        # rejecting an inverting mechanism is defensible and rejecting an absent one is the
        # false negative under investigation.
        return noise_a + effect, noise_b
    if kind == "transient":
        decay = np.linspace(1.0, 0.0, half)
        return noise_a + effect, noise_b + effect * decay
    raise ValueError(f"unknown planted kind {kind!r}")


def f3_both_arms_positive(is_arm: np.ndarray, oos_arm: np.ndarray) -> GateResult:
    """THE GATE AS IMPLEMENTED IN `run_full_sweep`, reproduced exactly.

    Transcribed from the sweep rather than from its documentation, because the whole exercise is
    worthless if it calibrates a rule the desk does not actually run. The sweep's condition is
    `r_is.net_bps <= 0 or sign(r_is) != sign(r_oos)`; on arm MEANS that is exactly "both arms
    strictly positive".
    """
    a, b = float(np.mean(is_arm)), float(np.mean(oos_arm))
    ok = a > 0.0 and b > 0.0
    return GateResult(ok, f"IS {a:+.4f} / OOS {b:+.4f}")


def power_curve(gate: Callable[[np.ndarray, np.ndarray], GateResult], *, name: str,
                kind: str = "stable", effects: tuple[float, ...] = DEFAULT_EFFECTS,
                n_obs: int = 2000, n_trials: int = 400, seed: int = 0) -> PowerCurve:
    """Pass rate at each planted effect size. The null (effect 0) gives the false-positive rate."""
    rng = np.random.default_rng(seed)
    rates: list[float] = []
    for e in effects:
        k = "null" if e <= 0 else kind
        passes = sum(gate(*plant(rng, n_obs, e, kind=k)).passed for _ in range(n_trials))
        rates.append(passes / n_trials)
    return PowerCurve(gate=name, effects=tuple(effects), pass_rates=tuple(rates),
                      n_trials=n_trials, n_obs=n_obs, false_positive_rate=rates[0], kind=kind)


def run_controls(*, n_obs: int = 2000, n_trials: int = 400, seed: int = 0,
                 ) -> dict[str, PowerCurve]:
    """F3 against every truth shape. THE COMPARISON IS THE RESULT, not any single curve.

    A gate that keeps stable edges and drops conditional ones of the SAME size is not merely
    strict -- it is selecting on a property the desk never intended to select on, and the two
    curves side by side are what make that visible rather than arguable.
    """
    return {kind: power_curve(f3_both_arms_positive, name="F3_BOTH_ARMS_POSITIVE", kind=kind,
                              n_obs=n_obs, n_trials=n_trials, seed=seed + i)
            for i, kind in enumerate(("stable", "conditional", "transient"))}


def summarise(curves: dict[str, PowerCurve]) -> dict[str, object]:
    """Report shape. Leads with the CONDITIONAL/STABLE gap, which is the economic question."""
    stable = curves.get("stable")
    cond = curves.get("conditional")
    rows = {k: {"effects": list(c.effects), "pass_rates": list(c.pass_rates),
                "false_positive_rate": c.false_positive_rate,
                "half_power_effect": c.half_power_effect} for k, c in curves.items()}
    head = "UNMEASURED -- no curves"
    if stable and cond:
        gaps = [(e, s - c) for e, s, c in
                zip(stable.effects, stable.pass_rates, cond.pass_rates, strict=True) if e > 0]
        worst_e, worst_gap = max(gaps, key=lambda t: t[1]) if gaps else (0.0, 0.0)
        s_at = dict(zip(stable.effects, stable.pass_rates, strict=True))[worst_e]
        c_at = dict(zip(cond.effects, cond.pass_rates, strict=True))[worst_e]
        # THE PLATEAU IS THE HEADLINE WHEN IT APPEARS. A gap that persists at the largest swept
        # effect is structural -- more data cannot close it -- and that is a different and much
        # more serious finding than a gate merely being underpowered.
        tail_gap = gaps[-1][1] if gaps else 0.0
        if tail_gap > 0.2:
            c_tail, s_tail = cond.pass_rates[-1], stable.pass_rates[-1]
            head = (
                f"F3 keeps {c_tail:.0%} of CONDITIONAL edges even at the LARGEST swept effect "
                f"({cond.effects[-1]:g}), against {s_tail:.0%} for stable edges of the same "
                "size. The gap does not close with effect size, so it "
                "is ARITHMETIC, not power: a conditional edge's second arm is noise and lands "
                "positive by chance about half the time. More tape cannot fix it")
            return {"curves": rows, "headline": head, "structural_gap": round(tail_gap, 4),
                    "note": ("Power is measured, never traded on. No function here returns a "
                             "recommended threshold: a gate changes only when a controlled "
                             "experiment shows a DIFFERENT rule has better expected survivor "
                             "quality -- never because many cells died.")}
        head = (
            f"F3 false-positive rate {stable.false_positive_rate:.1%} on pure noise. At effect "
            f"{worst_e:g} it keeps {s_at:.0%} of STABLE edges and {c_at:.0%} of CONDITIONAL edges "
            f"of the SAME size -- a {worst_gap:.0%} gap that is a property of the RULE, not of "
            "the market")
    return {
        "curves": rows, "headline": head,
        "note": ("Power is measured, never traded on. No function here returns a recommended "
                 "threshold: a gate changes only when a controlled experiment shows a DIFFERENT "
                 "rule has better expected survivor quality -- never because many cells died, "
                 "which is the argument this evidence is most tempting to misuse for."),
    }
