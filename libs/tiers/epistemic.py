"""THE EPISTEMIC UNCERTAINTY ENGINE (Tier S layer 37).

Every important quantity the desk publishes carries one of five labels, and the label is derived
from the evidence behind the number, never asserted by the organ that computed it:

    KNOWN       measured directly, enough observations, interval tight relative to the decision
    ESTIMATED   a statistical estimate whose interval does not straddle the decision threshold
    WEAK        an estimate whose interval straddles the threshold, or a small sample
    UNKNOWN     no usable evidence yet (absent, stale, or n below the minimum)
    UNKNOWABLE  the current data cannot answer it at any sample size the desk can reach
                (e.g. the minimum track-record length exceeds the history available)

`decide()` is the single place a yes/no is drawn from a labelled quantity, and it has a third
answer: INSUFFICIENT_EVIDENCE. An organ that needs a boolean and gets that answer must treat it as
"not decided", which is not the same as "no" -- UNMEASURED is a verdict (L1.28a), never a zero.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class Label(StrEnum):
    KNOWN = "KNOWN"
    ESTIMATED = "ESTIMATED"
    WEAK = "WEAK"
    UNKNOWN = "UNKNOWN"
    UNKNOWABLE = "UNKNOWABLE"


class Decision(StrEnum):
    YES = "YES"
    NO = "NO"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


#: Below this many observations nothing is better than WEAK, whatever its interval says.
MIN_N = 20
#: A KNOWN quantity's half-width must be at most this share of |value| (or of the threshold gap).
KNOWN_REL_HALFWIDTH = 0.10


@dataclass(frozen=True)
class Quantity:
    """A number with the evidence that stands behind it."""

    name: str
    value: float | None
    lo: float | None = None
    hi: float | None = None
    n: int = 0
    source: str = ""
    measured_directly: bool = False
    #: observations needed to decide at all, if the organ can say (e.g. min track record length)
    n_required: float | None = None
    #: the most observations the desk could reach with its data (history length, etc.)
    n_reachable: float | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)

    def label(self, threshold: float | None = None) -> Label:
        return classify(self, threshold)

    def to_dict(self, threshold: float | None = None) -> dict[str, Any]:
        d = asdict(self)
        d["notes"] = list(self.notes)
        d["label"] = str(self.label(threshold))
        return d


def _finite(x: float | None) -> bool:
    return x is not None and math.isfinite(x)


def classify(q: Quantity, threshold: float | None = None) -> Label:
    """Label a quantity from its evidence. Pure; the same inputs always give the same label."""
    if (_finite(q.n_required) and _finite(q.n_reachable)
            and float(q.n_required or 0) > float(q.n_reachable or 0)):
        return Label.UNKNOWABLE
    if not _finite(q.value):
        return Label.UNKNOWN
    if q.n <= 0 and not q.measured_directly:
        return Label.UNKNOWN
    if q.measured_directly and q.lo is None and q.hi is None:
        return Label.KNOWN
    if q.n < MIN_N:
        return Label.WEAK
    if not (_finite(q.lo) and _finite(q.hi)):
        return Label.WEAK
    lo, hi, v = float(q.lo or 0.0), float(q.hi or 0.0), float(q.value or 0.0)
    if threshold is not None and lo <= threshold <= hi:
        return Label.WEAK
    half = (hi - lo) / 2.0
    scale = abs(v - threshold) if threshold is not None else abs(v)
    if scale > 0 and half <= KNOWN_REL_HALFWIDTH * scale:
        return Label.KNOWN
    return Label.ESTIMATED


def decide(q: Quantity, threshold: float, *, greater: bool = True) -> Decision:
    """Is the quantity above (or below) the threshold? INSUFFICIENT_EVIDENCE unless the label is
    KNOWN or ESTIMATED -- a WEAK interval that straddles the bar has not decided anything."""
    lab = classify(q, threshold)
    if lab not in (Label.KNOWN, Label.ESTIMATED) or q.value is None:
        return Decision.INSUFFICIENT_EVIDENCE
    above = float(q.value) > threshold
    return Decision.YES if above == greater else Decision.NO


def mean_quantity(name: str, xs: list[float], *, source: str = "", z: float = 1.959964
                  ) -> Quantity:
    """A sample mean with a normal-approximation interval; empty input is UNKNOWN."""
    clean = [float(x) for x in xs if x is not None and math.isfinite(float(x))]
    n = len(clean)
    if n == 0:
        return Quantity(name, None, n=0, source=source)
    m = sum(clean) / n
    if n < 2:
        return Quantity(name, m, n=n, source=source)
    var = sum((x - m) ** 2 for x in clean) / (n - 1)
    se = math.sqrt(var / n)
    return Quantity(name, m, m - z * se, m + z * se, n=n, source=source)


def beta_quantity(name: str, successes: int, trials: int, *, source: str = "",
                  z: float = 1.959964) -> Quantity:
    """A rate with a Wilson interval; zero trials is UNKNOWN."""
    if trials <= 0:
        return Quantity(name, None, n=0, source=source)
    p = successes / trials
    denom = 1 + z * z / trials
    centre = (p + z * z / (2 * trials)) / denom
    half = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / denom
    return Quantity(name, p, max(0.0, centre - half), min(1.0, centre + half), n=trials,
                    source=source)


def census(quantities: list[Quantity], thresholds: dict[str, float] | None = None
           ) -> dict[str, Any]:
    """How much of what the desk publishes is actually known? Counts per label."""
    thresholds = thresholds or {}
    counts = {str(lab): 0 for lab in Label}
    for q in quantities:
        counts[str(classify(q, thresholds.get(q.name)))] += 1
    total = len(quantities)
    decided = counts["KNOWN"] + counts["ESTIMATED"]
    return {"n": total, "by_label": counts,
            "decidable_share": (decided / total) if total else None}


# ------------------------------------------------------------------------------------------------
# THE CERTIFIER'S OWN NUMBERS AS QUANTITIES (2026-09-30): DSR, PBO and the cost model.
# A certificate's deflated Sharpe, its probability of backtest overfitting and its cost stress
# are published as pass/fail. Each is an ESTIMATE with an interval, and the census labels it by
# that interval exactly as it labels a forward edge.
# ------------------------------------------------------------------------------------------------

Z95 = 1.959964


def _num(x: Any) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def dsr_quantity(name: str, sharpe: Any, sr0: Any, n_obs: Any, *, source: str = "gate"
                 ) -> Quantity:
    """The Sharpe in excess of the deflated bar (SR - SR0; the DSR is Phi of its z), with the
    Lo (2002) normal-approximation interval se = sqrt((1 + SR^2 / 2) / (T - 1)). Decision
    threshold 0. n_required is the minimum track record length at which that interval would
    exclude 0 -- the number of observations the desk must reach to decide it."""
    sr, s0, t = _num(sharpe), _num(sr0), _num(n_obs)
    if sr is None or s0 is None or t is None or t < 2:
        return Quantity(name, None, n=0, source=source)
    se = math.sqrt((1.0 + 0.5 * sr * sr) / (t - 1.0))
    ex = sr - s0
    need = None if ex == 0 else 1.0 + (1.0 + 0.5 * sr * sr) * (Z95 / ex) ** 2
    return Quantity(name, ex, ex - Z95 * se, ex + Z95 * se, n=int(t), source=source,
                    n_required=need, notes=("SR - SR0 per period; se Lo (2002)",))


def pbo_quantity(name: str, pbo: Any, splits: Any, *, source: str = "gate") -> Quantity:
    """PBO as a rate with a Wilson interval over the number of CSCV splits -- the combinations
    share blocks, so the SPLIT count, not the combination count, is the effective sample.
    Decision threshold 0.5 (below: not overfit)."""
    p, s = _num(pbo), _num(splits)
    if p is None or s is None or s < 1:
        return Quantity(name, None, n=0, source=source)
    q = beta_quantity(name, round(max(0.0, min(1.0, p)) * s), int(s), source=source)
    return Quantity(name, p, q.lo, q.hi, n=int(s), source=source,
                    notes=("Wilson over CSCV splits",))


def cost_stress_quantity(name: str, ev_stressed: Any, ev: Any, sharpe: Any, n_obs: Any, *,
                         source: str = "gate") -> Quantity:
    """The expected value per trade at 3x costs, with the se the certificate's own signal-to-
    noise implies: se(EV) = |EV| / (|SR| sqrt(T)) (the EV's t-statistic taken as the Sharpe's).
    Threshold 0: does the edge survive tripled costs? No usable Sharpe: no interval (WEAK)."""
    x, e, sr, t = _num(ev_stressed), _num(ev), _num(sharpe), _num(n_obs)
    if x is None or t is None or t < 1:
        return Quantity(name, None, n=0, source=source)
    if e is None or sr is None or sr == 0:
        return Quantity(name, x, n=int(t), source=source, notes=("no interval",))
    se = abs(e) / (abs(sr) * math.sqrt(t))
    return Quantity(name, x, x - Z95 * se, x + Z95 * se, n=int(t), source=source,
                    notes=("se from the certificate's Sharpe",))


def cost_model_quantity(name: str, measured: list[float], modelled: Any, *,
                        source: str = "cost_surface") -> Quantity:
    """log(measured spread / modelled spread) over the hours the surface measured: 0 is a
    correct cost model, > 0 the model undercharges, < 0 it overcharges. Threshold 0."""
    m = _num(modelled)
    xs = [math.log(v / m) for v in measured if m and m > 0 and v and v > 0]
    q = mean_quantity(name, xs, source=source)
    return Quantity(q.name, q.value, q.lo, q.hi, n=q.n, source=source,
                    notes=("log(measured / modelled spread) per measured hour",))
