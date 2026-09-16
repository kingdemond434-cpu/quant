"""THE EVALUATOR LAB -- the desk's ATTACKS evolve; the reality they are judged against does not.

THE FAILURE THIS EXISTS FOR. `hostile.py` is eight fixed adversaries and `redteam.py` four fixed
placebos, and both are excellent the first time a search meets them. They are a STATIC battery,
and a miner running ten thousand cells an hour against a static battery is doing gradient descent
on the battery. Nothing notices: the survivors keep clearing the same eight gates, the gates keep
reporting PASS, and the question has quietly changed from "is this an edge" to "does this clear
these eight". The desk has paid the fee in the other direction already -- an FVG cell at t=+9.0
that nothing objected to until `delayed_entry` was written, fifteen t-units later. An attack that
does not exist catches nothing, and an attack everything has been fitted to catches nothing.

THE RED QUEEN ANSWER. Every generation this lab proposes attack VARIANTS, measures each one's
DISCRIMINATING POWER against controls whose quality is KNOWN by construction, and keeps the ones
that separate a real edge from an artefact:

    power = P(pass | the planted edge) - P(pass | the artefacts)

over `--seeds` independent tapes, on MEASURED draws only -- an attack that cannot measure has no
power, and UNMEASURED never resolves into a pass or a fail (L1.28a).

    KEPT     power >= 0.60 AND it catches a negative control the standing battery lets through.
             The second clause is the point: an attack that agrees with the battery everywhere
             has perfect power and zero marginal value, and twelve tests that all catch the same
             artefact are one test wearing twelve names.
    RETIRED  power < 0.30 on two consecutive evaluations. Once is a draw, twice is a property.

THE IMMUTABLE WALL, and it is why this is safe to run on a clock. The lab evolves the
PROSECUTION and never touches the evidence: SEALED = ("lockbox", "forward_clock", "live_fills",
"real_costs"). No function here takes a sealed window, a forward clock, a real fill or a broker
cost -- inspect the signatures, a test does. Every control is SYNTHETIC, generated in this file
and DETERMINISTIC in its seed, so the anchor the attacks are scored against is the same tape
every generation: a battery that evolved against a moving reality would be measuring nothing.
The lab proposes attacks; OTHER organs run them, on IN-SAMPLE evidence. A lab that could reach
the holdout would be a lab that had already spent it. It promotes nothing, sizes nothing and
withdraws nothing.

THE FIRST THING IT FOUND, and the reason the control set has six members rather than four: NOT
ONE OF THE EIGHT HOSTILE TESTS CHARGES A COST. A mechanism that is real in the sequence, real in
both halves, real in every year and worth less per trade than a plausible round trip walks
through the entire standing battery untouched. `uneconomic_edge` is that control and the cost
families are what catch it.

THE ROSTER OF RECORD IS PROTECTED. The four wrapped hostile tests are seeded `protected` and are
never retired whatever their power. A specialist that catches one artefact in four scores 0.25 by
this definition, and `delayed_entry` is exactly such a specialist -- the one that caught the
fifteen t-units. Power is a PROMOTION criterion here, never a demotion criterion for what the
desk already stands on; their power is published anyway, because that number is the lab telling
the truth about its own metric.

DISAGREEMENT IS PRESERVED, NEVER VOTED. `judge()` returns every kept attack's verdict side by
side and names the pairs that disagree; averaging that away destroys the one bit worth reading.
`blocking` is the single actionable bit and only the protected roster can set it -- an attack
this lab invented reports, it does not block.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

if __package__ in (None, ""):  # pragma: no cover - `python libs/validation/evaluator_lab.py`
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from libs.validation.hostile import (
    BLOCK,
    MIN_BARS,
    MIN_TRADES,
    REPORT,
    Evaluate,
    TradeStats,
    Verdict,
    delayed_entry,
    stats_from_r,
    subperiod_removal,
    timestamp_permutation,
    worst_year_removal,
)

__all__ = ["GRID", "SEALED", "Attack", "Control", "Measurement", "battery", "controls_for",
           "judge", "keep_decision", "main", "measure", "propose", "run_generation",
           "synthetic_bars"]

ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = ROOT / "desks" / "mt5" / "data" / "evaluator_lab.json"
REPORT_PATH = ROOT / "desks" / "mt5" / "reports" / "EVALUATOR_LAB.json"

#: What this lab may never reach -- a constant, so the wall is something a test asserts on rather
#: than a paragraph somebody has to keep believing.
SEALED: tuple[str, ...] = ("lockbox", "forward_clock", "live_fills", "real_costs")

POSITIVE, NEGATIVE = "positive", "negative"
POWER_KEEP, POWER_RETIRE, RETIRE_STRIKES = 0.60, 0.30, 2
MIN_MEASURED_DRAWS, DEFAULT_SEEDS, MAX_RETIRED = 2, 5, 200
CAUGHT_RATE = 0.50
N_MUTATE, N_FRESH = 3, 3
#: Cheaper than hostile's 20: this null is rebuilt for every variant on every control on every
#: seed, and the lab ranks attacks against each other rather than certifying a cell.
PERMUTATIONS, MISSING_DRAWS = 8, 3
COST_RETENTION, MISSING_RETENTION, NEIGHBOUR_RETENTION, STACK_RETENTION = 0.25, 0.50, 0.50, 0.25
COLLAPSE_RATIO, REGIME_MIN_T = 0.50, 0.50
#: The control tape's constants. UNIT is one R in price fraction, HOLD the planted horizon; the
#: fill artefact sits at a different hour so two controls can share one tape.
UNIT, HOLD, SHOCK_HOUR, ARTEFACT_HOUR = 0.004, 6, 0, 9
CONTROL_YEARS, CONTROL_DRIFT = 2.2, 6.7e-5

AttackFn = Callable[..., Verdict]
EvaluateWith = Callable[[Mapping[str, float]], Evaluate]


# --------------------------------------------------------------------------------- small helpers


def _num(x: float | None) -> float | None:
    if x is None:
        return None
    f = float(x)
    return round(f, 6) if math.isfinite(f) else None


def _key(family: str, params: Mapping[str, Any]) -> str:
    if not params:
        return family
    inner = ",".join(f"{k}={v:g}" if isinstance(v, float) else f"{k}={v}"
                     for k, v in sorted(params.items()))
    return f"{family}[{inner}]"


def _unmeasured(name: str, why: str, basis: dict[str, Any] | None = None) -> Verdict:
    return Verdict(name=name, passed=None, statistic=None, threshold=None, why=why,
                   basis=basis or {}, severity=REPORT)


def _replay(evaluate: Evaluate, frame: pd.DataFrame | None) -> TradeStats | None:
    """The caller's replay on a frame it did not choose; a crash is a datum, never an exception."""
    if frame is None or len(frame) < MIN_BARS:
        return None
    try:
        out = evaluate(frame)
    except Exception:
        return None
    return out if isinstance(out, TradeStats) else None


def _base(evaluate: Evaluate, bars: pd.DataFrame, name: str) -> tuple[TradeStats | None, Verdict]:
    """The real reading a retention attack is measured against, or the reason there is none."""
    real = _replay(evaluate, bars)
    if real is None or real.n < MIN_TRADES or not math.isfinite(real.expectancy):
        return None, _unmeasured(name, "no measurable expectancy on the real bars")
    if real.expectancy <= 0.0:
        return None, _unmeasured(name, "real expectancy is not positive; nothing to retain")
    return real, _unmeasured(name, "")


def _retention(name: str, real: TradeStats, draws: Sequence[TradeStats | None], floor: float,
               what: str, basis: dict[str, Any] | None = None) -> Verdict:
    """MEDIAN retention of expectancy across the attack's draws -- one lucky draw is not a result.

    Zero surviving trades is 0.0 and not UNMEASURED: a rule whose entries all vanish under the
    attack was selecting on what the attack removed, which is the loudest reading available.
    UNMEASURED is kept for the frame that could not be built.
    """
    rets = [0.0 if st.n == 0 else float(st.expectancy / real.expectancy)
            for st in draws if st is not None]
    rets = [r for r in rets if math.isfinite(r)]
    if not rets:
        return _unmeasured(name, f"{what} produced no replayable frame", basis)
    med = float(np.median(rets))
    passed = bool(med >= floor)
    return Verdict(name=name, passed=passed, statistic=med, threshold=floor, severity=REPORT,
                   why=(f"{what} retains {med:.0%} of expectancy across {len(rets)} draw(s), "
                        f"floor {floor:.0%}; the result "
                        + ("survives it" if passed else "does NOT survive it")),
                   basis={"retentions": [_num(r) for r in rets], "median_retention": _num(med),
                          "real_expectancy": _num(real.expectancy), "real_n": int(real.n),
                          **(basis or {})})


# ------------------------------------------------------------------------------------ transforms


def _delay(bars: pd.DataFrame, k: int) -> pd.DataFrame | None:
    """Decision tape real, execution tape k bars on. `hostile.delayed_entry` owns the reasoning."""
    if k <= 0 or len(bars) - k < MIN_BARS:
        return None
    out = bars.iloc[:-k].copy()
    for name in ("open", "high", "low"):
        out[name] = bars[name].to_numpy(dtype=float)[k:]
    o, c = out["open"].to_numpy(dtype=float), out["close"].to_numpy(dtype=float)
    out["high"] = np.maximum(out["high"].to_numpy(dtype=float), np.maximum(o, c))
    out["low"] = np.minimum(out["low"].to_numpy(dtype=float), np.minimum(o, c))
    return out


def _drop_random(bars: pd.DataFrame, frac: float, rng: np.random.Generator) -> pd.DataFrame | None:
    keep = rng.random(len(bars)) >= float(frac)
    return bars[keep] if int(keep.sum()) >= MIN_BARS else None


def _drop_sessions(bars: pd.DataFrame, n: int, rng: np.random.Generator) -> pd.DataFrame | None:
    """Whole calendar days removed -- an outage, not a scatter of missing prints."""
    if not isinstance(bars.index, pd.DatetimeIndex):
        return None
    days = bars.index.normalize()
    uniq = pd.Index(days.unique())
    if uniq.size <= int(n) + 2:
        return None
    keep = ~days.isin(uniq[rng.choice(uniq.size, size=int(n), replace=False)])
    return bars[keep] if int(keep.sum()) >= MIN_BARS else None


def _vol_half(bars: pd.DataFrame, half: str, window: int = 24) -> pd.DataFrame | None:
    """The bars on one side of the realised-vol median -- a regime split the tape declares."""
    c = bars["close"].to_numpy(dtype=float)
    if c.size < window * 2 or not np.all(c > 0.0):
        return None
    sd = pd.Series(np.diff(np.log(c), prepend=float(np.log(c[0])))).rolling(
        window, min_periods=window).std().to_numpy()
    med = float(np.nanmedian(sd))
    if not math.isfinite(med):
        return None
    keep = ((sd >= med) if half == "high" else (sd < med)) & np.isfinite(sd)
    return bars[keep] if int(keep.sum()) >= MIN_BARS else None


def _basket_surrogate(bars: pd.DataFrame, basket: pd.Series) -> pd.DataFrame | None:
    """The instrument redrawn as its BETA on a basket: same gaps, same wicks, same clock, and a
    close-to-close return that is nothing but the common factor scaled. Anything still paying on
    this frame was never idiosyncratic."""
    b = pd.to_numeric(pd.Series(basket).reindex(bars.index), errors="coerce").to_numpy(dtype=float)
    o, h, lo, c = (bars[k].to_numpy(dtype=float) for k in ("open", "high", "low", "close"))
    if b.size < MIN_BARS or not np.all(np.isfinite(b)) or not np.all(b > 0.0):
        return None
    if not all(np.all(np.isfinite(a)) and np.all(a > 0.0) for a in (o, h, lo, c)):
        return None
    ln_o, ln_h, ln_l, ln_c = (np.log(a) for a in (o, h, lo, c))
    r, f = np.diff(ln_c), np.diff(np.log(b))
    var = float(f.var())
    if var <= 0.0:
        return None
    new_c = np.concatenate([ln_c[:1], ln_c[0] + np.cumsum(float(np.cov(r, f)[0, 1] / var) * f)])
    new_o = np.concatenate([ln_o[:1], new_c[:-1] + (ln_o[1:] - ln_c[:-1])])
    up, dn = ln_h - np.maximum(ln_o, ln_c), np.minimum(ln_o, ln_c) - ln_l
    out = bars.copy()
    out["open"], out["close"] = np.exp(new_o), np.exp(new_c)
    out["high"], out["low"] = (np.exp(np.maximum(new_o, new_c) + up),
                               np.exp(np.minimum(new_o, new_c) - dn))
    return out


def _charge(real: TradeStats, per_trade: float) -> TradeStats:
    return stats_from_r([r - float(per_trade) for r in real.per_trade_r])


def _bump(value: float, rel: float, sign: int) -> float:
    """One step along a parameter axis; an integral knob moves by at least a whole unit."""
    v = float(value)
    return (v + sign * max(1.0, round(abs(v) * float(rel))) if v.is_integer()
            else v * (1.0 + sign * float(rel)))


# ---------------------------------------------------------------------------------- the families


def _a_permutation(evaluate: Evaluate, bars: pd.DataFrame, *, block: int = 24,
                   n_permutations: int = PERMUTATIONS, seed: int = 0, **_: Any) -> Verdict:
    """Day ordering destroyed, clock kept. The block size is the parameter family: 6, 24, 96."""
    return timestamp_permutation(evaluate, bars, n_permutations=int(n_permutations),
                                 block=int(block), seed=int(seed))


def _a_cost(evaluate: Evaluate, bars: pd.DataFrame, *, cost_r: float = 0.05, mult: float = 2.0,
            floor: float = COST_RETENTION, name: str = "cost_multiplier", **_: Any) -> Verdict:
    """Charge `cost_r * mult` R to every trade -- the cheapest most-lethal question there is.

    `spread_shock` is the same machinery under a different claim: not a worse cost model but a
    spread REGIME the desk has met. They evolve separate parameters, because a result that
    survives a 3x cost model and not a x5 spread day is a different finding from one that
    survives neither.
    """
    real, veto = _base(evaluate, bars, name)
    if real is None:
        return veto
    if not real.per_trade_r:
        return _unmeasured(name, "the replay returned no per-trade R; a cost cannot be charged")
    charged = float(cost_r) * float(mult)
    return _retention(name, real, [_charge(real, charged)], float(floor),
                      f"a {charged:.3f}R charge per trade ({mult:g}x {cost_r:g}R)",
                      {"cost_r": _num(cost_r), "multiplier": _num(mult),
                       "charged_r": _num(charged)})


def _a_missing(evaluate: Evaluate, bars: pd.DataFrame, *, frac: float = 0.05, n_sessions: int = 0,
               n_draws: int = MISSING_DRAWS, floor: float = MISSING_RETENTION, seed: int = 0,
               name: str = "missing_bars", **_: Any) -> Verdict:
    """Data the desk did not get: a scatter of dropped bars, or whole sessions gone."""
    real, veto = _base(evaluate, bars, name)
    if real is None:
        return veto
    rng = np.random.default_rng(int(seed))
    whole = int(n_sessions) > 0
    draws = [_replay(evaluate, _drop_sessions(bars, int(n_sessions), rng) if whole
                     else _drop_random(bars, float(frac), rng)) for _ in range(int(n_draws))]
    what = (f"removing {int(n_sessions)} whole sessions" if whole
            else f"dropping {float(frac):.0%} of bars at random")
    return _retention(name, real, draws, float(floor), what,
                      {"frac": _num(frac), "n_sessions": int(n_sessions), "n_draws": int(n_draws)})


def _a_regime_transfer(evaluate: Evaluate, bars: pd.DataFrame, *, half: str = "high",
                       floor_t: float = REGIME_MIN_T, **_: Any) -> Verdict:
    """Does the result carry into the other volatility regime, or did it live in one of them?"""
    name = "regime_transfer"
    real = _replay(evaluate, bars)
    if real is None or real.n < MIN_TRADES or not math.isfinite(real.t_stat):
        return _unmeasured(name, "no measurable t on the real bars")
    side = _replay(evaluate, _vol_half(bars, str(half)))
    if side is None or side.n < MIN_TRADES or not math.isfinite(side.t_stat):
        return _unmeasured(name, f"the {half}-vol half produced no measurable t", {"half": half})
    same = bool(np.sign(side.mean_r) == np.sign(real.mean_r))
    return Verdict(name=name, passed=bool(same and side.t_stat > float(floor_t)), severity=REPORT,
                   statistic=float(side.t_stat), threshold=float(floor_t),
                   why=(f"the {half}-vol half scores t={side.t_stat:.2f} on {side.n} trades, sign "
                        f"{'agrees' if same else 'DISAGREES'} with the whole sample"),
                   basis={"half": str(half), "half_t": _num(side.t_stat), "half_n": int(side.n),
                          "real_t": _num(real.t_stat), "same_sign": same})


def _a_collapse(evaluate: Evaluate, bars: pd.DataFrame, *, basket: pd.Series | None = None,
                ratio: float = COLLAPSE_RATIO, **_: Any) -> Verdict:
    """The instrument redrawn as its beta on a basket. PASSES when the surrogate does NOT pay.

    Placebo-shaped on purpose, like `nearby_instrument_placebo`: a result that survives having
    every idiosyncratic return removed was a factor exposure wearing a strategy's clothes. It is
    UNMEASURED without a basket, because a collapse with nothing to collapse onto is not a
    lenient test, it is no test.
    """
    name = "correlation_collapse"
    if basket is None:
        return _unmeasured(name, "no basket supplied; there is nothing to collapse the tape onto")
    real = _replay(evaluate, bars)
    if real is None or real.n < MIN_TRADES or not math.isfinite(real.t_stat) or real.t_stat == 0.0:
        return _unmeasured(name, "no measurable t on the real bars")
    alt = _replay(evaluate, _basket_surrogate(bars, basket))
    if alt is None or alt.n < MIN_TRADES or not math.isfinite(alt.t_stat):
        return _unmeasured(name, "the basket-driven surrogate produced no measurable t")
    got = abs(alt.t_stat) / abs(real.t_stat)
    passed = bool(got < float(ratio))
    return Verdict(name=name, passed=passed, statistic=float(got), threshold=float(ratio),
                   severity=REPORT,
                   why=(f"the basket-driven surrogate scores |t|={abs(alt.t_stat):.2f}, "
                        f"{got:.2f}x the real |t|={abs(real.t_stat):.2f}; the result is "
                        + ("idiosyncratic" if passed else "REPRODUCED by the basket alone")),
                   basis={"real_t": _num(real.t_stat), "surrogate_t": _num(alt.t_stat),
                          "ratio": _num(got), "surrogate_n": int(alt.n)})


def _a_neighbourhood(evaluate: Evaluate, bars: pd.DataFrame, *,
                     evaluate_with: EvaluateWith | None = None,
                     base_params: Mapping[str, float] | None = None, rel: float = 0.15,
                     floor: float = NEIGHBOUR_RETENTION, **_: Any) -> Verdict:
    """Nudge every numeric knob and re-run. A peak with no shoulders is a selection, not a rule."""
    name = "parameter_neighbourhood"
    if evaluate_with is None or not base_params:
        return _unmeasured(name, "no evaluate_with / base_params supplied; the knobs are unknown")
    real, veto = _base(evaluate, bars, name)
    if real is None:
        return veto
    draws: list[TradeStats | None] = []
    moved: dict[str, list[float]] = {}
    for knob, value in base_params.items():
        moved[knob] = [_bump(float(value), float(rel), s) for s in (-1, 1)]
        draws += [_replay(evaluate_with({**dict(base_params), knob: v}), bars)
                  for v in moved[knob]]
    return _retention(name, real, draws, float(floor),
                      f"perturbing {len(base_params)} knob(s) by +-{float(rel):.0%}",
                      {"rel": _num(rel), "neighbourhood": moved})


def _a_stacked(evaluate: Evaluate, bars: pd.DataFrame, *, k: int = 1, frac: float = 0.05,
               cost_r: float = 0.05, mult: float = 1.0, floor: float = STACK_RETENTION,
               seed: int = 0, **_: Any) -> Verdict:
    """Late, thinned and charged at once -- the composite lane evolution proposes into.

    A cell meets all three at the same time in production and never one at a time, so the stack is
    not a harsher version of its parts; it is the only one of them shaped like a trading day.
    """
    name = "stacked_stress"
    real, veto = _base(evaluate, bars, name)
    if real is None:
        return veto
    frame = _delay(bars, int(k)) if int(k) > 0 else bars
    if frame is not None and float(frac) > 0.0:
        frame = _drop_random(frame, float(frac), np.random.default_rng(int(seed)))
    alt = _replay(evaluate, frame)
    charged = float(cost_r) * float(mult)
    if alt is not None and alt.per_trade_r and charged > 0.0:
        alt = _charge(alt, charged)
    return _retention(name, real, [alt], float(floor),
                      (f"a {int(k)}-bar delay, {float(frac):.0%} of bars dropped and a "
                       f"{charged:.3f}R charge, together"),
                      {"k": int(k), "frac": _num(frac), "charged_r": _num(charged)})


#: The roster. The three one-line wrappers stay lambdas on purpose -- they add a parameter axis to
#: a hostile test and nothing else, and a def apiece would say there was more to them.
FAMILIES: dict[str, AttackFn] = {
    "permutation": _a_permutation,
    "delayed_entry": lambda ev, bars, k=1, **_: delayed_entry(ev, bars, delays=(int(k),)),
    "subperiod_removal": lambda ev, bars, n_parts=5, **_: subperiod_removal(ev, bars,
                                                                           n_parts=int(n_parts)),
    "worst_year_removal": lambda ev, bars, **_: worst_year_removal(ev, bars),
    "cost_multiplier": _a_cost,
    "spread_shock": partial(_a_cost, name="spread_shock"),
    "missing_bars": _a_missing,
    "missing_sessions": partial(_a_missing, name="missing_sessions"),
    "regime_transfer": _a_regime_transfer,
    "correlation_collapse": _a_collapse,
    "parameter_neighbourhood": _a_neighbourhood,
    "stacked_stress": _a_stacked,
}

#: The axes evolution may move. An empty grid means the family is proposable only as it stands.
GRID: dict[str, dict[str, tuple[Any, ...]]] = {
    "permutation": {"block": (6, 24, 96)},
    "delayed_entry": {"k": (1, 2, 3, 5, 15)},
    "subperiod_removal": {"n_parts": (4, 5, 8)},
    "worst_year_removal": {},
    "cost_multiplier": {"cost_r": (0.03, 0.05, 0.08), "mult": (1.5, 2.0, 3.0)},
    "spread_shock": {"cost_r": (0.05, 0.08), "mult": (2.0, 5.0)},
    "missing_bars": {"frac": (0.05, 0.20)},
    "missing_sessions": {"n_sessions": (5, 20)},
    "regime_transfer": {"half": ("high", "low")},
    "correlation_collapse": {"ratio": (0.5, 0.75)},
    "parameter_neighbourhood": {"rel": (0.1, 0.25)},
    "stacked_stress": {"k": (1, 2), "frac": (0.05, 0.2), "mult": (1.0, 2.0)},
}

#: The desk's standing roster, wrapped. Seeded protected: proposed against, never retired.
SEED_BATTERY: tuple[tuple[str, dict[str, Any], str], ...] = (
    ("permutation", {"block": 24}, BLOCK), ("delayed_entry", {"k": 1}, BLOCK),
    ("subperiod_removal", {"n_parts": 5}, BLOCK), ("worst_year_removal", {}, BLOCK))


@dataclass(frozen=True)
class Attack:
    """A named, parameterised adversary: `(evaluate, bars, **params) -> Verdict`, and nothing else.

    `severity` is inherited from the protected roster and forced to REPORT for everything this lab
    invented: an evolved attack earns its way into the battery on measured power, it does not get
    the authority to stop a candidate on the same pass.
    """

    family: str
    params: Mapping[str, Any] = field(default_factory=dict)
    severity: str = REPORT
    protected: bool = False

    @property
    def key(self) -> str:
        return _key(self.family, self.params)

    def run(self, evaluate: Evaluate, bars: pd.DataFrame, **context: Any) -> Verdict:
        fn = FAMILIES.get(self.family)
        if fn is None:
            return _unmeasured(self.key, f"unknown attack family {self.family!r}")
        try:
            v = fn(evaluate, bars, **{**dict(self.params), **context})
        except Exception as exc:  # an attack that raises is UNMEASURED, never a silent pass
            return _unmeasured(self.key, f"the attack raised {type(exc).__name__}: {exc}")
        return replace(v, name=self.key, severity=v.severity if self.protected else REPORT)


# --------------------------------------------------------------------------------- the controls


def synthetic_bars(*, seed: int, years: float = CONTROL_YEARS, revert: float = 0.45,
                   drift: float = 0.0, edge_years: tuple[int, ...] | None = None,
                   start: str = "2023-01-01") -> tuple[pd.DataFrame, pd.Series]:
    """Hourly OHLCV with a KNOWN overnight mean-reversion, and the basket carrying its beta.

    The shock lands inside the SHOCK_HOUR bar and `revert` of it is handed back over the next HOLD
    bars, so the mechanism spans a block boundary and a block permutation genuinely severs cause
    from effect. `revert=0.0` gives a tape with no mechanism at all -- what the artefact controls
    are built on -- and `edge_years` confines it to named years, which is the windfall.
    """
    rng = np.random.default_rng(int(seed))
    n = round(float(years) * 365 * 24)
    index = pd.date_range(start, periods=n, freq="h", tz="UTC")
    hours, cal = np.asarray(index.hour), np.asarray(index.year)
    factor = rng.normal(0.0, 0.0006, n)
    shock = np.where(hours == SHOCK_HOUR, rng.normal(0.0, 0.004, n), 0.0)
    active = np.ones(n, dtype=bool) if edge_years is None else np.isin(cal, np.asarray(edge_years))
    rev = np.zeros(n)
    if float(revert) != 0.0:
        for i in np.flatnonzero((hours == SHOCK_HOUR) & active):
            rev[i + 1:min(i + 1 + HOLD, n)] -= float(revert) * shock[i] / HOLD
    ret = float(drift) + factor + rng.normal(0.0, 0.0006, n) + shock + rev
    log_c = np.log(2000.0) + np.cumsum(ret)
    log_o = np.empty(n)
    log_o[0] = log_c[0] - ret[0]
    log_o[1:] = log_c[:-1] + rng.normal(0.0, 0.00002, n - 1)
    wick = np.abs(rng.normal(0.0, 0.0006, n))
    bars = pd.DataFrame(
        {"open": np.exp(log_o), "high": np.exp(np.maximum(log_o, log_c) + wick),
         "low": np.exp(np.minimum(log_o, log_c) - wick), "close": np.exp(log_c),
         "volume": rng.integers(100, 1000, n).astype(float)}, index=index)
    return bars, pd.Series(np.exp(np.log(100.0) + np.cumsum(factor + float(drift))), index=index)


def _oc(bars: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray, int]:
    return (bars["open"].to_numpy(dtype=float), bars["close"].to_numpy(dtype=float),
            np.asarray(pd.DatetimeIndex(bars.index).hour), len(bars))


def _ev_planted(bars: pd.DataFrame, *, hold: int = HOLD) -> TradeStats:
    """Fade the overnight shock: decide on closes, enter at the NEXT open, exit `hold` bars on."""
    o, c, hrs, n = _oc(bars)
    h, pos = max(1, int(hold)), np.arange(n)
    idx = np.flatnonzero((hrs == SHOCK_HOUR) & (pos >= 1) & (pos + h < n))
    if idx.size == 0:
        return stats_from_r([])
    side = -np.sign(c[idx] / c[idx - 1] - 1.0)
    return stats_from_r((side * (c[idx + h] / o[idx + 1] - 1.0) / UNIT).tolist())


def _ev_same_bar(bars: pd.DataFrame, *, hold: int = HOLD) -> TradeStats:
    """THE FILL ARTEFACT: the entry bar's OWN close decides whether to enter at its open."""
    o, c, hrs, n = _oc(bars)
    h, pos = max(1, int(hold)), np.arange(n)
    idx = np.flatnonzero((hrs == ARTEFACT_HOUR) & (pos + h < n))
    idx = idx[c[idx] > o[idx]]
    return stats_from_r([] if idx.size == 0 else ((c[idx + h] / o[idx] - 1.0) / UNIT).tolist())


def _ev_long(bars: pd.DataFrame, *, hour: int = -1, stride: int = 0,
             hold: int = HOLD) -> TradeStats:
    """Long at the next open for `hold` bars, either every `stride`-th bar or at one hour of the
    day. Both are harmless -- until the drift pays the first and the tape chooses the second."""
    o, c, hrs, n = _oc(bars)
    h, pos = max(1, int(hold)), np.arange(n)
    idx = (np.arange(0, max(0, n - h - 1), max(1, int(stride))) if int(stride) > 0
           else np.flatnonzero((hrs == int(hour) % 24) & (pos >= 1) & (pos + h < n)))
    return stats_from_r([] if idx.size == 0 else ((c[idx + h] / o[idx + 1] - 1.0) / UNIT).tolist())


def _best_hour(bars: pd.DataFrame) -> int:
    best, best_mean = 0, -math.inf
    for h in range(24):
        st = _ev_long(bars, hour=h)
        if st.n >= MIN_TRADES and math.isfinite(st.mean_r) and st.mean_r > best_mean:
            best, best_mean = h, float(st.mean_r)
    return best


@dataclass(frozen=True)
class Control:
    """One strategy whose quality is KNOWN by construction, and the tape it was planted in."""

    name: str
    kind: str
    evaluate: Evaluate
    bars: pd.DataFrame
    context: dict[str, Any] = field(default_factory=dict)


def _with(fn: Callable[..., TradeStats], knob: str) -> EvaluateWith:
    def make(params: Mapping[str, float]) -> Evaluate:
        return partial(fn, **{knob: round(float(params.get(knob, 1.0)))})
    return make


def controls_for(seed: int, *, years: float = CONTROL_YEARS) -> tuple[Control, ...]:
    """One positive control and five negatives, all synthetic, all generated here.

    The negatives are five DIFFERENT ways to look like a certificate without being one, and the
    last two exist because the standing roster catches the first three cleanly and has nothing at
    all to say about these:

        selected_hour    a best-of-24 in-sample choice on a DRIFTLESS tape, so the whole of the
                         result is the selection. `random_entry` keeps the drifting tape, because
                         a monkey with no drift to harvest is not a tempting artefact.
        uneconomic_edge  the planted mechanism at a sixth of its amplitude: REAL sequence
                         information, real across both halves, real in every year, and a gross
                         expectancy smaller than a plausible round trip. THE HOSTILE ROSTER HAS NO
                         COST ADVERSARY -- not one of its eight tests charges a spread -- so this
                         one walks through the whole battery, and finding it is the first thing
                         this lab is for.

    That gap is the room evolution has to earn marginal value in, and a generation reporting no
    uncaught negative is reporting that the room has closed, not that it is idle.
    """
    edge, eb = synthetic_bars(seed=seed, years=years, revert=0.45)
    flat, fb = synthetic_bars(seed=seed + 1000, years=years, revert=0.0, drift=CONTROL_DRIFT)
    wind, wb = synthetic_bars(seed=seed + 2000, years=years, revert=0.45, edge_years=(2024,))
    noise, nb = synthetic_bars(seed=seed + 3000, years=years, revert=0.0)
    thin, tb = synthetic_bars(seed=seed + 4000, years=years, revert=0.08)
    hour = _best_hour(noise)
    spec: tuple[tuple[str, str, Evaluate, pd.DataFrame, pd.Series, Any, str, float], ...] = (
        ("planted_edge", POSITIVE, _ev_planted, edge, eb, _ev_planted, "hold", float(HOLD)),
        ("random_entry", NEGATIVE, partial(_ev_long, stride=37), flat, fb, _ev_long, "stride",
         37.0),
        ("same_bar_close", NEGATIVE, _ev_same_bar, edge, eb, _ev_same_bar, "hold", float(HOLD)),
        ("single_year_windfall", NEGATIVE, _ev_planted, wind, wb, _ev_planted, "hold",
         float(HOLD)),
        ("selected_hour", NEGATIVE, partial(_ev_long, hour=hour), noise, nb, _ev_long, "hour",
         float(hour)),
        ("uneconomic_edge", NEGATIVE, _ev_planted, thin, tb, _ev_planted, "hold", float(HOLD)),
    )
    return tuple(Control(nm, kind, ev, frame, {"basket": bk, "evaluate_with": _with(fn, knob),
                                               "base_params": {knob: val}})
                 for nm, kind, ev, frame, bk, fn, knob, val in spec)


# ----------------------------------------------------------------------------------- the scoring


@dataclass(frozen=True)
class Measurement:
    """One variant's discriminating power, and the per-control tally it was computed from."""

    key: str
    power: float | None
    positive_rate: float | None
    negative_rate: float | None
    per_control: dict[str, tuple[int, int]]
    caught: tuple[str, ...]
    draws: int

    def to_dict(self) -> dict[str, Any]:
        return {"key": self.key, "power": _num(self.power), "draws": self.draws,
                "positive_pass_rate": _num(self.positive_rate),
                "negative_pass_rate": _num(self.negative_rate), "caught": list(self.caught),
                "per_control": {k: {"passed": p, "measured": m}
                                for k, (p, m) in sorted(self.per_control.items())}}


def measure(attack: Attack, bundles: Sequence[Sequence[Control]]) -> Measurement:
    """Run one attack over every control on every seed. Rates are over MEASURED draws only.

    An UNMEASURED verdict is neither a pass nor a fail and leaves the denominator: an attack that
    cannot see a control has no opinion about it, and folding that into either rate would let an
    attack manufacture power out of its own blindness.
    """
    tally: dict[str, list[int]] = {}
    kinds: dict[str, str] = {}
    draws = 0
    for bundle in bundles:
        for ctl in bundle:
            kinds[ctl.name] = ctl.kind
            row = tally.setdefault(ctl.name, [0, 0])
            draws += 1
            v = attack.run(ctl.evaluate, ctl.bars, **ctl.context)
            if v.passed is None:
                continue
            row[1] += 1
            row[0] += int(bool(v.passed))
    pos = [tally[n] for n, k in kinds.items() if k == POSITIVE]
    neg = [tally[n] for n, k in kinds.items() if k == NEGATIVE]
    p_pass, p_meas = sum(r[0] for r in pos), sum(r[1] for r in pos)
    n_pass, n_meas = sum(r[0] for r in neg), sum(r[1] for r in neg)
    p_rate = p_pass / p_meas if p_meas else None
    n_rate = n_pass / n_meas if n_meas else None
    enough = p_meas >= MIN_MEASURED_DRAWS and n_meas >= MIN_MEASURED_DRAWS
    power = (p_rate - n_rate) if (enough and p_rate is not None and n_rate is not None) else None
    # CAUGHT IS A MAJORITY, NOT A TIE. An attack that fails an artefact on half its draws has not
    # caught it, and counting that as a catch would close the marginal-value room on a coin flip.
    caught = tuple(sorted(n for n, k in kinds.items() if k == NEGATIVE and tally[n][1] > 0
                          and tally[n][0] / tally[n][1] < CAUGHT_RATE))
    return Measurement(key=attack.key, power=power, positive_rate=p_rate, negative_rate=n_rate,
                       per_control={k: (v[0], v[1]) for k, v in tally.items()}, caught=caught,
                       draws=draws)


def keep_decision(m: Measurement, missed: set[str]) -> tuple[bool, str]:
    """The rule in one place: strong enough AND it adds something the battery does not have."""
    if m.power is None:
        return False, "UNMEASURED on the controls; absence is not a qualification"
    if m.power < POWER_KEEP:
        return False, f"power {m.power:.2f} below the {POWER_KEEP:.2f} keep floor"
    gained = sorted(set(m.caught) & missed)
    if not gained:
        return False, (f"power {m.power:.2f} but no marginal value: it catches nothing the "
                       "standing battery lets through")
    return True, f"power {m.power:.2f}; catches {', '.join(gained)}, which the battery passes"


def _retire_decision(history: Sequence[float | None]) -> bool:
    tail = list(history)[-RETIRE_STRIKES:]
    return (len(tail) == RETIRE_STRIKES and all(h is not None for h in tail)
            and all(float(h) < POWER_RETIRE for h in tail if h is not None))


# --------------------------------------------------------------------------- state and evolution


def _row(attack: Attack, generation: int) -> dict[str, Any]:
    return {"key": attack.key, "family": attack.family, "params": dict(attack.params),
            "severity": attack.severity, "protected": bool(attack.protected),
            "born_generation": int(generation), "power": None, "power_history": [], "caught": []}


def _attack_of(row: Mapping[str, Any]) -> Attack:
    return Attack(family=str(row.get("family", "")), params=dict(row.get("params") or {}),
                  severity=str(row.get("severity") or REPORT), protected=bool(row.get("protected")))


def seed_state(now: datetime | None = None) -> dict[str, Any]:
    return {"at": (now or datetime.now(tz=UTC)).isoformat(timespec="seconds"), "generation": 0,
            "battery": [_row(Attack(f, p, sev, protected=True), 0) for f, p, sev in SEED_BATTERY],
            "retired": []}


def load_state(path: Path | None = None) -> dict[str, Any]:
    try:
        doc = json.loads((path or STATE_PATH).read_text("utf-8"))
    except (OSError, ValueError):
        return seed_state()
    return doc if isinstance(doc, dict) and doc.get("battery") else seed_state()


def battery(state: Mapping[str, Any] | None = None) -> list[Attack]:
    """The attacks a gauntlet stage should run today. The lab's one outward-facing product."""
    doc = dict(state) if state is not None else load_state()
    return [_attack_of(r) for r in (doc.get("battery") or []) if isinstance(r, dict)]


def _pick(values: Sequence[Any], rng: np.random.Generator) -> Any:
    return values[int(rng.integers(len(values)))]


def _rank(row: Mapping[str, Any]) -> float:
    p = row.get("power")
    return -9.0 if p is None else float(p)


def propose(rows: Sequence[Mapping[str, Any]], excluded: set[str],
            rng: np.random.Generator) -> list[Attack]:
    """Mutate the strongest kept variants, then draw fresh family/parameter combinations."""
    seen = {str(r.get("key")) for r in rows} | set(excluded)
    out: list[Attack] = []
    for r in sorted(rows, key=_rank, reverse=True)[:N_MUTATE]:
        grid = GRID.get(str(r.get("family")), {})
        params = dict(r.get("params") or {})
        if grid:
            knob = _pick(sorted(grid), rng)
            params[knob] = _pick(grid[knob], rng)
        cand = Attack(family=str(r.get("family")), params=params)
        if cand.key not in seen:
            out.append(cand)
            seen.add(cand.key)
    names = sorted(FAMILIES)
    for _ in range(N_FRESH * 6):
        if len(out) >= N_MUTATE + N_FRESH:
            break
        fam = _pick(names, rng)
        cand = Attack(family=fam, params={k: _pick(v, rng) for k, v in GRID.get(fam, {}).items()})
        if cand.key not in seen:
            out.append(cand)
            seen.add(cand.key)
    return out


def _rule(seeds: int) -> dict[str, Any]:
    return {"power": ("pass rate on the positive control minus pass rate on the negative "
                      "controls, over MEASURED draws only"),
            "keep": (f"power >= {POWER_KEEP:.2f} AND it catches at least one negative control the "
                     "standing battery lets through"),
            "retire": (f"power < {POWER_RETIRE:.2f} on {RETIRE_STRIKES} consecutive evaluations; "
                       "the protected hostile roster is never retired"),
            "seeds": int(seeds), "sealed": list(SEALED),
            "wall": ("the lab proposes attacks only; it never reads a sealed window, a forward "
                     "clock, a real fill or a broker cost, and every control is synthetic")}


def run_generation(*, seeds: int = DEFAULT_SEEDS, state: Mapping[str, Any] | None = None,
                   bundles: Sequence[Sequence[Control]] | None = None,
                   candidates: Sequence[Attack] | None = None,
                   now: datetime | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    """One generation: measure the standing battery, retire, then judge this run's candidates."""
    doc = dict(state) if state is not None else load_state()
    gen = int(doc.get("generation", 0)) + 1
    stamp = (now or datetime.now(tz=UTC)).isoformat(timespec="seconds")
    if bundles is None:
        bundles = [controls_for(s) for s in range(max(1, int(seeds)))]
    seen: dict[str, Measurement] = {}
    kept_rows: list[dict[str, Any]] = []
    retired_now: list[dict[str, Any]] = []
    for row in [dict(r) for r in (doc.get("battery") or seed_state()["battery"])]:
        m = measure(_attack_of(row), bundles)
        row["power"] = _num(m.power)
        row["power_history"] = [*list(row.get("power_history") or [])[-7:], _num(m.power)]
        row["caught"] = list(m.caught)
        seen[m.key] = m
        if not row.get("protected") and _retire_decision(row["power_history"]):
            retired_now.append({**row, "retired_generation": gen, "retired_at": stamp,
                                "why": (f"power {row['power_history'][-RETIRE_STRIKES:]} under "
                                        f"{POWER_RETIRE:.2f} on {RETIRE_STRIKES} consecutive "
                                        "evaluations")})
        else:
            kept_rows.append(row)

    negatives = {c.name for b in bundles for c in b if c.kind == NEGATIVE}
    missed = negatives - {c for r in kept_rows for c in (r.get("caught") or [])}
    if candidates is None:
        candidates = propose(kept_rows, {str(r.get("key")) for r in (doc.get("retired") or [])},
                             np.random.default_rng(gen))
    verdicts: list[dict[str, Any]] = []
    kept_now: list[str] = []
    standing = {r["key"] for r in kept_rows}
    for cand in candidates:
        if cand.key in standing:
            continue
        m = measure(cand, bundles)
        ok, why = keep_decision(m, missed)
        verdicts.append({**m.to_dict(), "family": cand.family, "params": dict(cand.params),
                         "kept": ok, "why": why})
        if ok:
            kept_rows.append({**_row(cand, gen), "power": _num(m.power),
                              "power_history": [_num(m.power)], "caught": list(m.caught)})
            standing.add(cand.key)
            seen[m.key] = m
            kept_now.append(cand.key)

    retired = [*(doc.get("retired") or []), *retired_now][-MAX_RETIRED:]
    cols = ("key", "family", "params", "severity", "protected", "power", "power_history",
            "caught", "born_generation")
    report = {
        "at": stamp, "generation": gen, "n_battery": len(kept_rows), "n_retired": len(retired),
        "candidates_evaluated": len(verdicts), "kept_this_run": kept_now,
        "retired_this_run": [r["key"] for r in retired_now],
        "controls": _control_rates([seen[r["key"]] for r in kept_rows if r["key"] in seen],
                                   bundles),
        "uncaught_negatives": sorted(missed),
        "battery": [{k: r[k] for k in cols} for r in kept_rows], "candidates": verdicts,
        "retired": [{"key": r["key"], "why": r["why"],
                     "retired_generation": r["retired_generation"]} for r in retired[-20:]],
        "rule": _rule(len(bundles)),
        "status": ("MEASURED" if any(r.get("power") is not None for r in kept_rows)
                   else "UNMEASURED"),
    }
    return {"at": stamp, "generation": gen, "battery": kept_rows, "retired": retired}, report


def _control_rates(measurements: Sequence[Measurement],
                   bundles: Sequence[Sequence[Control]]) -> dict[str, dict[str, Any]]:
    """Per control, the fraction of the battery's MEASURED draws that passed it."""
    kinds = {c.name: c.kind for b in bundles for c in b}
    agg: dict[str, list[int]] = {name: [0, 0] for name in kinds}
    for m in measurements:
        for name, (p, meas) in m.per_control.items():
            row = agg.setdefault(name, [0, 0])
            row[0] += p
            row[1] += meas
    out: dict[str, dict[str, Any]] = {POSITIVE: {}, "negatives": {}}
    for name, (p, meas) in sorted(agg.items()):
        out[POSITIVE if kinds.get(name) == POSITIVE else "negatives"][name] = {
            "pass_rate": _num(p / meas) if meas else None, "passed": int(p),
            "measured": int(meas), "status": "MEASURED" if meas else "UNMEASURED"}
    return out


# ------------------------------------------------------------------------------------- the judge


def judge(evaluate: Evaluate, bars: pd.DataFrame, *, basket: pd.Series | None = None,
          evaluate_with: EvaluateWith | None = None,
          base_params: Mapping[str, float] | None = None,
          attacks: Sequence[Attack] | None = None) -> dict[str, Any]:
    """Every kept attack's verdict on one cell, side by side. NEVER a vote.

    Two attacks disagreeing is the most informative output this battery has, so both readings are
    kept and the pair is named. `blocking` is the single actionable bit, and only the protected
    roster can set it -- an attack this lab evolved reports, it does not withdraw a candidate.
    """
    roster = list(attacks) if attacks is not None else battery()
    context = {"basket": basket, "evaluate_with": evaluate_with, "base_params": base_params}
    found = [a.run(evaluate, bars, **context) for a in roster]
    passed = [v.name for v in found if v.passed is True]
    failed = [v.name for v in found if v.passed is False]
    blocked = [v.name for v in found if v.passed is False and v.severity == BLOCK]
    unmeasured = sum(1 for v in found if v.passed is None)
    pairs = [{"passed": a, "failed": b} for a in passed for b in failed]
    return {"at": datetime.now(tz=UTC).isoformat(timespec="seconds"), "n_attacks": len(found),
            "verdicts": [v.to_dict() for v in found], "n_passed": len(passed),
            "n_failed": len(failed), "n_unmeasured": unmeasured, "blocking": bool(blocked),
            "blocked_by": blocked, "disagreements": pairs, "sealed": list(SEALED),
            "why": (f"{len(passed)} passed, {len(failed)} failed, {unmeasured} unmeasured"
                    + (f"; {len(pairs)} disagreeing pair(s) kept side by side" if pairs else "")
                    + (f"; BLOCKED BY {', '.join(blocked)}" if blocked else ""))}


# --------------------------------------------------------------------------------------- the CLI


def _atomic(path: Path, doc: Mapping[str, Any]) -> None:
    """Write-then-rename. The chmod retry is the Windows lesson: os.replace onto a read-only
    destination is legal on POSIX and raises WinError 5 on the box that trades."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    try:
        os.replace(tmp, path)
    except PermissionError:
        path.chmod(0o644)
        os.replace(tmp, path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Evolve the desk's attacks against known controls.")
    ap.add_argument("--seeds", type=int, default=DEFAULT_SEEDS,
                    help="independent control tapes per variant (default %(default)s)")
    ap.add_argument("--dry-run", action="store_true", help="print the generation, write nothing")
    args = ap.parse_args(argv)
    state, report = run_generation(seeds=max(1, int(args.seeds)))
    head = (f"evaluator_lab: generation {report['generation']}; battery {report['n_battery']} "
            f"(kept {len(report['kept_this_run'])}, retired {len(report['retired_this_run'])}); "
            f"{report['candidates_evaluated']} candidate(s); uncaught negatives "
            f"{report['uncaught_negatives'] or 'none'}")
    if args.dry_run:
        print(json.dumps(report, indent=1, default=str))
        print(head + "  [DRY RUN -- nothing written]")
        return 0
    _atomic(STATE_PATH, state)
    _atomic(REPORT_PATH, report)
    rates = {**report["controls"][POSITIVE], **report["controls"]["negatives"]}
    print(f"{head}; control pass rates: "
          + ", ".join(f"{k} {v['pass_rate']}" for k, v in rates.items()))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
