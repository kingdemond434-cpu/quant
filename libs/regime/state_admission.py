"""Which state dimensions have earned the right to condition capital, and which have not.

THE RULE THIS ENFORCES (principal, 2026-09-04): "no new regime variable gets capital authority
merely because it sounds sensible. It enters as information, gets PIT-tested, must improve
forecast calibration or marginal E[log W], and otherwise goes to the graveyard."

Without this, a state vector is an invitation to overfit. Session phase, event phase, liquidity
state, per-asset regime, global regime, regime age -- every one of them sounds sensible, every one
of them slices the same finite evidence thinner, and the desk has no way to tell which of them is
carrying information from which of them is carrying noise that happens to be labelled.

HOW A DIMENSION IS JUDGED. Walk-forward, on the desk's own realised trades. For each block:

    fit    on the training trades, the per-bucket mean, shrunk toward the pooled mean by n/(n+k)
    score  each TEST trade twice -- once predicted by the pooled mean, once by its bucket's
    keep   the difference in squared error, per trade

A dimension is only better if it predicts trades it has never seen. Fitting bucket means and
admiring the in-sample fit is how every one of these dimensions would pass.

SLEEVE EFFECTS ARE REMOVED FIRST. Pooling raw returns across sleeves would let a dimension look
informative purely because one profitable sleeve trades mostly in one bucket. Each sleeve's
returns are centred on its own training mean, so what is measured is whether the STATE explains
variation the sleeve identity does not.

THREE VERDICTS, and the middle one is not a pass:

    ADMIT           measurably better out of sample, after deflation for how many dimensions
                    were tried. May condition the posterior.
    RETAIN_SHRUNK   too little evidence to say. The dimension keeps whatever access it already
                    has, and the ONLY reason that is safe is `robust_elog`'s k_state = 40: a
                    bucket needs forty observations to outweigh the unconditional posterior, so
                    an unproven dimension moves the estimate barely at all. This is a stay of
                    execution granted by the shrinkage, not a verdict in the dimension's favour,
                    and it should be revisited as the ledgers fill.
    GRAVEYARD       measurably WORSE out of sample. Removed from conditioning.

DEFLATION, because this is itself a search. Testing eight dimensions and reporting the best one's
t-statistic is the same error the gauntlet's deflated Sharpe exists to correct, so the paired t on
the per-trade error difference is deflated by E[max_N Z] over the dimensions tried.
"""
from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, cast

import numpy as np

#: Shrinkage of a bucket mean toward the pooled mean, matching `robust_elog`'s k_state so the
#: test measures the estimator the allocator would actually use rather than a sharper one.
K_BUCKET = 40.0
#: Test-fold trades needed before a verdict is possible at all.
MIN_TEST_TRADES = 150
#: Trades a bucket needs in training before it may be used to predict anything.
MIN_BUCKET_TRAIN = 15
#: Deflated t a dimension must clear to be ADMITted, and to be sent to the GRAVEYARD.
ADMIT_T = 2.0
GRAVEYARD_T = -2.0
#: Walk-forward blocks. Three is the fewest that has both a fit and more than one score.
N_BLOCKS = 4

ADMIT = "ADMIT"
RETAIN_SHRUNK = "RETAIN_SHRUNK"
GRAVEYARD = "GRAVEYARD"
UNJUDGED = "UNJUDGED"


@dataclass(frozen=True)
class Trade:
    """One realised trade, with the state it was taken in."""

    sleeve: str
    when: str
    r: float
    #: dimension name -> bucket label for this trade.
    buckets: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Verdict:
    dimension: str
    verdict: str
    #: Mean reduction in squared error from conditioning. Positive is better.
    mse_gain: float
    t_paired: float
    t_deflated: float
    n_test: int
    n_buckets: int
    dimensions_tried: int
    why: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"dimension": self.dimension, "verdict": self.verdict,
                "mse_gain": round(self.mse_gain, 10), "t_paired": round(self.t_paired, 4),
                "t_deflated": round(self.t_deflated, 4), "n_test": self.n_test,
                "n_buckets": self.n_buckets, "dimensions_tried": self.dimensions_tried,
                "why": self.why}


def _expected_max_z(n: int) -> float:
    if n <= 1:
        return 0.0
    ln = math.log(n)
    if ln <= 0:
        return 0.0
    return math.sqrt(2 * ln) - (math.log(ln) + math.log(4 * math.pi)) / (2 * math.sqrt(2 * ln))


def _blocks(n: int, k: int) -> list[tuple[int, int]]:
    """Expanding-window folds: train on everything before, score the next slice."""
    if n < k * 2:
        return []
    edges = [round(n * i / k) for i in range(k + 1)]
    return [(edges[i], edges[i + 1]) for i in range(1, k)]


def judge(trades: Sequence[Trade], dimension: str, dimensions_tried: int = 1,
          k_bucket: float = K_BUCKET) -> Verdict:
    """Walk-forward: does conditioning on `dimension` predict unseen trades better?"""
    rows = [t for t in sorted(trades, key=lambda x: x.when) if dimension in t.buckets]
    n = len(rows)
    folds = _blocks(n, N_BLOCKS)
    if not folds:
        return Verdict(dimension, UNJUDGED, 0.0, 0.0, 0.0, 0, 0, dimensions_tried,
                       why=f"{n} trades carry this dimension; too few for {N_BLOCKS} folds")

    diffs: list[float] = []
    buckets_seen: set[str] = set()
    for start, stop in folds:
        train, test = rows[:start], rows[start:stop]
        if not train or not test:
            continue
        # SLEEVE EFFECTS OUT FIRST. A dimension must explain variation the sleeve identity does
        # not, or a single profitable sleeve concentrated in one bucket makes it look informative.
        by_sleeve: dict[str, list[float]] = {}
        for t in train:
            by_sleeve.setdefault(t.sleeve, []).append(t.r)
        sleeve_mean = {k: float(np.mean(v)) for k, v in by_sleeve.items()}
        centred = [t.r - sleeve_mean.get(t.sleeve, 0.0) for t in train]
        pooled = float(np.mean(centred)) if centred else 0.0

        agg: dict[str, list[float]] = {}
        for t, c in zip(train, centred, strict=True):
            agg.setdefault(t.buckets[dimension], []).append(c)
        shrunk = {}
        for b, vals in agg.items():
            if len(vals) < MIN_BUCKET_TRAIN:
                continue
            lam = len(vals) / (len(vals) + k_bucket)
            shrunk[b] = lam * float(np.mean(vals)) + (1.0 - lam) * pooled
            buckets_seen.add(b)

        for t in test:
            if t.sleeve not in sleeve_mean:
                continue                     # a sleeve never seen in training explains nothing
            y = t.r - sleeve_mean[t.sleeve]
            b = t.buckets[dimension]
            if b not in shrunk:
                continue                     # an unseen bucket is not a prediction
            diffs.append((y - pooled) ** 2 - (y - shrunk[b]) ** 2)

    n_test = len(diffs)
    # A DIMENSION THAT NEVER VARIES IS NOT A DIMENSION. If every trade in training fell into one
    # bucket, the "conditional" mean IS the pooled mean and the test returns t = 0.00 -- which
    # reads as "measured, no effect" when the truth is "nothing was measured". Seen live: `event`
    # scored t=+0.00 on 336 predictions with buckets=1, because the calendar vintages the miner
    # keeps span days while the ledgers span months, so every trade was labelled NORMAL.
    if len(buckets_seen) < 2:
        return Verdict(dimension, UNJUDGED, 0.0, 0.0, 0.0, n_test, len(buckets_seen),
                       dimensions_tried,
                       why=(f"only {len(buckets_seen)} bucket ever had "
                            f"{MIN_BUCKET_TRAIN} training trades, so conditioning on this is "
                            "arithmetically identical to not conditioning. NOT a null result -- "
                            "the dimension's history does not cover the trades."))
    if n_test < MIN_TEST_TRADES:
        return Verdict(dimension, RETAIN_SHRUNK, float(np.mean(diffs)) if diffs else 0.0,
                       0.0, 0.0, n_test, len(buckets_seen), dimensions_tried,
                       why=(f"{n_test} out-of-sample predictions, needs {MIN_TEST_TRADES}. "
                            "UNDERPOWERED, not passed -- what makes keeping it safe is the "
                            f"k_state={k_bucket:.0f} shrinkage, which leaves an unproven bucket "
                            "barely able to move the posterior."))

    arr = np.asarray(diffs, dtype=float)
    sd = float(arr.std(ddof=1))
    gain = float(arr.mean())
    tstat = gain / (sd / math.sqrt(arr.size)) if sd > 0 else 0.0
    t_def = tstat - _expected_max_z(max(1, dimensions_tried)) if tstat > 0 else tstat
    if t_def >= ADMIT_T:
        verdict, why = ADMIT, "predicts unseen trades better, after deflation for the search"
    elif tstat <= GRAVEYARD_T:
        verdict, why = GRAVEYARD, "measurably worse out of sample; conditioning on it adds noise"
    else:
        verdict, why = RETAIN_SHRUNK, "no measurable improvement; kept only by the shrinkage"
    return Verdict(dimension, verdict, gain, tstat, t_def, n_test, len(buckets_seen),
                   dimensions_tried, why=why)


def judge_all(trades: Sequence[Trade], dimensions: Sequence[str],
              k_bucket: float = K_BUCKET) -> dict[str, Verdict]:
    """Judge every dimension against the same trades, each charged for the whole search."""
    tried = len(dimensions)
    return {d: judge(trades, d, dimensions_tried=tried, k_bucket=k_bucket) for d in dimensions}


def admitted(verdicts: dict[str, Verdict]) -> tuple[str, ...]:
    """Dimensions that may condition the posterior: everything not sent to the graveyard.

    RETAIN_SHRUNK is included on purpose and it is the conservative choice, not the permissive
    one: those dimensions already condition today, and removing a dimension on the strength of a
    test that reports it has no power would be substituting one unmeasured decision for another.
    Only a MEASURED failure removes access.
    """
    return tuple(sorted(d for d, v in verdicts.items() if v.verdict != GRAVEYARD))


def build_labeller(name: str) -> Callable[[Trade], str] | None:
    """A function from a trade to this dimension's bucket, or None when it cannot be rebuilt.

    ONLY DIMENSIONS RECONSTRUCTIBLE AT THE TRADE'S OWN MOMENT LIVE HERE. Labelling a trade from
    January with today's regime fit, today's spread percentile or today's calendar would test
    whether the PRESENT predicts the past, which every dimension would pass. An asset's regime
    needs the walk-forward decode `family_regime_transition` builds; the liquidity state needs the
    historical tape; both are recorded as gaps until their history is joined rather than faked
    from a current reading.
    """
    if name == "session":
        try:
            from research.session_phase import (  # type: ignore[import-not-found]
                broker_utc_offset_h,
                phase_at,
            )
        except ImportError:
            return None
        off, _src = broker_utc_offset_h()
        if off is None:
            return None

        def _session(t: Trade) -> str:
            from datetime import datetime
            try:
                return str(phase_at(datetime.fromisoformat(t.when), broker_utc_offset_h=off))
            except (TypeError, ValueError):
                return ""
        return _session

    if name == "weekday":
        def _weekday(t: Trade) -> str:
            from datetime import datetime
            try:
                return datetime.fromisoformat(t.when).strftime("%a")
            except (TypeError, ValueError):
                return ""
        return _weekday

    if name == "event":
        # POINT-IN-TIME BY CONSTRUCTION. The calendar rows carry the SCHEDULED stamp of each
        # release, so a trade from January is classified against the releases around January.
        # This is the one new state dimension whose history the desk already holds.
        try:
            from libs.regime.event_state import classify, parse_rows, relevant
        except ImportError:
            return None
        rows = _calendar()
        if not rows:
            return None
        meta = _universe_meta()
        parsed = parse_rows(rows)
        if not parsed:
            return None

        def _event(t: Trade) -> str:
            from datetime import datetime
            try:
                when = datetime.fromisoformat(t.when)
            except (TypeError, ValueError):
                return ""
            scoped = relevant(parsed, _symbol_of(t.sleeve), meta)
            if not scoped:
                return ""
            return classify(when, [r["_stamp"] for r in scoped],
                            symbol=_symbol_of(t.sleeve), rows=scoped).phase
        return _event
    return None


def _symbol_of(sleeve: str) -> str:
    """The instrument a sleeve name is about. Ledgers are `<SYM>_<family>_<window>`."""
    head = str(sleeve or "").split("_")[0]
    return head.upper() if head else ""


def _calendar() -> list[dict[str, Any]]:
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "desks" / "mt5" / "data" / "intelligence" \
        / "ff_calendar_vintage"
    if not root.exists():
        return []
    out, seen = [], set()
    for path in sorted(root.glob("*.json"))[-60:]:
        try:
            doc = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        rows = doc if isinstance(doc, list) else (doc.get("rows") or doc.get("discoveries") or [])
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            key = f"{row.get('event_date')}|{row.get('title')}"
            if key not in seen:
                seen.add(key)
                out.append(row)
    return out


def _universe_meta() -> dict[str, Any]:
    import json
    from pathlib import Path

    p = (Path(__file__).resolve().parents[2] / "desks" / "mt5" / "data" / "universe"
         / "universe.json")
    try:
        return cast("dict[str, Any]", json.loads(p.read_text("utf-8")))
    except (OSError, ValueError):
        return {}
