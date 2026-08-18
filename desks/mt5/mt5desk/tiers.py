"""Accelerated research, and the profile that decides whether to accelerate.
CONSTITUTION 220.

The objective named in 220.1 is VALIDATED SURVIVORS PER COMPUTE-HOUR, not
backtests per second. A faster engine producing the same survivors is worth
nothing; a faster engine producing WRONG survivors is worth less than nothing.

SO THIS DOES NOT CONTAIN A GPU ENGINE, AND THAT IS THE SECTION BEING FOLLOWED

220.5 is explicit: profile first, acceleration is justified by MEASURED
wall-time share and not by the availability of a technology. If backtesting is
not a large fraction of research wall time, the bottleneck is elsewhere and CUDA
is a distraction from it. Writing a CUDA kernel before the profile would violate
the section it claims to implement — and would be the more expensive mistake,
because an accelerator is permanent maintenance on a hot path.

What is here is therefore the two things the section actually requires before
any of that:

    PROFILE          where research wall time really goes, measured, with the
                     escalation ladder (Numba, C++, Rust, GPU, CUDA) gated on
                     the answer and stopping at the first tier that removes the
                     measured bottleneck.

    EQUIVALENCE      the regression that binds a cheap tier to the truth engine.
                     220.4: a lightning-fast wrong backtester would make this
                     operation worse.

THE ORDERING PROPERTY IS THE ONE THAT MATTERS

A cheap tier is permitted to be less precise. It is NEVER permitted to be
differently ordered: a hypothesis Tier C ranks above another must not be
eliminated by Tier A. Precision loss costs a little accuracy on survivors that
still survive; an ordering inversion silently discards the best candidate in the
funnel, and nothing downstream can recover it because it was never scored.

`rank_agreement` is therefore the gate, not correlation of returns. Two engines
can agree to four decimals on every backtest and still invert the top two
candidates, which is the only comparison the funnel actually performs.
"""
from __future__ import annotations

import math
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional, Sequence

TIERS_VERSION = "tiers-2026-08-18-a"

#: Wall-time share below which accelerating a stage is a distraction. If
#: backtesting is 15% of research time, an infinitely fast backtester buys 15%.
ACCELERATION_THRESHOLD = 0.40

#: Fraction of pairwise orderings a cheap tier must reproduce from the truth
#: engine. Not 1.0: a screening tier that never inverts ANY pair is a tier doing
#: the same work, which is why it would not be faster. The budget is for pairs
#: the truth engine itself ranks close together.
MIN_RANK_AGREEMENT = 0.95

#: Ranking pairs closer than this in the truth engine's own score are excluded
#: from the agreement test — inverting two candidates the reference cannot
#: separate is not an error of the cheap tier.
TIE_EPS = 1e-9


# ------------------------------------------------------------------ profile

@dataclass
class Stage:
    name: str
    seconds: float = 0.0
    calls: int = 0

    def add(self, dt: float) -> None:
        self.seconds += dt
        self.calls += 1


@dataclass
class Profile:
    """Where research wall time actually goes. 220.5's precondition."""
    stages: dict = field(default_factory=dict)

    @contextmanager
    def stage(self, name: str):
        t0 = time.perf_counter()
        try:
            yield
        finally:
            self.stages.setdefault(name, Stage(name)).add(time.perf_counter() - t0)

    @property
    def total(self) -> float:
        return sum(s.seconds for s in self.stages.values())

    def share(self, name: str) -> float:
        return (self.stages[name].seconds / self.total) if self.total > 0 and \
            name in self.stages else 0.0

    def bottleneck(self) -> Optional[Stage]:
        return max(self.stages.values(), key=lambda s: s.seconds, default=None)

    def verdict(self, threshold: float = ACCELERATION_THRESHOLD) -> dict:
        """Is acceleration justified, and of WHAT?

        The answer is usually no, and saying so is the point of the section. An
        accelerator on a stage that is 15% of wall time buys at most 15%, and
        costs permanent maintenance on a hot path forever.
        """
        b = self.bottleneck()
        if b is None or self.total <= 0:
            return {"accelerate": False, "stage": None,
                    "why": "nothing profiled; there is no measured bottleneck to "
                           "accelerate, and 220.5 forbids accelerating an "
                           "unmeasured one."}
        sh = self.share(b.name)
        if sh < threshold:
            return {
                "accelerate": False, "stage": b.name, "share": sh,
                "why": (f"the largest stage is {b.name} at {sh:.0%} of wall time, "
                        f"below the {threshold:.0%} bar. Making it INFINITELY "
                        f"fast buys {sh:.0%}. The bottleneck is elsewhere and an "
                        f"accelerator here is a distraction with permanent "
                        f"maintenance cost."),
                "ladder": [],
            }
        return {
            "accelerate": True, "stage": b.name, "share": sh,
            "why": (f"{b.name} is {sh:.0%} of measured wall time over {b.calls} "
                    f"call(s). Acceleration is justified BY MEASUREMENT."),
            # 220.5's order, cheapest engineering first, stopping at the first
            # tier that removes the measured bottleneck. Skipping ahead to CUDA
            # because it is interesting is the failure the ladder exists to stop.
            "ladder": ["numba", "c++", "rust", "gpu", "cuda"],
            "stop_rule": ("escalate one rung at a time and STOP at the first that "
                          "removes the bottleneck. Each rung is more engineering "
                          "cost forever, and the profile must be re-run after "
                          "each — removing one bottleneck reveals the next, and "
                          "it is frequently not the one you expected."),
        }

    def render(self) -> str:
        if not self.stages:
            return "PROFILE: nothing measured"
        rows = sorted(self.stages.values(), key=lambda s: -s.seconds)
        out = [f"RESEARCH PROFILE  ({TIERS_VERSION})  total {self.total:.3f}s"]
        for s in rows:
            out.append(f"  {s.name:<28}{s.seconds:>9.3f}s  "
                       f"{self.share(s.name):>6.1%}  {s.calls} call(s)")
        v = self.verdict()
        out += ["", f"  {'ACCELERATE: ' + str(v['stage']) if v['accelerate'] else 'DO NOT ACCELERATE'}",
                f"  {v['why']}"]
        if v.get("ladder"):
            out.append(f"  ladder: {' -> '.join(v['ladder'])}")
            out.append(f"  {v['stop_rule']}")
        return "\n".join(out)


# -------------------------------------------------------------- equivalence

@dataclass
class Equivalence:
    """Does a cheap tier agree with the truth engine well enough to screen?"""
    n: int
    max_abs_error: float
    mean_abs_error: float
    rank_agreement: float
    inversions: list
    tolerance: float
    passes: bool
    why: str

    def render(self) -> str:
        head = (f"TIER EQUIVALENCE  n={self.n}\n"
                f"  max |error|        {self.max_abs_error:.6g} "
                f"(tolerance {self.tolerance:g})\n"
                f"  mean |error|       {self.mean_abs_error:.6g}\n"
                f"  rank agreement     {self.rank_agreement:.4f} "
                f"(floor {MIN_RANK_AGREEMENT})")
        if self.inversions:
            head += f"\n  ORDERING INVERSIONS: {len(self.inversions)}"
            for a, b, ta, tb, ca, cb in self.inversions[:5]:
                head += (f"\n    truth ranks {a} ({ta:.6g}) above {b} ({tb:.6g}); "
                         f"cheap tier says {ca:.6g} vs {cb:.6g}")
        return f"{head}\n  {'PASSES' if self.passes else 'FAILS'}: {self.why}"


def rank_agreement(truth: Sequence[float], cheap: Sequence[float],
                   tie_eps: float = TIE_EPS) -> tuple:
    """Fraction of pairwise orderings the cheap tier reproduces.

    THE CHECK CORRELATION CANNOT MAKE. Two engines can agree to four decimals on
    every backtest and still invert the top two candidates — and inverting the
    top two is the only comparison the funnel actually performs. Pairs the truth
    engine cannot itself separate are excluded: inverting a tie is not an error.
    """
    n = min(len(truth), len(cheap))
    ok, total, inversions = 0, 0, []
    for i in range(n):
        for j in range(i + 1, n):
            d = truth[i] - truth[j]
            if abs(d) <= tie_eps:
                continue
            total += 1
            if (d > 0) == (cheap[i] - cheap[j] > 0):
                ok += 1
            else:
                inversions.append((i, j, truth[i], truth[j], cheap[i], cheap[j]))
    return (ok / total if total else 1.0), inversions


def check_equivalence(truth: Sequence[float], cheap: Sequence[float],
                      tolerance: float,
                      min_agreement: float = MIN_RANK_AGREEMENT) -> Equivalence:
    """220.4. A tier that drifts from the truth engine is DISABLED, not tuned.

    Two independent gates, and the ordering one is the gate that matters. A
    cheap tier is permitted to be less precise; it is never permitted to be
    differently ordered, because precision loss costs accuracy on survivors that
    still survive, while an ordering inversion silently discards the best
    candidate in the funnel and nothing downstream can recover it — it was never
    scored.
    """
    n = min(len(truth), len(cheap))
    if n == 0:
        return Equivalence(0, 0.0, 0.0, 0.0, [], tolerance, False,
                           "nothing to compare; a tier with no regression corpus "
                           "is an unvalidated tier and may not screen.")
    errs = [abs(float(truth[i]) - float(cheap[i])) for i in range(n)]
    mx, mean = max(errs), sum(errs) / n
    agree, inv = rank_agreement(truth[:n], cheap[:n])
    if not math.isfinite(mx):
        return Equivalence(n, mx, mean, agree, inv, tolerance, False,
                           "the cheap tier produced a non-finite result")
    if inv:
        return Equivalence(
            n, mx, mean, agree, inv, tolerance, False,
            f"{len(inv)} ordering inversion(s): the cheap tier ranks a candidate "
            f"below one the truth engine ranks above it. That is not a precision "
            f"loss, it is a different answer, and in a funnel it means the better "
            f"candidate is eliminated before anything expensive ever scores it. "
            f"DISABLE this tier until it agrees again — do not tune the "
            f"tolerance.")
    if agree < min_agreement:
        return Equivalence(n, mx, mean, agree, inv, tolerance, False,
                           f"rank agreement {agree:.4f} below {min_agreement}")
    if mx > tolerance:
        return Equivalence(
            n, mx, mean, agree, inv, tolerance, False,
            f"max error {mx:.6g} exceeds the stated tolerance {tolerance:g}. The "
            f"ordering survives, so this is a precision failure rather than a "
            f"correctness one — but the tolerance is a number that was justified, "
            f"and moving it to fit the result is how a tier drifts.")
    return Equivalence(n, mx, mean, agree, inv, tolerance, True,
                       f"ordering preserved on all {n} candidates and max error "
                       f"{mx:.6g} within the stated {tolerance:g}")


# ------------------------------------------------------------------ the funnel

@dataclass
class Funnel:
    """220.3. An expensive simulator is never run on what a cheap one can kill."""
    stages: list = field(default_factory=list)     # (name, keep_n, cost_per_item)

    def plan(self, n_start: int) -> dict:
        n, rows, total = n_start, [], 0.0
        for name, keep, cost in self.stages:
            spend = n * cost
            total += spend
            rows.append({"stage": name, "evaluated": n, "cost": spend,
                         "survivors": min(keep, n)})
            n = min(keep, n)
        return {"rows": rows, "total_cost": total, "final": n,
                "note": ("cost is in whatever unit the caller used per item. The "
                         "point is the SHAPE: the expensive stage must see a "
                         "small number, or the funnel is decorative.")}

    def render(self, n_start: int) -> str:
        p = self.plan(n_start)
        out = [f"FUNNEL from {n_start:,}"]
        for r in p["rows"]:
            out.append(f"  {r['stage']:<22}{r['evaluated']:>12,} evaluated "
                       f"-> {r['survivors']:>8,} kept   cost {r['cost']:,.1f}")
        out.append(f"  total cost {p['total_cost']:,.1f}, {p['final']:,} forward "
                   f"candidate(s)")
        out.append(f"  {p['note']}")
        return "\n".join(out)
