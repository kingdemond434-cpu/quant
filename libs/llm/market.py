"""INTERNAL INFORMATION MARKETS -- aggregate seats by calibration, not by headcount.

WHAT IS WRONG WITH MAJORITY VOTE, and the desk currently uses one. Eleven seats, one vote each,
majority kills. That treats a seat that has been right about mechanisms nine times out of ten as
exactly equal to one that has been wrong nine times out of ten -- so the panel's accuracy is
capped at the average seat's, forever, no matter how much evidence accumulates about which seats
are actually good. It also loses the strongest signal in the whole panel: a lone dissenter with a
track record is worth more than a comfortable consensus, and majority vote deletes exactly that.

WHAT A MARKET ADDS. Seats STAKE a probability rather than casting a vote. A proper scoring rule
settles the stake against what actually happened, so being confidently wrong costs more than
being uncertain, and being confidently right pays more than hedging. Over time a seat's realised
score IS its weight. Nobody has to decide who to trust; the record does it.

THE SCORING RULE IS LOGARITHMIC, and that choice is doing real work. Log score is the unique
proper rule whose expected value is maximised by reporting your TRUE belief -- under a linear
rule a seat maximises its score by always saying 0 or 1. It is also unbounded below, so a
confident wrong call is punished severely, which is the calibration failure that costs a desk
actual money. It is the same objective as the desk's: log score is to belief what E[log W] is to
capital, and for the identical reason -- both compound.

  LIVE ON DAY ONE with uniform weights, and it degrades to majority vote before any settlement
  exists, which is correct rather than a limitation: with no history there is no evidence anybody
  is better, and inventing weights would be fabrication.

Pure, dependency-free. Reports weights and aggregates; settles no hypothesis and promotes nothing.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field

__all__ = [
    "EPS",
    "MIN_SETTLED",
    "InformationMarket",
    "Stake",
    "aggregate",
    "brier",
    "log_score",
]

#: Probabilities are clipped into [EPS, 1-EPS] before scoring. A seat that says 0.0 and is wrong
#: scores -inf, which would end its weight permanently on a single call -- an overreaction that
#: destroys more information than the error did. Clipping bounds the worst single call at
#: log(1e-4) ~= -9.2, severe but survivable.
EPS = 1e-4

#: Settled stakes a seat needs before its record moves its weight off uniform. Below this the
#: sample is noise, and weighting on it would let one lucky call install a seat as the oracle.
MIN_SETTLED = 5


def log_score(p: float, outcome: bool) -> float:
    """log(p) if the event happened, log(1-p) otherwise. Proper: truth-telling maximises it."""
    q = min(max(float(p), EPS), 1.0 - EPS)
    return math.log(q if outcome else 1.0 - q)


def brier(p: float, outcome: bool) -> float:
    """Squared error. Reported alongside the log score because it is bounded and legible -- a
    reader can hold 0.18 in their head where -0.42 nats means nothing to anybody."""
    q = min(max(float(p), 0.0), 1.0)
    return (q - (1.0 if outcome else 0.0)) ** 2


@dataclass(frozen=True)
class Stake:
    """One seat's probability on one claim."""

    seat: str
    claim: str
    p: float
    rationale: str = ""


@dataclass
class InformationMarket:
    """Open stakes, settled history, and the weights that history implies."""

    stakes: list[Stake] = field(default_factory=list)
    #: claim -> what actually happened. Only settled claims move any weight.
    outcomes: dict[str, bool] = field(default_factory=dict)

    def stake(self, seat: str, claim: str, p: float, rationale: str = "") -> None:
        self.stakes.append(Stake(seat, claim, float(p), rationale))

    def settle(self, claim: str, outcome: bool) -> None:
        self.outcomes[claim] = bool(outcome)

    def records(self) -> dict[str, dict]:
        """Per-seat realised performance over SETTLED claims only."""
        acc: dict[str, list[tuple[float, bool]]] = defaultdict(list)
        for s in self.stakes:
            if s.claim in self.outcomes:
                acc[s.seat].append((s.p, self.outcomes[s.claim]))
        out = {}
        for seat, rows in acc.items():
            ls = sum(log_score(p, o) for p, o in rows) / len(rows)
            bs = sum(brier(p, o) for p, o in rows) / len(rows)
            out[seat] = {"settled": len(rows), "mean_log_score": round(ls, 4),
                         "mean_brier": round(bs, 4),
                         "mean_confidence": round(sum(p for p, _ in rows) / len(rows), 4),
                         "base_rate": round(sum(1 for _, o in rows if o) / len(rows), 4)}
        return out

    def weights(self, *, min_settled: int = MIN_SETTLED) -> dict[str, float]:
        """Seat -> weight, normalised. UNIFORM until a seat has a real record.

        Exponentiating the mean log score recovers the seat's geometric-mean probability on the
        truth -- the same relationship as E[log W] to wealth, which is not a coincidence: both
        are the quantity that compounds. A seat twice as often right as another gets roughly
        twice the weight, and one confidently-wrong call is felt for a long time.

        Seats below `min_settled` sit at the population mean weight rather than at zero. A new
        seat is unproven, not disbelieved, and starting it at zero would make the panel unable to
        ever learn that it is good.
        """
        recs = self.records()
        seats = sorted({s.seat for s in self.stakes})
        if not seats:
            return {}
        qualified = {k: v for k, v in recs.items() if v["settled"] >= min_settled}
        if not qualified:
            return dict.fromkeys(seats, round(1.0 / len(seats), 6))
        raw = {k: math.exp(v["mean_log_score"]) for k, v in qualified.items()}
        mean_raw = sum(raw.values()) / len(raw)
        full = {s: raw.get(s, mean_raw) for s in seats}
        tot = sum(full.values()) or 1.0
        return {s: round(w / tot, 6) for s, w in full.items()}

    def consensus(self, claim: str, *, min_settled: int = MIN_SETTLED) -> dict:
        """Calibration-weighted probability on one claim, with the dissent made visible."""
        rows = [s for s in self.stakes if s.claim == claim]
        if not rows:
            return {"claim": claim, "n": 0, "note": "nobody staked on this claim"}
        w = self.weights(min_settled=min_settled)
        tot = sum(w.get(r.seat, 0.0) for r in rows) or 1.0
        weighted = sum(r.p * w.get(r.seat, 0.0) for r in rows) / tot
        naive = sum(r.p for r in rows) / len(rows)
        spread = max(r.p for r in rows) - min(r.p for r in rows)
        extreme = max(rows, key=lambda r: abs(r.p - naive))
        return {
            "claim": claim,
            "n": len(rows),
            "weighted_p": round(weighted, 4),
            "unweighted_p": round(naive, 4),
            "weighting_moved_it": round(weighted - naive, 4),
            "spread": round(spread, 4),
            "strongest_dissent": {"seat": extreme.seat, "p": extreme.p,
                                  "weight": w.get(extreme.seat, 0.0),
                                  "rationale": extreme.rationale[:200]},
            "note": ("HIGH DISAGREEMENT -- this is the informative case, not the awkward one. "
                     "Unanimity mostly measures shared training data; a genuine split is where "
                     "an unpriced view lives, and majority vote deletes it by construction."
                     if spread > 0.4 else
                     "seats broadly agree -- which is weak evidence, since they share most of "
                     "their training data and correlated errors look exactly like consensus"),
        }


def aggregate(probabilities: dict[str, float], weights: dict[str, float] | None = None) -> float:
    """Weighted mean probability. Uniform when no weights are supplied.

    ARITHMETIC MEAN, DELIBERATELY, despite the log scoring. Averaging in log-odds is sharper and
    is the wrong tool here: these seats share most of their training data, so their errors are
    correlated, and log-odds pooling of correlated forecasts produces extreme confidence from
    what is nearly one opinion repeated. The arithmetic mean under-sharpens, which is the
    survivable direction to be wrong in.
    """
    if not probabilities:
        return 0.5
    w = weights or dict.fromkeys(probabilities, 1.0)
    tot = sum(w.get(k, 0.0) for k in probabilities) or 1.0
    return round(sum(p * w.get(k, 0.0) for k, p in probabilities.items()) / tot, 6)
