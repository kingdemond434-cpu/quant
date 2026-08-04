"""OPEN INTEREST x PRICE -- who paid for the move, and does it matter for the next one.

THE MECHANISM IS ARITHMETIC, NOT PSYCHOLOGY, which is why it is worth testing before any chart
pattern. Open interest counts OPEN POSITIONS. A perp contract exists only while both sides hold
it, so OI can only fall when positions CLOSE. That makes the joint sign of price change and OI
change an identity about who is transacting, not an inference about what anyone believes:

                    OI RISING                          OI FALLING
    PRICE UP        new longs opening                  shorts CLOSING (covering)
                    -> money entering, continuation    -> the move is being paid for by people
                                                          LEAVING, and the buyer of last resort
                                                          runs out when the shorts are done
    PRICE DOWN      new shorts opening                 longs CLOSING (liquidation)
                    -> continuation                    -> exhaustion, same argument mirrored

The tradeable claim is that the two EXHAUSTION quadrants have different forward-return
distributions from the two CONTINUATION quadrants. It is rarely tested properly for a boring
reason: most people never join OI to price at the bar level, and OI series are published on their
own clock with their own gaps.

WHY IT IS SEPARATE FROM THE PATTERN WORK. Same discipline as `liquidation_mechanism`: measure
whether the quadrants separate at all BEFORE building any rule on top of them. If they do not, no
amount of entry-rule tuning creates the effect, and the tuning would only find the noise.

EVERY VALUE IS CAUSAL. The quadrant at bar t uses changes over a window ENDING at t. Forward
returns are computed separately by the caller and are never an input to the classification -- the
one mistake that would make every quadrant look predictive.

Pure numpy/pandas. No I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

__all__ = [
    "CONTINUATION",
    "EXHAUSTION",
    "QuadrantEvidence",
    "classify",
    "quadrant_evidence",
]

#: The four states, named for the FLOW they imply rather than for the signs that produce them --
#: `price_up_oi_down` says nothing; `short_covering` says what the next bar depends on.
NEW_LONGS = "new_longs"            # price up,   OI up
SHORT_COVERING = "short_covering"  # price up,   OI down
NEW_SHORTS = "new_shorts"          # price down, OI up
LONG_LIQUIDATION = "long_liquidation"  # price down, OI down
FLAT = "flat"                      # neither series moved enough to classify

CONTINUATION = (NEW_LONGS, NEW_SHORTS)
EXHAUSTION = (SHORT_COVERING, LONG_LIQUIDATION)


@dataclass(frozen=True)
class QuadrantEvidence:
    """Forward-return separation between exhaustion and continuation, with the verdict apart from
    the numbers that produced it."""

    counts: dict[str, int]
    mean_fwd: dict[str, float]
    exhaustion_vs_continuation_d: float = float("nan")
    verdict: str = "UNKNOWN"
    why: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"counts": self.counts, "mean_fwd": self.mean_fwd,
                "exhaustion_vs_continuation_d": self.exhaustion_vs_continuation_d,
                "verdict": self.verdict, "why": self.why}


#: |d| below which the pre-registration calls OI additive-to-price ABSENT. Mirrors
#: docs/research/THREE_MECHANISM_PREREGISTRATION.md; a test asserts the two agree.
SEPARATION_FLOOR = 0.2


def classify(price: pd.Series, oi: pd.Series, *, window: int = 12,
             price_eps: float = 0.0, oi_eps: float = 0.0) -> pd.Series:
    """Quadrant per bar, from changes over the `window` bars ENDING at that bar.

    `price_eps` and `oi_eps` are DEAD BANDS in fractional terms, and they are load-bearing rather
    than cosmetic. Without them the sign of a change of one tick decides the quadrant, so most bars
    get classified by rounding noise and the four groups become four samples of the same
    distribution -- which reads as "no effect" and would retire the hypothesis for a reason that
    is about float comparison rather than about markets.

    Returns FLAT where either change is inside its band, or where the window is not yet full.
    FLAT is a real state and is never silently folded into a directional quadrant.
    """
    p = pd.to_numeric(price, errors="coerce").astype("float64")
    o = pd.to_numeric(oi, errors="coerce").astype("float64")
    if len(p) != len(o):
        raise ValueError(f"price and oi must align: {len(p)} vs {len(o)}")

    dp = p.pct_change(window)
    do = o.pct_change(window)
    out = pd.Series(FLAT, index=p.index, dtype=object)

    up = dp > price_eps
    dn = dp < -price_eps
    oi_up = do > oi_eps
    oi_dn = do < -oi_eps

    out[up & oi_up] = NEW_LONGS
    out[up & oi_dn] = SHORT_COVERING
    out[dn & oi_up] = NEW_SHORTS
    out[dn & oi_dn] = LONG_LIQUIDATION
    out[dp.isna() | do.isna()] = FLAT
    return out


def _cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    a = a[np.isfinite(a)]
    b = b[np.isfinite(b)]
    if a.size < 20 or b.size < 20:
        return float("nan")
    va, vb = a.var(ddof=1), b.var(ddof=1)
    pooled = np.sqrt(((a.size - 1) * va + (b.size - 1) * vb) / max(a.size + b.size - 2, 1))
    if not np.isfinite(pooled) or pooled <= 0:
        return float("nan")
    return float((a.mean() - b.mean()) / pooled)


def quadrant_evidence(quadrant: pd.Series, forward_ret: pd.Series) -> QuadrantEvidence:
    """Do the exhaustion quadrants' forward returns differ from the continuation quadrants'?

    THE SIGN CONVENTION IS THE SUBTLE PART AND GETTING IT WRONG WOULD INVENT AN EFFECT. Raw forward
    return cannot be pooled across quadrants: `new_longs` and `new_shorts` are both continuation
    but point opposite ways, so averaging them cancels to roughly zero and any exhaustion group
    would look different from it by construction.

    So each quadrant's forward return is signed by its OWN directional implication -- continuation
    expects the move to persist, exhaustion expects it to stop or reverse -- and what is compared
    is "did the implied direction pay". That is the comparison the hypothesis actually makes.

    `forward_ret[t]` must be the return AFTER t, computed by the caller. It is never an input to
    `classify`, which is the one join that would make every quadrant look predictive.
    """
    q = pd.Series(quadrant).astype(object)
    r = pd.to_numeric(forward_ret, errors="coerce").astype("float64")
    if len(q) != len(r):
        raise ValueError(f"quadrant and forward_ret must align: {len(q)} vs {len(r)}")

    # Continuation of an up-move pays if price keeps rising; continuation of a down-move pays if
    # it keeps falling. Exhaustion is the reverse of the move that produced it.
    sign = {NEW_LONGS: 1.0, NEW_SHORTS: -1.0, SHORT_COVERING: -1.0, LONG_LIQUIDATION: 1.0}
    counts = {k: int((q == k).sum()) for k in (*CONTINUATION, *EXHAUSTION, FLAT)}

    signed: dict[str, np.ndarray] = {}
    mean_fwd: dict[str, float] = {}
    for k, s in sign.items():
        v = (r[q == k] * s).to_numpy(dtype="float64")
        signed[k] = v
        finite = v[np.isfinite(v)]
        mean_fwd[k] = float(finite.mean()) if finite.size else float("nan")

    ex = np.concatenate([signed[k] for k in EXHAUSTION]) if counts else np.empty(0)
    co = np.concatenate([signed[k] for k in CONTINUATION]) if counts else np.empty(0)
    d = _cohens_d(ex, co)

    if not np.isfinite(d):
        verdict, why = "UNDERPOWERED", (
            "fewer than 20 usable observations in a group. The reading is uninformative in EITHER "
            "direction -- it is not evidence that the quadrants are the same.")
    elif abs(d) < SEPARATION_FLOOR:
        verdict, why = "NO-SEPARATION", (
            f"exhaustion and continuation forward returns differ by d={d:+.3f}, inside the "
            f"{SEPARATION_FLOOR} floor. Open interest adds nothing to price alone here, and no "
            "entry rule built on the quadrants can create an effect that is not in them.")
    else:
        verdict, why = "SEPARATED", (
            f"exhaustion pays d={d:+.3f} relative to continuation, on the direction each quadrant "
            "implies. That is the precondition for a rule -- NOT a tradeable edge: no costs, no "
            "multiplicity correction and no capacity have been applied at this stage.")

    return QuadrantEvidence(counts=counts, mean_fwd=mean_fwd,
                            exhaustion_vs_continuation_d=d, verdict=verdict, why=why)
