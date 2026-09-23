"""HOSTILE VALIDATION -- eight adversaries that re-run the STRATEGY, not its return series.

WHAT THE GAUNTLET ALREADY OWNS, AND WHY IT IS NOT THIS. Every adversary the desk has judges a
candidate from its RETURNS: `redteam` re-places the signals it was handed, `falsifiers` regresses,
splits and stresses the trade series, `bar_permutation` scrambles the tape and re-scores a
statistic, `pbo`/`reality_check`/`dsr` price the search that found it. All of them take the
strategy's OUTPUT as given, so none can ask the question that killed the desk's largest ever
backtest number: would the same CODE, re-run on bars it did not choose, still say this?

THE CASE THAT PAID FOR THIS MODULE. An FVG cell scored t = +9.0 and nothing in the battery
objected -- the trades were real, the costs were charged, both halves carried it, the placebos
lost. The result came from a same-bar limit-fill ambiguity: the replay assumed a fill at a level
the signal bar merely TOUCHED, so every entry booked the distance from the touch to the close for
free. Fixing that one line took the cell to t = -6.0. Fifteen t-units and a sign, invisible to
every test that reads the R series, because the R series was faithfully reporting a fill nobody
could have got. `delayed_entry` is the instrument that catches it.

THE INTERFACE IS THE WHOLE DESIGN. `evaluate(bars) -> TradeStats` is the caller's own replay,
injected, so this module never re-implements a family, a cost model or an engine (the rule
`redteam.run` follows with `score`). Each test is a pure function of that callable and a frame and
returns one `Verdict`; `passed=None` is UNMEASURED, because absence never resolves to a clean
verdict (L1.28a). One report, and it is a gauntlet stage that knows nothing about the gauntlet.

THE EIGHT, AND THE ARTEFACT EACH ONE CATCHES:

    timestamp_permutation  day ordering destroyed, clock kept -- an edge that is the asset's own
                           marginal distribution wearing a schedule. BLOCKS.
    regime_permutation     labels shuffled across blocks -- a conditioner that is a second free
                           parameter rather than a state.
    nearby_instrument_placebo  the same code where the mechanism says it must NOT pay -- a
                           mechanism story fitted after the fact.
    delayed_entry          decision tape real, execution tape k bars on -- the fill artefact
                           above. BLOCKS at k=1: an edge that cannot survive one bar of lateness
                           was never an edge, it was a fill assumption.
    subperiod_removal      each contiguous fifth dropped in turn -- one episode with a calendar
                           around it. BLOCKS on a sign flip only.
    worst_year_removal     the year contributing the most R removed, i.e. the one it would be
                           worst to lose -- a single-year windfall. BLOCKS.
    transfer_test          another instrument the mechanism PREDICTS carries it -- a fit with a
                           story transfers nowhere.
    data_source_substitution  the same instrument from a second SOURCE -- an edge living inside
                           one vendor's bar construction, which is not a market fact.

`dual_engine` is the ninth and sits outside the roster because it needs a second implementation
only the caller can supply: two independent replays of ONE strategy on ONE frame must agree on
how many trades there were and what each was worth, or the certificate rests on a coin flip.

SEVERITY. Four tests BLOCK, because a measured failure there means the number is not a
measurement of the market. The rest are REPORTED: a placebo that also pays is a defect report for
a human (`redteam`'s standing rule), not an automatic withdrawal. This module withdraws nothing,
sizes nothing and promotes nothing -- `blocking` is the one bit a stage can act on, and a failing
test makes an edge UNPROVEN, which is a reason to keep testing it and never a reason to run a
smaller book somewhere else (GROWTH GOVERNANCE Rule 1).
"""
from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

__all__ = ["BLOCKING_TESTS", "HostileReport", "TradeStats", "Verdict",
           "data_source_substitution", "delayed_entry", "dual_engine",
           "nearby_instrument_placebo", "regime_permutation", "run_all", "stats_from_r",
           "subperiod_removal", "timestamp_permutation", "transfer_test", "worst_year_removal"]

#: A t needs a spread and a spread needs three points: below this it is not small, it is
#: UNDEFINED, which is a different verdict (L1.28a). MIN_BARS refuses a frame too short to cut
#: into fifths or to have blocks to permute.
MIN_TRADES = 3
MIN_BARS = 60

#: One trading day of H1 bars. Blocks preserve within-day serial structure and destroy the
#: ordering ACROSS days, and -- because every block is placed at the same phase -- each bar keeps
#: its hour of day, so a session-conditioned rule still fires at its own hours in the null and
#: only the day it meets there is somebody else's. Below MIN_NULL_DRAWS usable draws a 95th
#: percentile is the maximum of a handful of numbers; dropping unusable draws and shrinking the
#: denominator with them is `bar_permutation`'s rule.
PERMUTATIONS = 20
PERM_BLOCK = 24
PERM_QUANTILE = 0.95
MIN_NULL_DRAWS = 5

PLACEBO_T_RATIO = 0.5
DELAYS: tuple[int, ...] = (1, 5, 15)
DELAY_RETENTION = 0.50
SUBPERIODS = 5
SUBPERIOD_MIN_T = 1.0
WORST_YEAR_MIN_T = 1.5
TRANSFER_MIN_T = 1.0
SOURCE_EXPECTANCY_TOL = 0.30
DUAL_COUNT_TOL = 0.10
DUAL_EXPECTANCY_TOL = 0.25

BLOCK = "block"
REPORT = "report"

#: The tests whose MEASURED failure means the number is not a measurement of the market.
#: `subperiod_removal` is in the roster but downgrades itself to ``report`` when its failure is one
#: of magnitude rather than a sign flip -- a thin fifth is weakness, a flipped fifth is a different
#: strategy. `_EXECUTION_COLS` is what a fill meets; `close` is deliberately absent, because it is
#: what the rule DECIDED on and moving it would move the signal instead of the fill.
BLOCKING_TESTS = frozenset({"timestamp_permutation", "delayed_entry", "subperiod_removal",
                            "worst_year_removal"})
_OHLC = ("open", "high", "low", "close")
_EXECUTION_COLS = ("open", "high", "low")


@dataclass(frozen=True)
class TradeStats:
    """What one replay of a strategy produced. The caller's own numbers, never recomputed here."""

    n: int
    mean_r: float
    t_stat: float
    expectancy: float
    per_trade_r: list[float] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"n": int(self.n), "mean_r": _num(self.mean_r), "t_stat": _num(self.t_stat),
                "expectancy": _num(self.expectancy)}


def stats_from_r(rs: Sequence[float]) -> TradeStats:
    """Per-trade R multiples -> `TradeStats`. The one constructor, so every test agrees on `t`.

    Non-finite R values are dropped and `n` is what survived: a NaN trade is not a zero trade.
    ``t_stat`` IS NaN BELOW THREE TRADES, a deliberate divergence from ``falsifiers._t``, which
    returns 0.0. There 0.0 reads as "no edge" on the real series; here the same number joins a
    NULL DISTRIBUTION, where a fabricated 0.0 for every permutation that happened to trade nothing
    drags the null down -- significance manufactured out of the permutations that failed.
    """
    arr = np.asarray(list(rs), dtype=float)
    arr = arr[np.isfinite(arr)]
    n = int(arr.size)
    if n == 0:
        return TradeStats(n=0, mean_r=float("nan"), t_stat=float("nan"),
                          expectancy=float("nan"), per_trade_r=[])
    mean = float(arr.mean())
    if n < MIN_TRADES:
        t = float("nan")
    else:
        sd = float(arr.std(ddof=1))
        t = float(mean / (sd / math.sqrt(n))) if sd > 0.0 else 0.0
    return TradeStats(n=n, mean_r=mean, t_stat=t, expectancy=mean,
                      per_trade_r=[float(x) for x in arr])


#: The caller's replay: any bars frame in, that frame's trade statistics out.
Evaluate = Callable[[pd.DataFrame], TradeStats]


@dataclass(frozen=True)
class Verdict:
    """One adversary's finding. ``passed is None`` is UNMEASURED and is never folded into False."""

    name: str
    passed: bool | None
    statistic: float | None
    threshold: float | None
    why: str
    basis: dict[str, Any] = field(default_factory=dict)
    severity: str = REPORT

    @property
    def measured(self) -> bool:
        return self.passed is not None

    @property
    def blocks(self) -> bool:
        """A MEASURED failure on a blocking test. An unmeasured test blocks nothing."""
        return self.passed is False and self.severity == BLOCK

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "passed": self.passed, "statistic": _num(self.statistic),
                "threshold": _num(self.threshold), "severity": self.severity,
                "status": ("UNMEASURED" if self.passed is None else
                           ("PASS" if self.passed else "FAIL")),
                "why": self.why, "basis": self.basis}


@dataclass(frozen=True)
class HostileReport:
    """The roster's finding. `blocking` is the only bit a gauntlet stage needs to read."""

    verdicts: tuple[Verdict, ...]
    seed: int = 0
    real: TradeStats | None = None

    @property
    def n_passed(self) -> int:
        return sum(1 for v in self.verdicts if v.passed is True)

    @property
    def n_failed(self) -> int:
        return sum(1 for v in self.verdicts if v.passed is False)

    @property
    def n_unmeasured(self) -> int:
        return sum(1 for v in self.verdicts if v.passed is None)

    @property
    def blocking(self) -> bool:
        return any(v.blocks for v in self.verdicts)

    @property
    def blocked_by(self) -> list[str]:
        return [v.name for v in self.verdicts if v.blocks]

    def by_name(self, name: str) -> Verdict | None:
        for v in self.verdicts:
            if v.name == name:
                return v
        return None

    def to_dict(self) -> dict[str, Any]:
        return {"seed": int(self.seed), "n_tests": len(self.verdicts),
                "real": self.real.to_dict() if self.real is not None else None,
                "n_passed": self.n_passed, "n_failed": self.n_failed,
                "n_unmeasured": self.n_unmeasured, "blocking": self.blocking,
                "blocked_by": self.blocked_by,
                "verdicts": [v.to_dict() for v in self.verdicts],
                "why": (f"{self.n_passed} passed, {self.n_failed} failed, "
                        f"{self.n_unmeasured} unmeasured"
                        + (f"; BLOCKED BY {', '.join(self.blocked_by)}"
                           if self.blocking else ""))}


# --------------------------------------------------------------------------------------------
# helpers


def _num(x: float | None) -> float | None:
    """JSON-safe; NaN/inf become None rather than a number no reader can compare."""
    if x is None:
        return None
    f = float(x)
    return round(f, 8) if math.isfinite(f) else None


def _unmeasured(name: str, why: str, severity: str = REPORT,
                basis: dict[str, Any] | None = None) -> Verdict:
    return Verdict(name=name, passed=None, statistic=None, threshold=None, why=why,
                   basis=basis or {}, severity=severity)


def _safe(evaluate: Evaluate, frame: pd.DataFrame | None) -> TradeStats | None:
    """Re-run the caller's replay, returning None rather than raising into the roster.

    A replay that blows up on a permuted frame is a datum, not a crash: the callers COUNT the
    failures into their basis (`knob_sensitivity`'s rule -- record, never swallow).
    """
    if frame is None or len(frame) < MIN_BARS:
        return None
    try:
        out = evaluate(frame)
    except Exception:
        return None
    return out if isinstance(out, TradeStats) else None


def _has_ohlc(bars: pd.DataFrame | None) -> bool:
    return bars is not None and all(c in bars.columns for c in _OHLC)


def _usable(st: TradeStats | None) -> bool:
    return st is not None and st.n >= MIN_TRADES and math.isfinite(st.t_stat)


def _rel_gap(a: float, b: float) -> float:
    """|a-b| relative to the FIRST argument, which is always the reference measurement."""
    if not (math.isfinite(a) and math.isfinite(b)) or a == 0.0:
        return float("nan")
    return abs(b - a) / abs(a)


def _block_order(m: int, block: int, rng: np.random.Generator) -> np.ndarray | None:
    """A permutation of 0..m-1 that moves whole blocks and leaves the ragged tail in place."""
    b = max(1, int(block))
    nb = m // b
    if nb < 2:
        return None
    idx = np.arange(m)
    head = nb * b
    perm = rng.permutation(nb)
    body = idx[:head].reshape(nb, b)[perm].reshape(-1)
    return np.concatenate([body, idx[head:]])


def _block_permute(bars: pd.DataFrame, *, block: int,
                   rng: np.random.Generator) -> pd.DataFrame | None:
    """Rebuild the frame from a BLOCK permutation of its log-return decomposition.

    The decomposition is `bar_permutation`'s, including its correction: each bar's gap travels
    with its own intra-bar triple under ONE index permutation, so close-to-close log returns are an
    exact reordering of the real ones -- every moment preserved, order destroyed. Splitting them
    inflates the null's variance and hands a zero-skill rule a p-value. Two deliberate departures:
    BLOCKS rather than single bars, because a bar-wise shuffle also destroys the short-horizon
    autocorrelation a mean-reversion rule legitimately eats; and a closed-form reassembly of that
    module's sequential loop (`close = c0 + cumsum(gap + dclose)`), because this null is rebuilt
    twenty times per candidate inside a stage rather than once in a study.
    """
    if not _has_ohlc(bars) or len(bars) < MIN_BARS:
        return None
    o, h, lo, c = (bars[k].to_numpy(dtype=float) for k in _OHLC)
    if not all(np.all(np.isfinite(a)) and np.all(a > 0.0) for a in (o, h, lo, c)):
        return None
    ln_o, ln_h, ln_l, ln_c = (np.log(a) for a in (o, h, lo, c))
    gap = ln_o[1:] - ln_c[:-1]
    d_h, d_l, d_c = ln_h[1:] - ln_o[1:], ln_l[1:] - ln_o[1:], ln_c[1:] - ln_o[1:]
    order = _block_order(gap.size, block, rng)
    if order is None:
        return None
    g, dh, dl, dc = gap[order], d_h[order], d_l[order], d_c[order]
    close = np.concatenate([ln_c[:1], ln_c[0] + np.cumsum(g + dc)])
    open_ = np.concatenate([ln_o[:1], close[:-1] + g])
    high = np.concatenate([ln_h[:1], open_[1:] + dh])
    low = np.concatenate([ln_l[:1], open_[1:] + dl])
    out = bars.copy()
    for name, arr in zip(_OHLC, (open_, high, low, close), strict=True):
        out[name] = np.exp(arr)
    if "volume" in out.columns:
        vol = bars["volume"].to_numpy()
        out["volume"] = np.concatenate([vol[:1], vol[1:][order]])
    return out


def _delay_entry_frame(bars: pd.DataFrame, k: int) -> pd.DataFrame | None:
    """The decision tape real, the EXECUTION tape moved `k` bars on.

    A WHOLE-FRAME SHIFT WOULD BE DECORATIVE, which is why the frame is split. Any shift of every
    column is a relabelling and a rule that is a function of the path alone is invariant under one
    -- the test would buy nothing against exactly the class it exists to prosecute
    (`knob_sensitivity`). So `close` and volume stay where they are, because that is what the rule
    looked at, while `open`, `high` and `low` at row t become the real ones from row t+k, because
    that is the market the trade met after arriving k bars late. The trade enters later and exits
    on its original clock, holding k bars fewer: an edge spread over its horizon loses roughly
    k/hold, an edge that was a same-bar fill assumption loses all of it at k=1 (the FVG case). The
    blended bar is REPAIRED (`high >= max(open, close) >= min(open, close) >= low`) so nobody is
    handed a bar no venue could print -- basis points at k=1 on an hourly chart, wider at k=15.

    THE LONG DELAYS ARE A CURVE, NOT A VERDICT, which is why only k=1 blocks. Once k exceeds the
    holding period the entry sits AFTER the exit and a rule comparing a decision price with a fill
    price is re-selecting on a move it already knows: on the desk's own synthetic artefact
    retention at k=15 came back at 2.46, which means the construction has left the question behind.
    """
    if k <= 0 or not _has_ohlc(bars) or len(bars) - k < MIN_BARS:
        return None
    out = bars.iloc[:-k].copy()
    for name in _EXECUTION_COLS:
        out[name] = bars[name].to_numpy(dtype=float)[k:]
    o = out["open"].to_numpy(dtype=float)
    c = out["close"].to_numpy(dtype=float)
    out["high"] = np.maximum(out["high"].to_numpy(dtype=float), np.maximum(o, c))
    out["low"] = np.minimum(out["low"].to_numpy(dtype=float), np.minimum(o, c))
    return out


def _drop_slice(bars: pd.DataFrame, lo: int, hi: int) -> pd.DataFrame | None:
    """The frame without rows [lo, hi). The seam is real and is named in the verdict's basis."""
    parts = [p for p in (bars.iloc[:lo], bars.iloc[hi:]) if len(p) > 0]
    if not parts:
        return None
    return parts[0] if len(parts) == 1 else pd.concat(parts)


def _null_verdict(name: str, real: TradeStats, null: list[float], failed: int, *,
                  severity: str, what: str) -> Verdict:
    """Real t against the 95th percentile of a null of t's. Shared by the two permutation tests."""
    if len(null) < MIN_NULL_DRAWS:
        return _unmeasured(name, f"only {len(null)} usable null draw(s) of {len(null) + failed}; "
                                 f"{MIN_NULL_DRAWS} are needed before a {PERM_QUANTILE:.0%} "
                                 "quantile means anything", severity,
                           {"n_null": len(null), "n_null_failed": failed})
    arr = np.asarray(null, dtype=float)
    q = float(np.quantile(arr, PERM_QUANTILE))
    p = float((np.sum(arr >= real.t_stat) + 1) / (arr.size + 1))
    passed = bool(real.t_stat > q)
    return Verdict(
        name=name, passed=passed, statistic=float(real.t_stat), threshold=q, severity=severity,
        why=(f"real t={real.t_stat:.2f} {'beats' if passed else 'does not beat'} the "
             f"{PERM_QUANTILE:.0%} quantile of {what} (t={q:.2f}, p={p:.3f})"),
        basis={"real_t": _num(real.t_stat), "null_q": _num(q), "p_value": _num(p),
               "null_mean_t": _num(float(arr.mean())), "null_max_t": _num(float(arr.max())),
               "n_null": int(arr.size), "n_null_failed": int(failed), "n_trades": int(real.n)},
    )


# --------------------------------------------------------------------------------------------
# the eight


def timestamp_permutation(evaluate: Evaluate, bars: pd.DataFrame, *,
                          n_permutations: int = PERMUTATIONS, block: int = PERM_BLOCK,
                          seed: int = 0, real: TradeStats | None = None) -> Verdict:
    """(1) Is there information in the SEQUENCE, or only in the distribution it came from?"""
    name = "timestamp_permutation"
    real = real if real is not None else _safe(evaluate, bars)
    if not _usable(real) or real is None:
        return _unmeasured(name, "the strategy produced no measurable t on the real bars", BLOCK)
    rng = np.random.default_rng(seed)
    null: list[float] = []
    failed = 0
    for _ in range(max(0, int(n_permutations))):
        st = _safe(evaluate, _block_permute(bars, block=block, rng=rng))
        if st is None or not math.isfinite(st.t_stat):
            failed += 1
            continue
        null.append(float(st.t_stat))
    return _null_verdict(name, real, null, failed, severity=BLOCK,
                         what=f"the block-permuted tape (blocks of {block})")


def regime_permutation(evaluate: Evaluate, bars: pd.DataFrame, *,
                       regime: pd.Series | None = None, n_permutations: int = PERMUTATIONS,
                       block: int = PERM_BLOCK, seed: int = 0) -> Verdict:
    """(2) Is the conditioner a STATE, or a second free parameter with a state's name on it?

    The frame carries a `regime` column; the null shuffles that column in blocks and leaves the
    prices alone, so tape, clock and rule are unchanged and only the labelling moves. An edge that
    survives relabelled regimes was never conditioned on anything.
    """
    name = "regime_permutation"
    if regime is None:
        return _unmeasured(name, "no regime series supplied")
    reg = pd.Series(regime).reindex(bars.index)
    if int(reg.notna().sum()) * 2 < len(bars):
        return _unmeasured(name, "the regime series covers under half the bars once aligned",
                           basis={"n_labelled": int(reg.notna().sum()), "n_bars": len(bars)})
    framed = bars.copy()
    framed["regime"] = reg
    real = _safe(evaluate, framed)
    if not _usable(real) or real is None:
        return _unmeasured(name, "the strategy produced no measurable t with real regime labels")
    rng = np.random.default_rng(seed)
    values = reg.to_numpy()
    null: list[float] = []
    failed = 0
    for _ in range(max(0, int(n_permutations))):
        order = _block_order(values.size, block, rng)
        if order is None:
            failed += 1
            continue
        shuffled = framed.copy()
        shuffled["regime"] = values[order]
        st = _safe(evaluate, shuffled)
        if st is None or not math.isfinite(st.t_stat):
            failed += 1
            continue
        null.append(float(st.t_stat))
    return _null_verdict(name, real, null, failed, severity=REPORT,
                         what=f"block-shuffled regime labels (blocks of {block})")


def nearby_instrument_placebo(evaluate: Evaluate, bars: pd.DataFrame, *,
                              bars_neighbour: pd.DataFrame | None = None,
                              real: TradeStats | None = None) -> Verdict:
    """(3) The same code on a correlated instrument the mechanism says must NOT carry it.

    ABSOLUTE t ON THE PLACEBO, which is the point rather than a convenience: a neighbour scoring
    t = -6 has not failed to carry the mechanism, it is carrying something just as strong and
    mirrored, which is what a shared construction artefact looks like. `same_sign` is reported so
    a caller whose mechanism predicts the neighbour SHOULD carry it reads the other direction;
    this verdict grades the default prediction, that it should not.
    """
    name = "nearby_instrument_placebo"
    if bars_neighbour is None:
        return _unmeasured(name, "no neighbour instrument supplied")
    real = real if real is not None else _safe(evaluate, bars)
    if not _usable(real) or real is None or real.t_stat == 0.0:
        return _unmeasured(name, "the strategy produced no measurable t on the real bars")
    placebo = _safe(evaluate, bars_neighbour)
    if placebo is None or not math.isfinite(placebo.t_stat):
        return _unmeasured(name, "the strategy produced no measurable t on the neighbour",
                           basis={"n_placebo": 0 if placebo is None else int(placebo.n)})
    ratio = abs(placebo.t_stat) / abs(real.t_stat)
    passed = bool(ratio < PLACEBO_T_RATIO)
    return Verdict(
        name=name, passed=passed, statistic=float(ratio), threshold=PLACEBO_T_RATIO,
        why=(f"placebo |t|={abs(placebo.t_stat):.2f} is {ratio:.2f}x the real |t|="
             f"{abs(real.t_stat):.2f}; the neighbour "
             f"{'does not carry' if passed else 'ALSO carries'} the result"),
        basis={"real_t": _num(real.t_stat), "placebo_t": _num(placebo.t_stat),
               "placebo_n": int(placebo.n), "real_n": int(real.n),
               "same_sign": bool(np.sign(placebo.mean_r) == np.sign(real.mean_r))},
    )


def delayed_entry(evaluate: Evaluate, bars: pd.DataFrame, *, delays: Sequence[int] = DELAYS,
                  real: TradeStats | None = None) -> Verdict:
    """(4) Arrive k bars late at the same decision. The fill-artefact prosecutor.

    The verdict is the 1-BAR reading; 5 and 15 are the decay curve, reported because the SHAPE
    says what kind of edge it is (a slow decay is a real effect with a horizon, a cliff at 1 is an
    execution assumption). Retention is measured on expectancy, not on t, because t also moves
    with the trade count and a late arrival legitimately loses trades at the tape's edge.
    """
    name = "delayed_entry"
    real = real if real is not None else _safe(evaluate, bars)
    if real is None or real.n < MIN_TRADES or not math.isfinite(real.expectancy):
        return _unmeasured(name, "the strategy produced no measurable expectancy on real bars",
                           BLOCK)
    if real.expectancy <= 0.0:
        return _unmeasured(name, "real expectancy is not positive; there is nothing to retain",
                           BLOCK, {"real_expectancy": _num(real.expectancy)})
    # ZERO TRADES IS A MEASUREMENT, AND THE LOUDEST ONE THIS TEST MAKES: a rule whose entries all
    # vanish when the fill moves one bar was selecting on the fill price itself, so retention is 0
    # rather than unknown. UNMEASURED is kept for the frame that could not be built or the replay
    # that raised -- letting the worst case out through the gap reserved for missing inputs would
    # invert the test. A st.n of 0 is the first case, st is None the second.
    curve: dict[str, Any] = {}
    for k in delays:
        st = _safe(evaluate, _delay_entry_frame(bars, int(k)))
        if st is None:
            curve[str(int(k))] = {"measured": False}
        elif st.n == 0:
            curve[str(int(k))] = {"measured": True, "n": 0, "expectancy": None, "t_stat": None,
                                  "retention": 0.0}
        else:
            curve[str(int(k))] = {"measured": True, "n": int(st.n),
                                  "expectancy": _num(st.expectancy), "t_stat": _num(st.t_stat),
                                  "retention": _num(st.expectancy / real.expectancy)}
    first = str(int(delays[0])) if delays else ""
    head = curve.get(first) or {}
    if not head.get("measured") or head.get("retention") is None:
        return _unmeasured(name, f"the {first}-bar delayed frame could not be evaluated", BLOCK,
                           {"curve": curve})
    retention = float(head["retention"])
    passed = bool(retention >= DELAY_RETENTION)
    return Verdict(
        name=name, passed=passed, statistic=retention, threshold=DELAY_RETENTION, severity=BLOCK,
        why=(f"a {first}-bar delay retains {retention:.0%} of expectancy "
             f"(floor {DELAY_RETENTION:.0%}); "
             + ("the edge survives arriving late" if passed else
                "an edge that dies with one bar of delay is a fill artefact, not a market fact")),
        basis={"curve": curve, "real_expectancy": _num(real.expectancy), "real_n": int(real.n),
               "construction": ("close/volume real, open/high/low taken k bars later, bar "
                                "repaired to stay quotable")},
    )


def subperiod_removal(evaluate: Evaluate, bars: pd.DataFrame, *, n_parts: int = SUBPERIODS,
                      real: TradeStats | None = None) -> Verdict:
    """(5) Drop each contiguous fifth in turn. Catches one episode wearing a calendar.

    A SIGN FLIP AND A THIN FIFTH ARE NOT THE SAME FINDING: a fold whose t falls to 0.8 is an edge
    that needed that stretch, a fold whose MEAN flips sign is a different strategy that happened
    to average out. Only the second blocks, and the verdict's severity says which happened.
    """
    name = "subperiod_removal"
    real = real if real is not None else _safe(evaluate, bars)
    if not _usable(real) or real is None:
        return _unmeasured(name, "the strategy produced no measurable t on the real bars")
    parts = max(2, int(n_parts))
    n = len(bars)
    if n < parts * MIN_BARS:
        return _unmeasured(name, f"{n} bars cannot be cut into {parts} removable parts")
    edges = [round(i * n / parts) for i in range(parts + 1)]
    folds: list[dict[str, Any]] = []
    ts: list[float] = []
    flipped: list[int] = []
    real_sign = float(np.sign(real.mean_r))
    for i in range(parts):
        st = _safe(evaluate, _drop_slice(bars, edges[i], edges[i + 1]))
        row: dict[str, Any] = {"removed": [edges[i], edges[i + 1]], "measured": _usable(st)}
        if st is not None and row["measured"]:
            row.update({"n": int(st.n), "t_stat": _num(st.t_stat), "mean_r": _num(st.mean_r)})
            ts.append(float(st.t_stat))
            if float(np.sign(st.mean_r)) != real_sign:
                flipped.append(i)
        folds.append(row)
    if len(ts) < MIN_TRADES:
        return _unmeasured(name, f"only {len(ts)} of {parts} folds produced a measurable t",
                           basis={"folds": folds})
    min_t = float(min(ts))
    sign_flip = bool(flipped)
    passed = bool(min_t > SUBPERIOD_MIN_T and not sign_flip)
    return Verdict(
        name=name, passed=passed, statistic=min_t, threshold=SUBPERIOD_MIN_T,
        severity=BLOCK if sign_flip else REPORT,
        why=(f"worst of {len(ts)} fifth-removals t={min_t:.2f} (floor {SUBPERIOD_MIN_T})"
             + (f"; SIGN FLIPPED on fold(s) {flipped}" if sign_flip else "; sign held")),
        basis={"folds": folds, "min_t": _num(min_t), "n_measured_folds": len(ts),
               "sign_flipped_folds": flipped, "real_t": _num(real.t_stat)},
    )


def worst_year_removal(evaluate: Evaluate, bars: pd.DataFrame, *,
                       real: TradeStats | None = None) -> Verdict:
    """(6) Remove the year it would be worst to lose -- the one contributing the most R.

    THE BEST YEAR IS THE WORST ONE TO OWN, hence the name. The year is found by REMOVAL rather
    than by slicing: each calendar year is dropped in turn and the one whose absence costs the
    most total R is the contributor. Scoring a sliced-out year on its own would judge a different
    strategy, one whose warm-up, state and neighbouring context were cut away with it.
    """
    name = "worst_year_removal"
    real = real if real is not None else _safe(evaluate, bars)
    if real is None or real.n < MIN_TRADES or not math.isfinite(real.mean_r):
        return _unmeasured(name, "the strategy produced no measurable R on the real bars", BLOCK)
    try:
        years = pd.DatetimeIndex(bars.index).year.to_numpy()
    except (TypeError, ValueError):
        return _unmeasured(name, "the bars are not indexed by time; calendar years are undefined",
                           BLOCK)
    labels = sorted({int(y) for y in years})
    if len(labels) < 2:
        return _unmeasured(name, f"{len(labels)} calendar year(s) in the index; "
                                 "removing the only year leaves nothing to test", BLOCK,
                           {"years": labels})
    total_r = float(real.n * real.mean_r)
    per_year: dict[str, Any] = {}
    best: tuple[float, int, TradeStats] | None = None
    for y in labels:
        st = _safe(evaluate, bars[years != y])
        if st is None or not _usable(st):
            per_year[str(y)] = {"measured": False}
            continue
        contributed = total_r - float(st.n * st.mean_r)
        per_year[str(y)] = {"measured": True, "n_without": int(st.n),
                            "t_without": _num(st.t_stat), "r_contributed": _num(contributed)}
        if best is None or contributed > best[0]:
            best = (contributed, y, st)
    if best is None:
        return _unmeasured(name, "no year-removal produced a measurable t", BLOCK,
                           {"years": per_year})
    contributed, year, without = best
    passed = bool(without.t_stat > WORST_YEAR_MIN_T)
    return Verdict(
        name=name, passed=passed, statistic=float(without.t_stat), threshold=WORST_YEAR_MIN_T,
        severity=BLOCK,
        why=(f"{year} contributed {contributed:.2f}R of {total_r:.2f}R; without it "
             f"t={without.t_stat:.2f} (floor {WORST_YEAR_MIN_T})"),
        basis={"best_year": int(year), "r_contributed": _num(contributed),
               "total_r": _num(total_r), "t_without_best_year": _num(without.t_stat),
               "n_without": int(without.n), "years": per_year},
    )


def transfer_test(evaluate: Evaluate, bars: pd.DataFrame, *,
                  bars_alt: pd.DataFrame | None = None, alt_is_same_instrument: bool = False,
                  real: TradeStats | None = None) -> Verdict:
    """(7) Another instrument the mechanism PREDICTS carries it. A fit transfers nowhere."""
    name = "transfer_test"
    if bars_alt is None:
        return _unmeasured(name, "no transfer instrument supplied")
    if alt_is_same_instrument:
        return _unmeasured(name, "bars_alt is a second SOURCE of the same instrument; that is "
                                 "data_source_substitution's input, not a transfer")
    real = real if real is not None else _safe(evaluate, bars)
    if not _usable(real) or real is None:
        return _unmeasured(name, "the strategy produced no measurable t on the real bars")
    alt = _safe(evaluate, bars_alt)
    if alt is None or alt.n < MIN_TRADES or not math.isfinite(alt.t_stat):
        return _unmeasured(name, "the strategy produced no measurable t on the transfer "
                                 "instrument", basis={"n_alt": 0 if alt is None else int(alt.n)})
    same_sign = bool(np.sign(alt.mean_r) == np.sign(real.mean_r))
    passed = bool(same_sign and alt.t_stat > TRANSFER_MIN_T)
    return Verdict(
        name=name, passed=passed, statistic=float(alt.t_stat), threshold=TRANSFER_MIN_T,
        why=(f"transfer t={alt.t_stat:.2f} on {alt.n} trades, sign "
             f"{'agrees' if same_sign else 'DISAGREES'} with the real mean"),
        basis={"real_t": _num(real.t_stat), "alt_t": _num(alt.t_stat), "alt_n": int(alt.n),
               "real_mean_r": _num(real.mean_r), "alt_mean_r": _num(alt.mean_r),
               "same_sign": same_sign},
    )


def data_source_substitution(evaluate: Evaluate, bars: pd.DataFrame, *,
                             bars_alt: pd.DataFrame | None = None,
                             alt_is_same_instrument: bool = False,
                             real: TradeStats | None = None) -> Verdict:
    """(8) The same instrument from a second SOURCE. Catches an edge inside a bar construction.

    Two vendors disagree about a bar's high, where the session boundary is and which ticks were
    real. An edge on only one of them is a property of that feed, and the desk cannot trade a feed.
    """
    name = "data_source_substitution"
    if bars_alt is None:
        return _unmeasured(name, "no second data source supplied")
    if not alt_is_same_instrument:
        return _unmeasured(name, "bars_alt is another instrument (alt_is_same_instrument=False); "
                                 "that is transfer_test's input, not a source substitution")
    real = real if real is not None else _safe(evaluate, bars)
    if real is None or real.n < MIN_TRADES or not math.isfinite(real.expectancy):
        return _unmeasured(name, "the strategy produced no measurable expectancy on real bars")
    alt = _safe(evaluate, bars_alt)
    if alt is None or alt.n < MIN_TRADES or not math.isfinite(alt.expectancy):
        return _unmeasured(name, "the strategy produced no measurable expectancy on the second "
                                 "source", basis={"n_alt": 0 if alt is None else int(alt.n)})
    gap = _rel_gap(real.expectancy, alt.expectancy)
    if not math.isfinite(gap):
        return _unmeasured(name, "real expectancy is zero; a relative agreement is undefined")
    passed = bool(gap <= SOURCE_EXPECTANCY_TOL)
    return Verdict(
        name=name, passed=passed, statistic=float(gap), threshold=SOURCE_EXPECTANCY_TOL,
        why=(f"expectancy {real.expectancy:.6f} vs {alt.expectancy:.6f} on the second source, "
             f"a {gap:.0%} gap (tolerance {SOURCE_EXPECTANCY_TOL:.0%})"),
        basis={"real_expectancy": _num(real.expectancy), "alt_expectancy": _num(alt.expectancy),
               "real_n": int(real.n), "alt_n": int(alt.n), "relative_gap": _num(gap)},
    )


def dual_engine(evaluate_a: Evaluate, evaluate_b: Evaluate, bars: pd.DataFrame) -> Verdict:
    """Two independent implementations of ONE strategy on ONE frame must agree.

    Outside `run_all` because it needs a second implementation only the caller can supply -- the
    desk's is `libs.validation.replay2` against `mt5desk.engine.run_backtest`, written from the
    contract rather than from the engine's source, which is the only way the comparison is
    evidence. Trade COUNT first: two engines that disagree about how many trades there were are
    not two opinions about one strategy, they are two strategies.
    """
    name = "dual_engine"
    a, b = _safe(evaluate_a, bars), _safe(evaluate_b, bars)
    if a is None or b is None or min(a.n, b.n) < MIN_TRADES:
        return _unmeasured(name, "one of the two engines produced no measurable trade set",
                           basis={"n_a": None if a is None else int(a.n),
                                  "n_b": None if b is None else int(b.n)})
    count_gap = abs(a.n - b.n) / max(a.n, b.n)
    exp_gap = _rel_gap(a.expectancy, b.expectancy)
    if not math.isfinite(exp_gap):
        return _unmeasured(name, "engine A's expectancy is zero; relative agreement is undefined",
                           basis={"n_a": int(a.n), "n_b": int(b.n)})
    counts_ok = bool(count_gap <= DUAL_COUNT_TOL)
    exp_ok = bool(exp_gap <= DUAL_EXPECTANCY_TOL)
    passed = bool(counts_ok and exp_ok)
    return Verdict(
        name=name, passed=passed, statistic=float(exp_gap), threshold=DUAL_EXPECTANCY_TOL,
        why=(f"trade counts {a.n} vs {b.n} ({count_gap:.0%}, tol {DUAL_COUNT_TOL:.0%}); "
             f"expectancy {a.expectancy:.6f} vs {b.expectancy:.6f} ({exp_gap:.0%}, tol "
             f"{DUAL_EXPECTANCY_TOL:.0%})"),
        basis={"n_a": int(a.n), "n_b": int(b.n), "trade_count_gap": _num(count_gap),
               "trade_count_tolerance": DUAL_COUNT_TOL, "expectancy_a": _num(a.expectancy),
               "expectancy_b": _num(b.expectancy), "expectancy_gap": _num(exp_gap),
               "counts_agree": counts_ok, "expectancy_agrees": exp_ok},
    )


def run_all(evaluate: Evaluate, bars: pd.DataFrame, *, bars_alt: pd.DataFrame | None = None,
            bars_neighbour: pd.DataFrame | None = None, regime: pd.Series | None = None,
            alt_is_same_instrument: bool = False, seed: int = 0) -> HostileReport:
    """The whole roster, in one pass, on one seed. This is the gauntlet stage.

    The real replay runs ONCE and is handed to every test, so a candidate is scored on the number
    the certificate quotes rather than on eight redraws of it. `bars_alt` is read by test 7 OR
    test 8 according to `alt_is_same_instrument`, never both: one frame cannot be another
    instrument and the same instrument, and the wrong reader would report agreement it did not
    measure.
    """
    real = _safe(evaluate, bars)
    verdicts = (
        timestamp_permutation(evaluate, bars, seed=seed, real=real),
        regime_permutation(evaluate, bars, regime=regime, seed=seed),
        nearby_instrument_placebo(evaluate, bars, bars_neighbour=bars_neighbour, real=real),
        delayed_entry(evaluate, bars, real=real),
        subperiod_removal(evaluate, bars, real=real),
        worst_year_removal(evaluate, bars, real=real),
        transfer_test(evaluate, bars, bars_alt=bars_alt,
                      alt_is_same_instrument=alt_is_same_instrument, real=real),
        data_source_substitution(evaluate, bars, bars_alt=bars_alt,
                                 alt_is_same_instrument=alt_is_same_instrument, real=real),
    )
    return HostileReport(verdicts=verdicts, seed=int(seed), real=real)
