"""THE MACRO MEASUREMENT LANE -- fifteen miners, every one of them controlled, split and nulled.

THE ONE THING THIS MODULE REFUSES TO DO. "Gold rose 0.3% in the hour after the Fed" is not a
finding. It is the sample mean of gold in an hour, filtered by a date list, and it is true of
hours on which nothing happened too. Every measurement here therefore runs against a MATCHED
CONTROL LEG built before the effect is read: the same instrument, the same hour of day, the
nearest days that were NOT event days, with the event's own window excluded. The number reported
is the event response MINUS the control mean, both are published, and `mean_raw` and
`mean_adjusted` sit next to each other on every row so a reader can see what the control removed.

SURPRISE IS NOT ACTUAL, AND THE ENGINE PROVES IT ROW BY ROW. A policy decision has a level and a
deviation, and they are different variables with different payers. `surprise_engine` computes
Surprise = Actual - Expected, using the CAPTURED CONSENSUS when the event carries one and the
PRIOR print otherwise, and stamps `basis` on every single observation so a run that fell back is
never read as a run that did not. It then regresses the control-adjusted response on the surprise
and on the level JOINTLY, publishes both t statistics, and names the `carrier`. A reaction that
loads on the level and not on the deviation is a trend, not an event study, and the engine says
so instead of reporting the deviation's coefficient alone.

FIVE ERAS, ALWAYS. pre_2015 / 2015_2019 / covid_2020_2021 / hiking_2022_2023 / post_2024. A macro
effect measured over 2018-2026 without a split is an average of at least three different worlds,
and the desk has been shown that arithmetic before. Every miner publishes the per-era table with
its per-era n, and a row that exists in one era is labelled a regime bet with the era named.

NULLS ARE NOT OPTIONAL. Every effect is charged either a PERMUTATION null (the conditioning label
is shuffled across days, the statistic recomputed, and p is the tail fraction) or a STATIONARY
BLOCK BOOTSTRAP (blocks preserve the serial dependence that makes a naive t statistic lie). The
null used is named on the row; a row without one is not published.

UNMEASURED IS A FIRST-CLASS RESULT (L1.28a). Every miner returns `unmeasured`, a list of
`{what, why}` naming, by axis, what it could not reach: an empty FRED axis, a symbol missing from
the COT map, an era with four observations, an operator with no implementation. The FRED axis on
this box is EMPTY -- seven of seven series failed on 2026-09-12 -- so the rates and curve miners
name every tenor they wanted rather than reporting a clean zero.

WHAT IS REUSED RATHER THAN REBUILT. `universe_policy` routes every symbol (no symbol list lives
here); `actor_atlas.resolve` turns selector tokens into instruments; `causal_lab.bh_fdr` charges
multiplicity; `shadow_discovery`'s permutation helper is used where it imports;
`graveyard_resurrection`'s GATE_CLASS and RESURRECTION tables classify and route failures; and
`transformation_miners` supplies the operator implementations the transfer miner drives. Each is
imported LAZILY, and when one is unreachable the miner says which and keeps going -- a department
that cannot run because a sibling module moved is a department that does not run.
"""
from __future__ import annotations

import importlib
import itertools
import json
import math
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REGION = "macro"
TAG = f"{REGION}:"

DESK = Path(__file__).resolve().parents[2]
ROOT = DESK.parents[1]
UNIVERSE_DIR = DESK / "data" / "universe"
AXES_DIR = DESK / "data" / "axes"
CALENDAR = DESK / "data" / "forced_flow_calendar.json"
MACRO_LEDGER = DESK / "data" / "macro" / "event_ledger.jsonl"

#: Sample floors. Below them a row is published WITH ITS n and never as a verdict.
MIN_EVENTS = 12
MIN_OBS = 60
MIN_ERA_EVENTS = 6
#: Draws for the permutation and bootstrap nulls.
N_PERM = 400
N_BOOT = 400
#: The matched control leg: days either side of the event, at the same hour, that are not events.
CONTROL_DAYS = 5
#: Deterministic seed -- a null whose p-value moves between runs is not a null.
SEED = 20260917
ALPHA = 0.05
#: Rows published per miner, so one loud symbol cannot crowd out the rest.
MAX_ROWS = 40

PERMUTATION = "permutation_of_the_conditioning_label"
BOOTSTRAP = "stationary_block_bootstrap"
UNMEASURED = "UNMEASURED"

#: The propagation chain the mandate names, in order. Each node is a SELECTOR, resolved against
#: MetaTrader's registry; a node with no executable instrument on this box is named and empty.
PROPAGATION_CHAIN: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("usd", ("symbol:EURUSD", "symbol:USDJPY", "symbol:GBPUSD")),
    ("rates", ("symbol:UST10Y", "symbol:UST05Y", "symbol:UKGILT")),
    ("vol", ("symbol:US500",)),
    ("equities", ("symbol:US500", "symbol:NAS100", "symbol:GER40", "symbol:JPN225")),
    ("gold", ("symbol:XAUUSD", "symbol:XAGUSD")),
    ("carry", ("symbol:AUDJPY", "symbol:NZDJPY", "symbol:EURCHF")),
    ("commodities", ("symbol:XTIUSD", "symbol:XBRUSD", "symbol:XNGUSD")),
    ("credit", ()),
)

#: The rate factors the rates and curve miners want. Every one absent is named, never dropped.
RATE_FACTORS: tuple[tuple[str, str], ...] = (
    ("fred:DGS2", "2y nominal"), ("fred:DGS5", "5y nominal"), ("fred:DGS10", "10y nominal"),
    ("fred:DGS30", "30y nominal"), ("fred:DFII10", "10y real"),
    ("fred:T10YIE", "10y breakeven"), ("fred:T10Y2Y", "10y-2y slope"),
)

#: The framework operator -> the `transformation_miners` implementation that answers it. An
#: operator with no implementation is BLOCKED by name, never dropped from the disposition table.
OPERATOR_IMPL: dict[str, str] = {
    "ORIGINAL": "", "INVERSE": "inverse", "ASSET_TRANSFER": "asset_transfer",
    "CROSS_ASSET": "cross_asset", "SESSION_TRANSFER": "session", "HORIZON_TRANSFER": "horizon",
    "REGIME_CONDITION": "regime", "RESIDUALIZATION": "residual",
    "FACTOR_NEUTRALIZATION": "residual", "EVENT_CONDITION": "macro_condition",
    "POSITIONING_CONDITION": "macro_condition", "VOLATILITY_CONDITION": "regime",
    "EXECUTION_VARIANT": "execution", "MECHANISM_COMBINATION": "interaction",
    # The region's own fallback vocabulary, so a framework that has not landed still maps.
    "asset_transfer": "asset_transfer", "horizon": "horizon", "session": "session",
    "regime": "regime", "residual": "residual", "interaction": "interaction",
    "inverse": "inverse", "execution": "execution", "cross_asset": "cross_asset",
    "macro_condition": "macro_condition", "failure_resurrection": "failure_resurrection",
    "parameter_neighborhood": "parameter_neighborhood", "information_substitution": "",
    "frequency_ladder": "horizon",
}


# =============================================================================================
# Lazy siblings -- a moved module is a named note, never an ImportError at import time
# =============================================================================================
def _mod(name: str) -> Any:
    for candidate in (name, f"desks.mt5.research.{name}"):
        try:
            return importlib.import_module(candidate)
        except ImportError:
            continue
    return None


def _registry() -> Any:
    try:
        return importlib.import_module("libs.moat.registry")
    except ImportError:
        return None


def _mandate() -> Any:
    # Package-relative FIRST: `japan/mandate.py` exists too, and a bare `import mandate` would
    # resolve to whichever package reached sys.path first.
    for name in (f"{__package__}.mandate", "mandate"):
        try:
            return importlib.import_module(name)
        except ImportError:
            continue
    return None


def _eras() -> tuple[tuple[str, str | None, str | None], ...]:
    m = _mandate()
    got = getattr(getattr(m, "MANDATE", None), "eras", None) if m is not None else None
    if got:
        return tuple(got)
    return (("pre_2015", None, "2015-01-01"), ("2015_2019", "2015-01-01", "2020-01-01"),
            ("covid_2020_2021", "2020-01-01", "2022-01-01"),
            ("hiking_2022_2023", "2022-01-01", "2024-01-01"), ("post_2024", "2024-01-01", None))


def _operators() -> tuple[str, ...]:
    m = _mandate()
    got = getattr(getattr(m, "MANDATE", None), "operators", None) if m is not None else None
    return tuple(got) if got else tuple(getattr(m, "OPERATORS", ()) or ())


def _dispositions() -> tuple[str, ...]:
    m = _mandate()
    got = getattr(getattr(m, "MANDATE", None), "dispositions", None) if m is not None else None
    return tuple(got) if got else ("GENERATED", "DUPLICATE", "ECONOMICALLY_INVALID",
                                   "DATA_BLOCKED", "PIT_BLOCKED", "COST_BLOCKED",
                                   "ALREADY_TESTED")


def _disposition(name: str, default: str) -> str:
    """A disposition from the region's own vocabulary; the default when the word is unknown."""
    known = _dispositions()
    return name if name in known else (default if default in known else known[-1])


# =============================================================================================
# Numbers
# =============================================================================================
def _num(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _rng(*key: Any) -> np.random.Generator:
    return np.random.default_rng(abs(hash(("macro", *key))) % (2**32) + SEED)


def _z(values: np.ndarray) -> np.ndarray:
    """Standardise, tolerating a degenerate column rather than emitting a RuntimeWarning."""
    if values.size == 0:
        return values
    sd = float(np.std(values, ddof=1)) if values.size > 1 else 0.0
    if not math.isfinite(sd) or sd <= 0:
        return np.zeros_like(values)
    return (values - float(np.mean(values))) / sd


def ols(y: np.ndarray, x: np.ndarray) -> dict[str, Any]:
    """Least squares of y on [1, x0, x1, ...] with the t of every slope. No library, no magic."""
    y = np.asarray(y, dtype=float)
    x = np.asarray(x, dtype=float)
    if x.ndim == 1:
        x = x[:, None]
    ok = np.isfinite(y) & np.all(np.isfinite(x), axis=1)
    y, x = y[ok], x[ok]
    n, k = x.shape[0], x.shape[1] + 1
    if n <= k:
        return {"n": int(n), "beta": [], "t": [], "r2": None,
                "why": f"n={n} does not exceed the {k} parameters"}
    design = np.column_stack([np.ones(n), x])
    beta, *_ = np.linalg.lstsq(design, y, rcond=None)
    resid = y - design @ beta
    dof = n - k
    sigma2 = float(resid @ resid) / dof
    try:
        cov = sigma2 * np.linalg.pinv(design.T @ design)
    except np.linalg.LinAlgError:
        return {"n": int(n), "beta": [], "t": [], "r2": None, "why": "singular design"}
    se = np.sqrt(np.clip(np.diag(cov), 0.0, None))
    with np.errstate(divide="ignore", invalid="ignore"):
        tstat = np.where(se > 0, beta / np.where(se > 0, se, 1.0), 0.0)
    tss = float(((y - y.mean()) ** 2).sum())
    return {"n": int(n), "beta": [float(b) for b in beta[1:]],
            "t": [float(t) for t in tstat[1:]], "intercept": float(beta[0]),
            "r2": None if tss <= 0 else float(1.0 - float(resid @ resid) / tss)}


def one_sample_t(values: np.ndarray) -> tuple[float | None, int]:
    v = np.asarray(values, dtype=float)
    v = v[np.isfinite(v)]
    if v.size < 3:
        return None, int(v.size)
    sd = float(np.std(v, ddof=1))
    if not math.isfinite(sd) or sd <= 0:
        return None, int(v.size)
    return float(np.mean(v) / (sd / math.sqrt(v.size))), int(v.size)


def permutation_p(stat: float, y: np.ndarray, labels: np.ndarray,
                  fn: Callable[[np.ndarray, np.ndarray], float], rng: np.random.Generator,
                  n: int = N_PERM) -> float | None:
    """The conditioning label is shuffled; p is the fraction of nulls at least as extreme."""
    y = np.asarray(y, dtype=float)
    labels = np.asarray(labels)
    if y.size < 4 or labels.size != y.size or not math.isfinite(stat):
        return None
    hits = 0
    draws = 0
    for _ in range(int(n)):
        value = fn(y, rng.permutation(labels))
        if not math.isfinite(value):
            continue
        draws += 1
        hits += int(abs(value) >= abs(stat))
    return None if draws == 0 else float((hits + 1) / (draws + 1))


def block_bootstrap_ci(values: np.ndarray, rng: np.random.Generator, n: int = N_BOOT,
                       block: int = 5, alpha: float = ALPHA) -> dict[str, Any]:
    """A stationary block bootstrap of the mean: blocks keep the serial dependence a t ignores."""
    v = np.asarray(values, dtype=float)
    v = v[np.isfinite(v)]
    if v.size < max(8, block * 2):
        return {"lo": None, "hi": None, "n": int(v.size), "null": BOOTSTRAP,
                "why": f"n={v.size} is below the block bootstrap floor"}
    means = np.empty(int(n), dtype=float)
    blocks = max(1, math.ceil(v.size / block))
    for i in range(int(n)):
        starts = rng.integers(0, v.size, size=blocks)
        take = np.concatenate([np.take(v, np.arange(s, s + block), mode="wrap") for s in starts])
        means[i] = float(take[: v.size].mean())
    lo, hi = np.quantile(means, [alpha / 2, 1 - alpha / 2])
    return {"lo": float(lo), "hi": float(hi), "n": int(v.size), "null": BOOTSTRAP,
            "excludes_zero": bool(lo > 0 or hi < 0)}


def bh_fdr(pvalues: Sequence[float], q: float = ALPHA) -> list[bool]:
    """Benjamini-Hochberg, through `causal_lab`'s implementation when it imports."""
    p = np.asarray([1.0 if v is None or not math.isfinite(v) else float(v) for v in pvalues])
    if p.size == 0:
        return []
    lab = _mod("causal_lab")
    if lab is not None and hasattr(lab, "bh_fdr"):
        try:
            keep, _ = lab.bh_fdr(p, q)
            return [bool(k) for k in np.asarray(keep).ravel()]
        except (TypeError, ValueError):
            pass
    order = np.argsort(p)
    ranked = p[order]
    thresh = q * (np.arange(1, p.size + 1) / p.size)
    passed = ranked <= thresh
    cut = int(np.max(np.nonzero(passed)[0]) + 1) if passed.any() else 0
    keep = np.zeros(p.size, dtype=bool)
    keep[order[:cut]] = True
    return [bool(k) for k in keep]


def era_of(when: Any) -> str:
    """Which of the five eras a stamp falls in. An unparseable stamp is its own bucket."""
    try:
        ts = pd.Timestamp(when)
    except (TypeError, ValueError):
        return UNMEASURED
    if ts.tzinfo is None:
        ts = ts.tz_localize(UTC)
    day = ts.tz_convert(UTC).strftime("%Y-%m-%d")
    for name, lo, hi in _eras():
        if (lo is None or day >= lo) and (hi is None or day < hi):
            return name
    return UNMEASURED


# =============================================================================================
# The bars, and the matched control leg
# =============================================================================================
def _as_utc(value: Any) -> datetime | None:
    try:
        ts = pd.Timestamp(value)
    except (TypeError, ValueError):
        return None
    if ts is pd.NaT:
        return None
    ts = ts.tz_localize(UTC) if ts.tzinfo is None else ts.tz_convert(UTC)
    return ts.to_pydatetime()


def bar_at(frame: pd.DataFrame, when: datetime) -> int | None:
    """The index of the first bar at or after `when`; None when the stamp is off the frame."""
    if frame is None or frame.empty:
        return None
    pos = int(frame.index.searchsorted(pd.Timestamp(when), side="left"))
    return None if pos <= 0 or pos >= len(frame) else pos


def response(frame: pd.DataFrame, when: datetime, horizon_bars: int) -> float | None:
    """Log return from the last bar CLOSING BEFORE the event to `horizon_bars` after it."""
    pos = bar_at(frame, when)
    if pos is None:
        return None
    end = pos - 1 + int(horizon_bars)
    if end >= len(frame) or pos - 1 < 0:
        return None
    close = frame["close"].to_numpy(dtype=float)
    base, tip = close[pos - 1], close[end]
    if not (math.isfinite(base) and math.isfinite(tip)) or base <= 0 or tip <= 0:
        return None
    return float(math.log(tip / base))


def matched_control(frame: pd.DataFrame, when: datetime, horizon_bars: int,
                    excluded: set[str], days: int = CONTROL_DAYS) -> tuple[float | None, int]:
    """The SAME instrument, the SAME hour of day, the nearest NON-EVENT days either side.

    This is the whole defence against reading the market's own drift as an event effect: the
    control window has the same clock, the same instrument and the same length, and differs from
    the treated window only in that nothing was scheduled.
    """
    out: list[float] = []
    for offset in [*range(-days, 0), *range(1, days + 1)]:
        day = when + timedelta(days=offset)
        if day.strftime("%Y-%m-%d") in excluded:
            continue
        got = response(frame, day, horizon_bars)
        if got is not None:
            out.append(got)
    if not out:
        return None, 0
    return float(np.mean(out)), len(out)


def controlled_responses(frame: pd.DataFrame, events: Sequence[Mapping[str, Any]],
                         horizon_bars: int, days: int = CONTROL_DAYS) -> dict[str, Any]:
    """Event responses, their matched control means, and the adjusted series. Nothing fitted."""
    stamps = [_as_utc(e.get("at") or e.get("when") or e.get("window_start_utc")) for e in events]
    excluded = {s.strftime("%Y-%m-%d") for s in stamps if s is not None}
    raw: list[float] = []
    ctrl: list[float] = []
    adj: list[float] = []
    kept: list[int] = []
    control_n = 0
    no_bar = 0
    no_control = 0
    for i, stamp in enumerate(stamps):
        if stamp is None:
            no_bar += 1
            continue
        r = response(frame, stamp, horizon_bars)
        if r is None:
            no_bar += 1
            continue
        c, n = matched_control(frame, stamp, horizon_bars, excluded, days)
        if c is None:
            no_control += 1
            continue
        raw.append(r)
        ctrl.append(c)
        adj.append(r - c)
        kept.append(i)
        control_n += n
    return {"raw": np.asarray(raw), "control": np.asarray(ctrl), "adjusted": np.asarray(adj),
            "kept": kept, "stamps": [stamps[i] for i in kept], "control_obs": control_n,
            "dropped_no_bar": no_bar, "dropped_no_control": no_control,
            "control_basis": f"same instrument, same hour, non-event days within +/-{days}d"}


# =============================================================================================
# The surprise engine
# =============================================================================================
def surprise_of(event: Mapping[str, Any]) -> tuple[float | None, float | None, str]:
    """(surprise, actual, basis). The basis is stamped so a fallback is never read as a capture."""
    actual = _num(event.get("actual"))
    expected = _num(event.get("expected") if event.get("expected") is not None
                    else event.get("consensus") if event.get("consensus") is not None
                    else event.get("forecast"))
    prior = _num(event.get("prior") if event.get("prior") is not None
                 else event.get("previous"))
    if actual is None:
        return None, None, "NO_ACTUAL"
    if expected is not None:
        return actual - expected, actual, "consensus"
    if prior is not None:
        return actual - prior, actual, "prior"
    return None, actual, "NO_EXPECTATION"


def surprise_engine(frame: pd.DataFrame, events: Sequence[Mapping[str, Any]], *,
                    horizon_bars: int, label: str = "", rng: np.random.Generator | None = None,
                    days: int = CONTROL_DAYS, n_perm: int = N_PERM,
                    min_events: int = MIN_EVENTS) -> dict[str, Any]:
    """Surprise = Actual - Expected, against a matched control, split by era, charged a null.

    The separation is the point. `t_surprise` and `t_actual` come from ONE joint regression of
    the control-adjusted response on both variables, so the surprise's coefficient is the part
    the LEVEL does not already explain. `carrier` names whichever of the two the reaction loads
    on, and `separates` is True only when the surprise carries it and clears the t=2 bar -- an
    honest answer to "is this an event study or a trend with a date filter".
    """
    gen = rng if rng is not None else _rng("surprise", label, horizon_bars)
    rows = list(events)
    measured = controlled_responses(frame, rows, horizon_bars, days)
    kept = measured["kept"]
    surprises: list[float] = []
    actuals: list[float] = []
    bases: list[str] = []
    eras: list[str] = []
    usable: list[int] = []
    basis_counts: dict[str, int] = {}
    for slot, idx in enumerate(kept):
        s, a, basis = surprise_of(rows[idx])
        basis_counts[basis] = basis_counts.get(basis, 0) + 1
        if s is None or a is None:
            continue
        surprises.append(s)
        actuals.append(a)
        bases.append(basis)
        eras.append(era_of(measured["stamps"][slot]))
        usable.append(slot)
    n = len(usable)
    out: dict[str, Any] = {
        "label": label, "horizon_bars": int(horizon_bars), "n_events_in": len(rows),
        "n_measured": len(kept), "n": n, "basis": basis_counts,
        "control_basis": measured["control_basis"], "control_obs": measured["control_obs"],
        "dropped_no_bar": measured["dropped_no_bar"],
        "dropped_no_control": measured["dropped_no_control"],
        "null": PERMUTATION, "floor": int(min_events),
    }
    # NAMED BEFORE THE EARLY RETURN, ON PURPOSE. The commonest real case on this box is a
    # calendar with dates and no actual, and that is exactly the case where an UNMEASURED axis
    # must still reach the caller by name -- a generic "verdict: UNMEASURED" with an empty
    # `unmeasured` list is the silent zero the law forbids.
    if basis_counts.get("NO_ACTUAL"):
        out.setdefault("unmeasured", []).append(
            {"what": f"{label}:actual", "why": f"{basis_counts['NO_ACTUAL']} events carry no "
             "actual; the desk's vintages hold forecast and previous only"})
    if basis_counts.get("NO_EXPECTATION"):
        out.setdefault("unmeasured", []).append(
            {"what": f"{label}:expectation", "why": f"{basis_counts['NO_EXPECTATION']} events "
             "carry neither a consensus nor a prior, so no surprise exists for them"})
    if n == 0:
        out["verdict"] = UNMEASURED
        out["why"] = ("no event carried both an actual and an expectation, or none landed on a "
                      "bar with a matched control")
        if not basis_counts:
            out.setdefault("unmeasured", []).append(
                {"what": f"{label}:bars", "why": "no event landed on a bar with a matched "
                 "control leg on this box"})
        return out
    adj = measured["adjusted"][usable]
    raw = measured["raw"][usable]
    ctrl = measured["control"][usable]
    sur = np.asarray(surprises, dtype=float)
    act = np.asarray(actuals, dtype=float)
    out["mean_raw"] = float(np.mean(raw))
    out["mean_control"] = float(np.mean(ctrl))
    out["mean_adjusted"] = float(np.mean(adj))
    out["control_removed"] = float(np.mean(raw) - np.mean(adj))
    t_mean, _ = one_sample_t(adj)
    out["t_mean_adjusted"] = t_mean
    joint = ols(adj, np.column_stack([_z(sur), _z(act)]))
    solo_s = ols(adj, _z(sur))
    solo_a = ols(adj, _z(act))
    out["joint"] = {"n": joint["n"], "beta_surprise": (joint["beta"] or [None, None])[0],
                    "beta_actual": (joint["beta"] or [None, None])[-1],
                    "t_surprise": (joint["t"] or [None, None])[0],
                    "t_actual": (joint["t"] or [None, None])[-1], "r2": joint.get("r2")}
    out["surprise_only"] = {"beta": (solo_s["beta"] or [None])[0],
                            "t": (solo_s["t"] or [None])[0], "r2": solo_s.get("r2")}
    out["actual_only"] = {"beta": (solo_a["beta"] or [None])[0],
                          "t": (solo_a["t"] or [None])[0], "r2": solo_a.get("r2")}
    ts = out["joint"]["t_surprise"]
    ta = out["joint"]["t_actual"]
    if ts is None or ta is None:
        out["carrier"] = UNMEASURED
        out["separates"] = False
    else:
        out["carrier"] = ("surprise" if abs(ts) > abs(ta) else
                          "actual" if abs(ta) > abs(ts) else "indistinguishable")
        out["separates"] = bool(out["carrier"] == "surprise" and abs(ts) >= 2.0)

    def _slope(y: np.ndarray, labels: np.ndarray) -> float:
        fit = ols(y, _z(np.asarray(labels, dtype=float)))
        return float((fit["t"] or [float("nan")])[0])

    out["p_permutation"] = permutation_p(
        float(ts) if ts is not None else float("nan"), adj, sur, _slope, gen, n_perm)
    out["bootstrap"] = block_bootstrap_ci(adj, gen)
    by_era: dict[str, Any] = {}
    for name in {*eras}:
        mask = np.asarray([e == name for e in eras])
        if not mask.any():
            continue
        fit = ols(adj[mask], _z(sur[mask])) if int(mask.sum()) > 3 else {"beta": [], "t": []}
        by_era[name] = {"n": int(mask.sum()), "mean_adjusted": float(np.mean(adj[mask])),
                        "beta": (fit["beta"] or [None])[0], "t": (fit["t"] or [None])[0],
                        "below_floor": bool(int(mask.sum()) < MIN_ERA_EVENTS)}
    out["by_era"] = by_era
    out["eras_present"] = sorted(by_era)
    signs = [v["beta"] for v in by_era.values()
             if v["beta"] is not None and not v["below_floor"]]
    out["sign_stable"] = bool(len(signs) >= 2 and (all(s > 0 for s in signs)
                                                   or all(s < 0 for s in signs)))
    out["below_floor"] = bool(n < min_events)
    out["verdict"] = ("UNDERPOWERED" if out["below_floor"] else
                      "SEPARATED" if out["separates"] else "MEASURED")
    return out


# =============================================================================================
# The context
# =============================================================================================
def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def default_bars(symbol: str, chart: str = "H1") -> pd.DataFrame | None:
    """The desk's own capture. Broker time carrying a UTC tzinfo -- measured, not assumed."""
    path = UNIVERSE_DIR / f"{symbol}_{chart}.parquet"
    if not path.exists():
        return None
    try:
        frame = pd.read_parquet(path)
    except (OSError, ValueError, ImportError):
        return None
    if frame.empty or "close" not in frame.columns:
        return None
    frame.index = pd.DatetimeIndex(pd.to_datetime(frame.index, utc=True, errors="coerce"))
    frame = frame[~frame.index.isna()].sort_index()
    return frame if len(frame) > 10 else None


def default_series(name: str) -> list[tuple[str, float]]:
    """A dated macro observation series from the desk's axes. Empty is a MEASUREMENT."""
    axis, _, key = str(name).partition(":")
    doc = _read_json(AXES_DIR / f"{axis}.json")
    if not isinstance(doc, dict):
        return []
    if axis in ("fred", "ecb"):
        series = doc.get("series")
        row = series.get(key) if isinstance(series, dict) else None
        points = row.get("points") if isinstance(row, dict) else None
        return [(str(p["d"]), float(p["v"])) for p in (points or [])
                if isinstance(p, dict) and _num(p.get("v")) is not None]
    if axis == "cot":
        out = [(str(r.get("knowable_at")), _num(r.get("net_pct_oi")))
               for r in (doc.get("rows") or [])
               if isinstance(r, dict) and str(r.get("symbol") or "").upper() == key.upper()]
        return [(d, float(v)) for d, v in out if d and v is not None]
    if axis == "bis":
        out = [(str(r.get("knowable_at")), _num(r.get("carry_differential")))
               for r in (doc.get("rows") or [])
               if isinstance(r, dict) and str(r.get("symbol") or "").upper() == key.upper()]
        return [(d, float(v)) for d, v in out if d and v is not None]
    return []


_EVENT_TIME_KEYS = ("window_start_utc", "at", "published_at", "happened_at", "time", "date")


def default_events(kind: str) -> list[dict[str, Any]]:
    """Dated events from the rule-derived calendar and the macro desk's own ledger."""
    out: list[dict[str, Any]] = []
    doc = _read_json(CALENDAR)
    for row in (doc.get("events") if isinstance(doc, dict) else []) or []:
        if not isinstance(row, dict) or (kind and str(row.get("kind")) != kind):
            continue
        at = next((row[k] for k in _EVENT_TIME_KEYS if row.get(k)), None)
        out.append({**row, "at": at, "source": "forced_flow_calendar"})
    if MACRO_LEDGER.exists():
        try:
            lines = MACRO_LEDGER.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            lines = []
        for line in lines[-5000:]:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if not isinstance(row, dict):
                continue
            if kind and kind not in (str(row.get("kind") or ""), str(row.get("category") or "")):
                continue
            at = next((row[k] for k in _EVENT_TIME_KEYS if row.get(k)), None)
            out.append({**row, "at": at, "source": "macro_event_ledger"})
    return out


def default_symbols(selectors: Sequence[str]) -> list[str]:
    """Selector tokens -> executable symbols, through the atlas and the hypothesis-lane fence."""
    atlas = _mod("actor_atlas")
    if atlas is not None and hasattr(atlas, "resolve"):
        try:
            return list(atlas.resolve(list(selectors)))
        except (OSError, ValueError, KeyError):
            pass
    policy = _mod("universe_policy")
    doc = _read_json(UNIVERSE_DIR / "universe.json")
    rows = doc if isinstance(doc, dict) else {}
    picked: list[str] = []
    for raw in selectors:
        head, _, tail = str(raw).partition(":")
        head, tail = head.lower(), tail.strip().upper()
        if head == "symbol":
            picked.extend(k for k in rows if k.upper() == tail)
        elif head == "prefix":
            picked.extend(k for k in rows if k.upper().startswith(tail))
        elif head == "fx":
            picked.extend(k for k, v in rows.items()
                          if str((v or {}).get("asset_class") or "").lower().startswith("forex")
                          and tail in k.upper())
        elif head == "class":
            want = tail.lower()
            picked.extend(k for k, v in rows.items()
                          if str((v or {}).get("asset_class") or "").lower() == want)
    out = sorted(dict.fromkeys(picked))
    if policy is not None and hasattr(policy, "may_hypothesise"):
        out = [s for s in out if policy.may_hypothesise(s)]
    return out


@dataclass
class Ctx:
    """Everything a macro miner needs, built ONCE per run and injected whole in a test.

    The readers are callables rather than paths so a test plants a synthetic world without a
    single file on disk, and so a miner can never quietly reach past them to the real universe.
    """

    conn: Any = None
    mandate: Any = None
    budget_s: float = 240.0
    now: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    bars_fn: Callable[[str, str], Any] | None = None
    series_fn: Callable[[str], list[tuple[str, float]]] | None = None
    events_fn: Callable[[str], list[dict[str, Any]]] | None = None
    symbols_fn: Callable[[Sequence[str]], list[str]] | None = None
    record_fn: Callable[..., tuple[str, bool]] | None = None
    miner: str = ""
    started: float = field(default_factory=time.monotonic)
    notes: list[dict[str, Any]] = field(default_factory=list)
    unmeasured_rows: list[dict[str, Any]] = field(default_factory=list)
    recorded: list[str] = field(default_factory=list)
    max_rows: int = MAX_ROWS

    # -- the readers -------------------------------------------------------------------------
    def bars(self, symbol: str, chart: str = "H1") -> Any:
        return (self.bars_fn or default_bars)(symbol, chart)

    def series(self, name: str) -> list[tuple[str, float]]:
        return list((self.series_fn or default_series)(name) or [])

    def events(self, kind: str) -> list[dict[str, Any]]:
        return list((self.events_fn or default_events)(kind) or [])

    def symbols(self, selectors: Sequence[str]) -> list[str]:
        return list((self.symbols_fn or default_symbols)(selectors) or [])

    # -- the ledger --------------------------------------------------------------------------
    def enter(self, miner: str) -> Ctx:
        self.miner = miner
        self.started = time.monotonic()
        return self

    def over(self) -> bool:
        return (time.monotonic() - self.started) >= float(self.budget_s)

    def note(self, what: str, why: str) -> None:
        self.notes.append({"miner": self.miner, "what": what, "why": why})

    def unmeasured(self, what: str, why: str) -> None:
        """UNMEASURED BY NAME. An absence recorded here is a verdict, never a silent zero."""
        self.unmeasured_rows.append({"miner": self.miner, "what": what, "why": why})

    def record_discovery(self, **fields: Any) -> tuple[str, bool]:
        """One discovery, stamped `macro:<miner>` with `payload.region = "macro"`. Always."""
        miner = str(fields.pop("miner", "") or self.miner or "unknown")
        payload = dict(fields.pop("payload", None) or {})
        payload["region"] = REGION
        payload.setdefault("miner", miner)
        payload.setdefault("tag", f"{TAG}{miner}")
        fields.setdefault("origin", "EXTERNAL")
        fields.setdefault("source_type", "macro_measurement")
        fields.setdefault("source_id", f"{TAG}{miner}")
        if self.record_fn is not None:
            got = self.record_fn(generator=f"{TAG}{miner}", payload=payload, **fields)
        else:
            reg = _registry()
            if reg is None or self.conn is None:
                self.note("record_discovery", "no registry connection: the row is measured and "
                                              "reported but not persisted")
                return "", False
            got = reg.record_discovery(generator=f"{TAG}{miner}", payload=payload,
                                       conn=self.conn, **fields)
        did = str(got[0]) if isinstance(got, tuple) else str(got)
        if did:
            self.recorded.append(did)
        return did, bool(got[1]) if isinstance(got, tuple) else True


def make_ctx(conn: Any = None, mandate: Any = None, budget_s: float = 240.0,
             **readers: Any) -> Ctx:
    """The one door. Readers default to the desk's own artifacts; a test injects its own."""
    if mandate is None:
        m = _mandate()
        mandate = getattr(m, "MANDATE", None) if m is not None else None
    return Ctx(conn=conn, mandate=mandate, budget_s=float(budget_s), **readers)


def _result(ctx: Ctx, name: str, rows: list[dict[str, Any]], *, ok: bool = True,
            extra: dict[str, Any] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {
        "miner": name, "generator": f"{TAG}{name}", "region": REGION, "ok": ok,
        "seconds": round(time.monotonic() - ctx.started, 3), "budget_s": ctx.budget_s,
        "n_rows": len(rows), "rows": rows[: ctx.max_rows],
        "discoveries": list(ctx.recorded),
        "unmeasured": [u for u in ctx.unmeasured_rows if u["miner"] == name],
        "notes": [n for n in ctx.notes if n["miner"] == name],
        "controls": "matched non-event days at the same hour, plus the five-era split",
        "null": PERMUTATION,
    }
    out.update(extra or {})
    return out


# =============================================================================================
# 1. the central-bank surprise engine
# =============================================================================================
def _bank_table(ctx: Ctx) -> tuple[tuple[str, str, str, str], ...]:
    m = _mandate()
    got = getattr(m, "G10_BANKS", None) if m is not None else None
    return tuple(got) if got else (("Fed", "Federal Reserve / FOMC", "USD", "en"),)


def _subbeats(ctx: Ctx) -> tuple[str, ...]:
    m = _mandate()
    return tuple(getattr(m, "CB_SUBBEATS", ()) or ("decision",))


#: What each bank is actually CALLED in the records this box can reach. Measured 2026-09-17: the
#: forced-flow calendar names the Fed's meetings `fomc_<date>`, so matching on the bank's own code
#: found zero Fed decisions and reported the whole lane UNMEASURED -- a silent narrowing that
#: looked exactly like an absent calendar. Aliases are data, and a record naming a bank by a
#: spelling not listed here is UNATTRIBUTED and counted, never guessed at.
BANK_ALIASES: dict[str, tuple[str, ...]] = {
    "Fed": ("fed", "fomc", "federal reserve", "federal open market"),
    "ECB": ("ecb", "european central bank", "governing council"),
    "BoE": ("boe", "bank of england", "mpc"),
    "SNB": ("snb", "swiss national bank", "nationalbank"),
    "RBA": ("rba", "reserve bank of australia"),
    "RBNZ": ("rbnz", "reserve bank of new zealand"),
    "BoC": ("boc", "bank of canada", "banque du canada"),
    "Riksbank": ("riksbank", "riksbanken", "sveriges"),
    "Norges": ("norges", "norges bank"),
}


def matches_bank(code: str, key: str) -> bool:
    """Does this record name this bank? Its code, or any spelling the record actually uses."""
    text = str(key or "").lower()
    return any(alias in text for alias in (code.lower(), *BANK_ALIASES.get(code, ())))


def _bank_of(event: Mapping[str, Any]) -> str:
    for key in ("bank", "central_bank", "actor", "name"):
        value = str(event.get(key) or "")
        if value:
            return value
    return ""


def _language_change(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Statement-to-statement language change, when the text was archived. Usually it was not."""
    texts = [str(r.get("statement") or r.get("text") or "") for r in rows]
    have = [t for t in texts if t.strip()]
    if len(have) < 2:
        return {"status": UNMEASURED,
                "why": "fewer than two archived statements; language change cannot be measured"}
    changes = []
    for prev, cur in itertools.pairwise(have):
        a, b = set(prev.lower().split()), set(cur.lower().split())
        union = a | b
        changes.append(0.0 if not union else 1.0 - len(a & b) / len(union))
    return {"status": "MEASURED", "n": len(changes), "mean_jaccard_change": float(
        np.mean(changes)), "method": "1 - Jaccard overlap of consecutive statement vocabularies"}


def mine_central_bank(ctx: Ctx) -> dict[str, Any]:
    """Per bank, per sub-beat: what the decision's SURPRISE did, against a matched control."""
    ctx.enter("central_bank")
    events = ctx.events("central_bank")
    rows: list[dict[str, Any]] = []
    if not events:
        ctx.unmeasured("central_bank:events",
                       "no central_bank events: the calendar's meeting table is a TABLE, and a "
                       "year absent from it produces no events rather than a silent zero")
        return _result(ctx, "central_bank", rows)
    by_bank: dict[str, list[dict[str, Any]]] = {}
    for ev in events:
        by_bank.setdefault(_bank_of(ev) or "UNATTRIBUTED", []).append(dict(ev))
    horizons = (("1h", 1), ("4h", 4), ("1d", 24))
    for code, long_name, ccy, _lang in _bank_table(ctx):
        bank_rows = [e for k, v in by_bank.items() if matches_bank(code, k) for e in v]
        if not bank_rows:
            ctx.unmeasured(f"central_bank:{code}", "no dated decision for this bank in the "
                                                   "events the box can reach")
            continue
        symbols = ctx.symbols((f"fx:{ccy}", "prefix:XAU"))
        if not symbols:
            ctx.unmeasured(f"central_bank:{code}:instruments",
                           f"no executable instrument carries the {ccy} leg on this box")
            continue
        language = _language_change(bank_rows)
        for subbeat in _subbeats(ctx):
            beat_rows = [e for e in bank_rows
                         if str(e.get("subbeat") or e.get("beat") or "decision") == subbeat]
            if not beat_rows:
                ctx.unmeasured(f"central_bank:{code}:{subbeat}",
                               "the sub-beat is not separately dated in the reachable record")
                continue
            for symbol in symbols[:4]:
                frame = ctx.bars(symbol, "H1")
                if frame is None or len(frame) < MIN_OBS:
                    ctx.unmeasured(f"central_bank:{code}:{symbol}", "no H1 bars on this box")
                    continue
                for hname, hbars in horizons:
                    got = surprise_engine(frame, beat_rows, horizon_bars=hbars,
                                          label=f"{code}:{subbeat}:{symbol}:{hname}")
                    got.update({"bank": code, "bank_name": long_name, "currency": ccy,
                                "subbeat": subbeat, "symbol": symbol, "horizon": hname,
                                "language_change": language})
                    rows.append(got)
                    for row in got.get("unmeasured", ()):
                        ctx.unmeasured(row["what"], row["why"])
                    if got.get("separates") and not got.get("below_floor"):
                        ctx.record_discovery(
                            mechanism="policy_surprise",
                            actor=f"{long_name} ({code})",
                            information="event",
                            economic_rationale=(
                                f"a {code} {subbeat} that differs from what was expected repriced "
                                f"{symbol} over {hname}; the reaction loads on the SURPRISE and "
                                "not on the level of the decision (t_surprise="
                                f"{got['joint']['t_surprise']:.2f} vs t_actual="
                                f"{got['joint']['t_actual']:.2f}) against a matched non-event "
                                "control leg"),
                            assets=[symbol], horizons=[hname], sessions=["all"],
                            regimes=got["eras_present"],
                            required_data=["cb_publications", "bis_cbpol", "desk_universe_bars"],
                            pit_requirements=["decision timestamp to the minute",
                                              "consensus captured BEFORE the decision"],
                            novelty=0.5, confidence=min(0.9, 0.4 + 0.1 * len(got["by_era"])),
                            falsifier=("the surprise coefficient loses significance, or the "
                                       "carrier flips to the level, in the next era"),
                            payload={"row": {k: got[k] for k in
                                             ("n", "joint", "by_era", "p_permutation",
                                              "mean_raw", "mean_adjusted", "basis")},
                                     "bank": code, "subbeat": subbeat})
                if ctx.over():
                    ctx.note("budget", "time box reached; the remaining banks resume next pass")
                    return _result(ctx, "central_bank", rows)
    return _result(ctx, "central_bank", rows,
                   extra={"banks": [b[0] for b in _bank_table(ctx)],
                          "subbeats": list(_subbeats(ctx))})


# =============================================================================================
# 2. the macro release engine
# =============================================================================================
def _positioning_state(ctx: Ctx, symbol: str, when: datetime) -> str:
    """The COT state KNOWABLE at `when` -- the 4-day lag is already in the axis's stamps."""
    points = ctx.series(f"cot:{symbol}")
    if not points:
        return UNMEASURED
    day = when.strftime("%Y-%m-%d")
    history = [v for d, v in points if d <= day]
    if len(history) < 20:
        return UNMEASURED
    value = history[-1]
    lo, hi = float(np.quantile(history, 0.2)), float(np.quantile(history, 0.8))
    return "short_extreme" if value <= lo else "long_extreme" if value >= hi else "neutral"


def mine_release(ctx: Ctx) -> dict[str, Any]:
    """CPI, payrolls, GDP, PMI, retail, claims: the surprise, the revision, the conditioners."""
    ctx.enter("release")
    events = ctx.events("macro_release")
    rows: list[dict[str, Any]] = []
    if not events:
        ctx.unmeasured("release:events",
                       "no macro_release events reachable: the desk's vintages carry forecast "
                       "and previous, and no dated actual, so the release lane is UNMEASURED")
        return _result(ctx, "release", rows)
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for ev in events:
        family = str(ev.get("family") or ev.get("release") or ev.get("name") or "unknown")
        economy = str(ev.get("economy") or ev.get("country") or "unknown")
        grouped.setdefault((economy, family), []).append(dict(ev))
    for (economy, family), group in sorted(grouped.items()):
        selectors = tuple(dict.fromkeys(
            sel for ev in group for sel in (ev.get("selectors") or ())
        )) or ("prefix:XAU",)
        symbols = ctx.symbols(selectors)
        if not symbols:
            ctx.unmeasured(f"release:{economy}:{family}:instruments",
                           "no executable instrument resolved from the release's selectors")
            continue
        for symbol in symbols[:3]:
            frame = ctx.bars(symbol, "H1")
            if frame is None or len(frame) < MIN_OBS:
                ctx.unmeasured(f"release:{symbol}", "no H1 bars on this box")
                continue
            for hname, hbars in (("1h", 1), ("1d", 24)):
                got = surprise_engine(frame, group, horizon_bars=hbars,
                                      label=f"{economy}:{family}:{symbol}:{hname}")
                revisions = [_num(e.get("revision")) for e in group]
                revisions = [r for r in revisions if r is not None]
                got["revision"] = ({"n": len(revisions), "mean": float(np.mean(revisions))}
                                   if revisions else
                                   {"status": UNMEASURED,
                                    "why": "no revision field on the reachable release rows"})
                stamps = [_as_utc(e.get("at")) for e in group]
                states = [_positioning_state(ctx, symbol, s) for s in stamps if s is not None]
                got["positioning_conditioner"] = {
                    "states": {s: states.count(s) for s in set(states)},
                    "status": UNMEASURED if all(s == UNMEASURED for s in states) else "MEASURED",
                }
                got.update({"economy": economy, "family": family, "symbol": symbol,
                            "horizon": hname})
                rows.append(got)
                for row in got.get("unmeasured", ()):
                    ctx.unmeasured(row["what"], row["why"])
                if got.get("separates") and not got.get("below_floor"):
                    ctx.record_discovery(
                        mechanism="macro_surprise",
                        actor="commercial hedgers and speculators (COT categories)",
                        information="event",
                        economic_rationale=(
                            f"a {economy} {family} surprise repriced {symbol} over {hname}; the "
                            "reaction loads on the deviation from expectation rather than on the "
                            "level, measured against matched non-release days"),
                        assets=[symbol], horizons=[hname], sessions=["all"],
                        regimes=got["eras_present"],
                        required_data=["bls_bea", "eurostat", "ons", "desk_universe_bars"],
                        pit_requirements=["release time to the minute",
                                          "consensus captured before the print",
                                          "vintages through ALFRED for any revised series"],
                        novelty=0.5, confidence=0.5,
                        falsifier="the surprise coefficient does not survive the next era",
                        payload={"row": {k: got[k] for k in ("n", "joint", "by_era",
                                                             "p_permutation", "basis")},
                                 "economy": economy, "family": family})
            if ctx.over():
                ctx.note("budget", "time box reached; the remaining releases resume next pass")
                return _result(ctx, "release", rows)
    return _result(ctx, "release", rows, extra={"n_groups": len(grouped)})


# =============================================================================================
# 3. positioning
# =============================================================================================
def mine_positioning(ctx: Ctx) -> dict[str, Any]:
    """COT extremes, changes and crowding, against the same symbol's neutral weeks."""
    ctx.enter("positioning")
    rows: list[dict[str, Any]] = []
    symbols = ctx.symbols(("class:Forex", "prefix:XAU", "prefix:XAG", "class:Energy"))
    if not symbols:
        ctx.unmeasured("positioning:instruments", "no executable instrument resolved")
        return _result(ctx, "positioning", rows)
    for symbol in symbols:
        points = ctx.series(f"cot:{symbol}")
        if len(points) < 40:
            ctx.unmeasured(f"positioning:{symbol}",
                           f"{len(points)} COT observations: the symbol is outside the CFTC map "
                           "or below the 40-week floor")
            continue
        frame = ctx.bars(symbol, "H1")
        if frame is None or len(frame) < MIN_OBS:
            ctx.unmeasured(f"positioning:{symbol}:bars", "no H1 bars on this box")
            continue
        dates = [d for d, _ in points]
        values = np.asarray([v for _, v in points], dtype=float)
        changes = np.diff(values, prepend=values[0])
        lo, hi = float(np.quantile(values, 0.2)), float(np.quantile(values, 0.8))
        states = np.asarray(["short_extreme" if v <= lo else "long_extreme" if v >= hi
                             else "neutral" for v in values])
        crowding = np.asarray([s != "neutral" and abs(c) > float(np.quantile(np.abs(changes),
                                                                             0.8))
                               for s, c in zip(states, changes, strict=False)])
        forward: list[float] = []
        keep: list[int] = []
        for i, day in enumerate(dates):
            stamp = _as_utc(day)
            if stamp is None:
                continue
            r = response(frame, stamp, 24 * 5)
            if r is None:
                continue
            forward.append(r)
            keep.append(i)
        if len(forward) < MIN_EVENTS:
            ctx.unmeasured(f"positioning:{symbol}:forward",
                           f"only {len(forward)} COT weeks land on bars this box holds")
            continue
        y = np.asarray(forward)
        lab = states[keep]
        neutral = y[lab == "neutral"]
        row: dict[str, Any] = {"symbol": symbol, "n": int(y.size),
                               "knowable_lag_days": 4,
                               "control": "the same symbol's neutral-positioning weeks",
                               "null": PERMUTATION, "by_state": {}, "by_era": {}}
        gen = _rng("positioning", symbol)
        for state in ("short_extreme", "long_extreme", "neutral"):
            mask = lab == state
            if int(mask.sum()) < 4:
                row["by_state"][state] = {"n": int(mask.sum()), "below_floor": True}
                continue

            def _diff(values_: np.ndarray, labels_: np.ndarray, want: str = state) -> float:
                sel = np.asarray(labels_) == want
                rest = ~sel
                if sel.sum() < 2 or rest.sum() < 2:
                    return float("nan")
                return float(values_[sel].mean() - values_[rest].mean())

            stat = _diff(y, lab)
            row["by_state"][state] = {
                "n": int(mask.sum()), "mean_forward_5d": float(y[mask].mean()),
                "vs_neutral": (None if neutral.size < 2
                               else float(y[mask].mean() - neutral.mean())),
                "p_permutation": permutation_p(stat, y, lab, _diff, gen),
                "bootstrap": block_bootstrap_ci(y[mask], gen),
                "below_floor": bool(int(mask.sum()) < MIN_EVENTS),
            }
        eras = np.asarray([era_of(dates[i]) for i in keep])
        for name in sorted(set(eras)):
            mask = eras == name
            row["by_era"][name] = {"n": int(mask.sum()),
                                   "mean_forward_5d": float(y[mask].mean()),
                                   "below_floor": bool(int(mask.sum()) < MIN_ERA_EVENTS)}
        row["crowding_weeks"] = int(np.asarray(crowding)[keep].sum())
        rows.append(row)
        best = max((v for v in row["by_state"].values() if v.get("p_permutation") is not None),
                   key=lambda v: abs(v.get("vs_neutral") or 0.0), default=None)
        if best is not None and (best.get("p_permutation") or 1.0) <= ALPHA \
                and not best.get("below_floor"):
            ctx.record_discovery(
                mechanism="positioning_crowding",
                actor="commercial hedgers and speculators (COT categories)",
                information="positioning",
                economic_rationale=(
                    f"an extreme speculative position in {symbol} precedes a different five-day "
                    "forward distribution than the same symbol's neutral weeks; a crowded book "
                    "is forced out by margin rather than by opinion"),
                assets=[symbol], horizons=["5d"], sessions=["all"],
                regimes=sorted(row["by_era"]),
                required_data=["cftc_cot", "desk_universe_bars"],
                pit_requirements=["the COT knowable_at, never the as_of (a 4-day lag)"],
                novelty=0.45, confidence=0.5,
                falsifier="the extreme-vs-neutral difference does not survive the next era",
                payload={"row": row})
        if ctx.over():
            ctx.note("budget", "time box reached; the remaining symbols resume next pass")
            break
    return _result(ctx, "positioning", rows)


# =============================================================================================
# 4/5. rates and the curve
# =============================================================================================
def _aligned(points: Sequence[tuple[str, float]], frame: pd.DataFrame
             ) -> tuple[np.ndarray, np.ndarray, list[str]] | None:
    """Daily factor changes aligned to the next day's instrument return. No lookahead."""
    if not points or frame is None or frame.empty:
        return None
    closes = frame["close"].resample("1D").last().dropna()
    if len(closes) < 30:
        return None
    logc = np.log(closes.to_numpy(dtype=float))
    ret = pd.Series(np.concatenate(([np.nan], np.diff(logc))), index=closes.index)
    series = pd.Series({pd.Timestamp(d, tz=UTC): v for d, v in points}).sort_index()
    dfac = series.diff()
    joined = pd.concat([dfac.rename("f"), ret.rename("r")], axis=1).dropna()
    if len(joined) < 30:
        return None
    return (joined["f"].to_numpy(dtype=float), joined["r"].to_numpy(dtype=float),
            [str(i.date()) for i in joined.index])


def mine_rates(ctx: Ctx) -> dict[str, Any]:
    """The transmission beta of each instrument on each rate factor, charged BH across the set."""
    ctx.enter("rates")
    rows: list[dict[str, Any]] = []
    have: list[tuple[str, str, list[tuple[str, float]]]] = []
    for key, what in RATE_FACTORS:
        points = ctx.series(key)
        if len(points) < 60:
            ctx.unmeasured(f"rates:{key}",
                           f"{len(points)} observations for {what}: the FRED axis on this box "
                           "reported 0 series and 7 failures on 2026-09-12")
            continue
        have.append((key, what, points))
    if not have:
        return _result(ctx, "rates", rows, extra={"factors_wanted": [k for k, _ in RATE_FACTORS]})
    symbols = ctx.symbols(("class:Forex", "prefix:XAU", "class:Indices", "class:Energy"))
    if not symbols:
        ctx.unmeasured("rates:instruments", "no executable instrument resolved")
        return _result(ctx, "rates", rows)
    pending: list[dict[str, Any]] = []
    for symbol in symbols:
        frame = ctx.bars(symbol, "H1")
        if frame is None or len(frame) < MIN_OBS:
            ctx.unmeasured(f"rates:{symbol}", "no H1 bars on this box")
            continue
        for key, what, points in have:
            got = _aligned(points, frame)
            if got is None:
                ctx.unmeasured(f"rates:{symbol}:{key}",
                               "fewer than 30 overlapping days between the factor and the bars")
                continue
            fac, ret, days = got
            fit = ols(ret, _z(fac))
            gen = _rng("rates", symbol, key)

            def _slope(y: np.ndarray, labels: np.ndarray) -> float:
                return float((ols(y, _z(np.asarray(labels, dtype=float)))["t"]
                              or [float("nan")])[0])

            t = (fit["t"] or [None])[0]
            placebo = ols(ret, _z(gen.permutation(fac)))
            by_era: dict[str, Any] = {}
            eras = np.asarray([era_of(d) for d in days])
            for name in sorted(set(eras)):
                mask = eras == name
                sub = ols(ret[mask], _z(fac[mask])) if int(mask.sum()) > 10 else {"beta": []}
                by_era[name] = {"n": int(mask.sum()), "beta": (sub["beta"] or [None])[0],
                                "below_floor": bool(int(mask.sum()) < 30)}
            pending.append({
                "symbol": symbol, "factor": key, "what": what, "n": fit["n"],
                "beta": (fit["beta"] or [None])[0], "t": t, "r2": fit.get("r2"),
                "placebo_t": (placebo["t"] or [None])[0],
                "p_permutation": permutation_p(float(t) if t is not None else float("nan"),
                                               ret, fac, _slope, gen, 200),
                "by_era": by_era, "control": "shuffled-date factor as a placebo regressor",
                "null": PERMUTATION,
            })
        if ctx.over():
            ctx.note("budget", "time box reached; the remaining symbols resume next pass")
            break
    keep = bh_fdr([r["p_permutation"] for r in pending])
    for row, survived in zip(pending, keep, strict=False):
        row["bh_survives"] = bool(survived)
        rows.append(row)
        if survived and row["n"] >= MIN_OBS:
            ctx.record_discovery(
                mechanism="rates_transmission",
                actor="banks and dealers", information="macro",
                economic_rationale=(
                    f"a daily move in {row['what']} transmits into {row['symbol']} the next day "
                    f"(beta={row['beta']}, t={row['t']}); the placebo regressor on shuffled "
                    "dates does not, and the edge survives BH across every instrument x factor "
                    "pair tested this pass"),
                assets=[row["symbol"]], horizons=["1d"], sessions=["all"],
                regimes=sorted(row["by_era"]),
                required_data=["fred", "ecb_sdw", "bis_cbpol", "desk_universe_bars"],
                pit_requirements=["the factor's own publication stamp, not its reference date"],
                novelty=0.4, confidence=0.5,
                falsifier="the beta changes sign in the next era, or the placebo matches it",
                payload={"row": row})
    return _result(ctx, "rates", rows,
                   extra={"factors_used": [k for k, _, _ in have], "bh_q": ALPHA,
                          "n_tested": len(pending)})


def mine_curve(ctx: Ctx) -> dict[str, Any]:
    """Slope, curvature and the real rate as STATES, with the forward distribution inside each."""
    ctx.enter("curve")
    rows: list[dict[str, Any]] = []
    legs = {key.split(":")[-1]: ctx.series(key) for key, _ in RATE_FACTORS}
    two, five, ten = legs.get("DGS2", []), legs.get("DGS5", []), legs.get("DGS10", [])
    if len(two) < 60 or len(ten) < 60:
        ctx.unmeasured("curve:legs",
                       "the 2y and 10y legs are not both present on this box, so slope and "
                       "curvature cannot be constructed -- UNMEASURED, not flat")
        return _result(ctx, "curve", rows)
    frames = {"slope": {}, "curvature": {}}
    s2 = dict(two)
    s5 = dict(five)
    s10 = dict(ten)
    days = sorted(set(s2) & set(s10))
    slope = [(d, s10[d] - s2[d]) for d in days]
    curvature = [(d, 2 * s5[d] - s2[d] - s10[d]) for d in days if d in s5]
    del frames
    symbols = ctx.symbols(("prefix:XAU", "class:Indices", "class:Forex"))
    if not symbols:
        ctx.unmeasured("curve:instruments", "no executable instrument resolved")
        return _result(ctx, "curve", rows)
    for symbol in symbols[:8]:
        frame = ctx.bars(symbol, "H1")
        if frame is None or len(frame) < MIN_OBS:
            ctx.unmeasured(f"curve:{symbol}", "no H1 bars on this box")
            continue
        for name, points in (("slope", slope), ("curvature", curvature)):
            if len(points) < 60:
                ctx.unmeasured(f"curve:{name}", "fewer than 60 dated observations")
                continue
            got = _aligned(points, frame)
            if got is None:
                ctx.unmeasured(f"curve:{symbol}:{name}", "fewer than 30 overlapping days")
                continue
            change, ret, dates = got
            gen = _rng("curve", symbol, name)
            lab = np.where(change > 0, f"{name}_up", f"{name}_down")

            def _diff(values_: np.ndarray, labels_: np.ndarray, want: str = f"{name}_up"
                      ) -> float:
                sel = np.asarray(labels_) == want
                if sel.sum() < 2 or (~sel).sum() < 2:
                    return float("nan")
                return float(values_[sel].mean() - values_[~sel].mean())

            stat = _diff(ret, lab)
            by_era = {}
            eras = np.asarray([era_of(d) for d in dates])
            for era in sorted(set(eras)):
                mask = eras == era
                by_era[era] = {"n": int(mask.sum()),
                               "mean": float(ret[mask].mean()) if mask.any() else None,
                               "below_floor": bool(int(mask.sum()) < 30)}
            rows.append({"symbol": symbol, "state": name, "n": int(ret.size),
                         "up_minus_down": float(stat) if math.isfinite(stat) else None,
                         "p_permutation": permutation_p(stat, ret, lab, _diff, gen, 200),
                         "bootstrap": block_bootstrap_ci(ret, gen),
                         "by_era": by_era, "null": PERMUTATION,
                         "control": "the same symbol's opposite-state days"})
        if ctx.over():
            break
    return _result(ctx, "curve", rows)


# =============================================================================================
# 6. fiscal / auction calendars
# =============================================================================================
def _window_stat(ctx: Ctx, frame: pd.DataFrame, events: Sequence[Mapping[str, Any]],
                 pre_bars: int, post_bars: int, label: str) -> dict[str, Any]:
    stamps = [_as_utc(e.get("at") or e.get("window_start_utc")) for e in events]
    excluded = {s.strftime("%Y-%m-%d") for s in stamps if s is not None}
    pre: list[float] = []
    post: list[float] = []
    ctrl_pre: list[float] = []
    eras: list[str] = []
    for stamp in stamps:
        if stamp is None:
            continue
        before = response(frame, stamp - timedelta(hours=pre_bars), pre_bars)
        after = response(frame, stamp, post_bars)
        c, _n = matched_control(frame, stamp, post_bars, excluded)
        if before is None or after is None or c is None:
            continue
        pre.append(before)
        post.append(after)
        ctrl_pre.append(c)
        eras.append(era_of(stamp))
    n = len(post)
    if n == 0:
        return {"label": label, "n": 0, "verdict": UNMEASURED,
                "why": "no event landed on a bar with a matched control"}
    adj = np.asarray(post) - np.asarray(ctrl_pre)
    t_adj, _ = one_sample_t(adj)
    gen = _rng("window", label)
    by_era = {e: {"n": int(sum(1 for x in eras if x == e))} for e in sorted(set(eras))}
    return {"label": label, "n": n, "mean_pre": float(np.mean(pre)),
            "mean_post_raw": float(np.mean(post)), "mean_control": float(np.mean(ctrl_pre)),
            "mean_post_adjusted": float(np.mean(adj)), "t_adjusted": t_adj,
            "bootstrap": block_bootstrap_ci(adj, gen), "by_era": by_era,
            "below_floor": bool(n < MIN_EVENTS), "null": BOOTSTRAP,
            "control": "matched non-event days at the same hour",
            "verdict": "UNDERPOWERED" if n < MIN_EVENTS else "MEASURED"}


def mine_fiscal_auction(ctx: Ctx) -> dict[str, Any]:
    """Pre-auction concession and post-auction reversal, against matched non-auction days."""
    ctx.enter("fiscal_auction")
    events = ctx.events("bond_auction")
    rows: list[dict[str, Any]] = []
    if not events:
        ctx.unmeasured("fiscal_auction:events",
                       "no bond_auction rows: the desk's auction dates are a PATTERN labelled "
                       "VERIFY_SCHEDULE and a year absent from it produces none")
        return _result(ctx, "fiscal_auction", rows)
    symbols = ctx.symbols(("class:Bonds", "fx:USD"))
    if not symbols:
        ctx.unmeasured("fiscal_auction:instruments", "no bond or USD instrument resolved")
        return _result(ctx, "fiscal_auction", rows)
    for symbol in symbols[:8]:
        frame = ctx.bars(symbol, "H1")
        if frame is None or len(frame) < MIN_OBS:
            ctx.unmeasured(f"fiscal_auction:{symbol}", "no H1 bars on this box")
            continue
        named = [e for e in events if symbol in (e.get("instruments") or [symbol])]
        if not named:
            continue
        got = _window_stat(ctx, frame, named, 24 * 3, 24 * 3, f"auction:{symbol}")
        got["symbol"] = symbol
        rows.append(got)
        if ctx.over():
            break
    return _result(ctx, "fiscal_auction", rows, extra={"n_events": len(events)})


# =============================================================================================
# 7. intervention states
# =============================================================================================
def mine_intervention(ctx: Ctx) -> dict[str, Any]:
    """Inside a DECLARED state, is the pair's conditional distribution asymmetric or truncated?"""
    ctx.enter("intervention")
    events = ctx.events("intervention")
    rows: list[dict[str, Any]] = []
    if not events:
        ctx.unmeasured("intervention:events",
                       "no declared intervention windows reachable: MoF discloses daily detail "
                       "quarterly and some interventions are never disclosed")
        return _result(ctx, "intervention", rows)
    for ev in events[:20]:
        symbols = ctx.symbols(tuple(ev.get("selectors") or ()) or ("fx:JPY",))
        start, end = _as_utc(ev.get("at") or ev.get("start")), _as_utc(ev.get("end"))
        if start is None:
            ctx.unmeasured("intervention:stamp", "an intervention row carries no usable stamp")
            continue
        for symbol in symbols[:3]:
            frame = ctx.bars(symbol, "H1")
            if frame is None or len(frame) < MIN_OBS:
                ctx.unmeasured(f"intervention:{symbol}", "no H1 bars on this box")
                continue
            close = frame["close"].to_numpy(dtype=float)
            logr = np.concatenate(([np.nan], np.diff(np.log(np.clip(close, 1e-12, None)))))
            stamps = frame.index
            inside = (stamps >= pd.Timestamp(start)) & (
                stamps <= pd.Timestamp(end if end is not None else start + timedelta(days=30)))
            out = ~inside
            a, b = logr[inside], logr[out]
            a, b = a[np.isfinite(a)], b[np.isfinite(b)]
            if a.size < 30 or b.size < 30:
                ctx.unmeasured(f"intervention:{symbol}:{ev.get('name')}",
                               f"inside n={a.size}, outside n={b.size}: below the 30-bar floor")
                continue
            gen = _rng("intervention", symbol, str(ev.get("name")))
            skew_in = float(np.mean(_z(a) ** 3)) if a.size > 2 else None
            skew_out = float(np.mean(_z(b) ** 3)) if b.size > 2 else None
            rows.append({
                "symbol": symbol, "state": str(ev.get("name") or ev.get("kind") or "declared"),
                "n_inside": int(a.size), "n_outside": int(b.size),
                "skew_inside": skew_in, "skew_outside": skew_out,
                "vol_inside": float(np.std(a, ddof=1)), "vol_outside": float(np.std(b, ddof=1)),
                "downside_q05_inside": float(np.quantile(a, 0.05)),
                "downside_q05_outside": float(np.quantile(b, 0.05)),
                "bootstrap_inside": block_bootstrap_ci(a, gen),
                "control": "the same pair outside the declared state",
                "null": BOOTSTRAP,
            })
        if ctx.over():
            break
    return _result(ctx, "intervention", rows)


# =============================================================================================
# 8. cross-asset propagation
# =============================================================================================
def mine_propagation(ctx: Ctx) -> dict[str, Any]:
    """The chain USD -> rates -> vol -> equities -> gold -> carry -> commodities -> credit."""
    ctx.enter("propagation")
    rows: list[dict[str, Any]] = []
    node_returns: dict[str, pd.Series] = {}
    for node, selectors in PROPAGATION_CHAIN:
        symbols = ctx.symbols(selectors) if selectors else []
        picked = None
        for symbol in symbols:
            frame = ctx.bars(symbol, "H1")
            if frame is None or len(frame) < MIN_OBS:
                continue
            closes = frame["close"].resample("1D").last().dropna()
            if len(closes) < 60:
                continue
            picked = (symbol, pd.Series(np.concatenate(
                ([np.nan], np.diff(np.log(closes.to_numpy(dtype=float))))), index=closes.index))
            break
        if picked is None:
            ctx.unmeasured(f"propagation:{node}",
                           "no executable instrument with 60 daily bars represents this node on "
                           "this box" if selectors else
                           "the node has no executable instrument at all (credit has no CFD)")
            continue
        node_returns[node] = picked[1].rename(node)
        rows.append({"node": node, "proxy": picked[0], "n": int(picked[1].notna().sum())})
    if len(node_returns) < 2:
        return _result(ctx, "propagation", rows, extra={"edges": [], "nodes": list(node_returns)})
    panel = pd.concat(node_returns.values(), axis=1).dropna()
    if len(panel) < 60:
        ctx.unmeasured("propagation:panel",
                       f"the aligned panel is {len(panel)} days, below the 60-day floor")
        return _result(ctx, "propagation", rows, extra={"edges": [], "nodes": list(panel.columns)})
    order = [n for n, _ in PROPAGATION_CHAIN if n in panel.columns]
    edges: list[dict[str, Any]] = []
    pending_p: list[float] = []
    for src, dst in itertools.pairwise(order):
        x_all = panel[src].to_numpy(dtype=float)
        y_all = panel[dst].to_numpy(dtype=float)
        others = [c for c in panel.columns if c not in (src, dst)]
        for lag in (1, 2, 3):
            x = x_all[:-lag]
            y = y_all[lag:]
            controls = [panel[c].to_numpy(dtype=float)[:-lag] for c in others]
            design = np.column_stack([_z(x), *[_z(c) for c in controls]]) if controls \
                else _z(x)[:, None]
            fit = ols(y, design)
            t = (fit["t"] or [None])[0]
            gen = _rng("propagation", src, dst, lag)

            def _slope(vals: np.ndarray, labels: np.ndarray) -> float:
                return float((ols(vals, _z(np.asarray(labels, dtype=float)))["t"]
                              or [float("nan")])[0])

            p = permutation_p(float(t) if t is not None else float("nan"), y, x, _slope, gen, 200)
            reverse = ols(x_all[lag:], _z(y_all[:-lag]))
            edges.append({"from": src, "to": dst, "lag_days": lag, "n": fit["n"],
                          "beta": (fit["beta"] or [None])[0], "t": t,
                          "partialled_out": others,
                          "placebo_reverse_t": (reverse["t"] or [None])[0],
                          "p_permutation": p, "null": PERMUTATION,
                          "control": "every other node's contemporaneous return partialled out, "
                                     "plus the lag-reversed placebo edge"})
            pending_p.append(p if p is not None else 1.0)
    keep = bh_fdr(pending_p)
    for edge, survived in zip(edges, keep, strict=False):
        edge["bh_survives"] = bool(survived)
        if survived:
            ctx.record_discovery(
                mechanism="cross_market_lead", actor="banks and dealers",
                information="cross_asset",
                economic_rationale=(
                    f"{edge['from']} leads {edge['to']} by {edge['lag_days']} day(s) with every "
                    "other node in the chain partialled out; the lag-reversed placebo does not "
                    "carry it and the edge survives BH across the whole chain"),
                assets=[str(r["proxy"]) for r in rows if r["node"] == edge["to"]],
                horizons=[f"{edge['lag_days']}d"], sessions=["all"], regimes=[],
                required_data=["desk_universe_bars"],
                pit_requirements=["daily closes only; no intraday lookahead across venues"],
                novelty=0.5, confidence=0.45,
                falsifier="the edge does not survive BH in the next pass, or the reverse edge "
                          "matches it",
                payload={"edge": edge})
    return _result(ctx, "propagation", rows,
                   extra={"edges": edges, "nodes": list(panel.columns), "panel_days": len(panel),
                          "chain": [n for n, _ in PROPAGATION_CHAIN]})


# =============================================================================================
# 9. fixing flows
# =============================================================================================
def _fixings(ctx: Ctx) -> tuple[tuple[str, str, str, str], ...]:
    m = _mandate()
    got = getattr(m, "FIXINGS", None) if m is not None else None
    return tuple(got) if got else (("wmr_london_1600", "WMR 4pm London", "Europe/London",
                                    "16:00"),)


def _hour_mask(frame: pd.DataFrame, hour: int) -> np.ndarray:
    return np.asarray(frame.index.hour == hour)


def mine_fixing(ctx: Ctx) -> dict[str, Any]:
    """The fix window, its month-end amplification, its reversal, against a placebo hour."""
    ctx.enter("fixing")
    rows: list[dict[str, Any]] = []
    symbols = ctx.symbols(("class:Forex", "prefix:XAU"))
    if not symbols:
        ctx.unmeasured("fixing:instruments", "no executable instrument resolved")
        return _result(ctx, "fixing", rows)
    for fix_id, what, tz, hhmm in _fixings(ctx):
        hour = int(str(hhmm).split(":")[0])
        for symbol in symbols[:10]:
            frame = ctx.bars(symbol, "H1")
            if frame is None or len(frame) < MIN_OBS:
                ctx.unmeasured(f"fixing:{symbol}", "no H1 bars on this box")
                continue
            close = frame["close"].to_numpy(dtype=float)
            logr = np.concatenate(([np.nan], np.diff(np.log(np.clip(close, 1e-12, None)))))
            window = _hour_mask(frame, hour)
            placebo = _hour_mask(frame, (hour - 1) % 24)
            reversal = _hour_mask(frame, (hour + 1) % 24)
            month_end = np.asarray(frame.index.is_month_end)
            w = logr[window & np.isfinite(logr)]
            p = logr[placebo & np.isfinite(logr)]
            if w.size < MIN_OBS or p.size < MIN_OBS:
                ctx.unmeasured(f"fixing:{symbol}:{fix_id}",
                               f"window n={w.size}, placebo n={p.size}: below the {MIN_OBS} floor")
                continue
            gen = _rng("fixing", symbol, fix_id)
            me = logr[window & month_end & np.isfinite(logr)]
            not_me = logr[window & ~month_end & np.isfinite(logr)]
            t_w, _ = one_sample_t(w)
            rows.append({
                "symbol": symbol, "fixing": fix_id, "what": what, "tz": tz, "hour_utc": hour,
                "n_window": int(w.size), "mean_window": float(w.mean()), "t_window": t_w,
                "n_placebo": int(p.size), "mean_placebo": float(p.mean()),
                "window_minus_placebo": float(w.mean() - p.mean()),
                "bootstrap_window": block_bootstrap_ci(w, gen),
                "month_end": {"n": int(me.size),
                              "mean": float(me.mean()) if me.size else None,
                              "amplification": (None if me.size < 8 or not_me.size < 8
                                                else float(me.mean() - not_me.mean())),
                              "below_floor": bool(me.size < 8)},
                "reversal_next_hour": float(np.nanmean(logr[reversal])) if reversal.any()
                else None,
                "chart_coarseness": "H1 bars: a 30-minute fix window is measured at bar "
                                    "resolution and the coarseness is on the row",
                "control": "the same instrument at the hour BEFORE the fix (placebo window)",
                "null": BOOTSTRAP,
            })
            if ctx.over():
                ctx.note("budget", "time box reached; the remaining fixings resume next pass")
                return _result(ctx, "fixing", rows)
    return _result(ctx, "fixing", rows, extra={"fixings": [f[0] for f in _fixings(ctx)]})


# =============================================================================================
# 10. commodity fundamentals
# =============================================================================================
def mine_commodity_fundamentals(ctx: Ctx) -> dict[str, Any]:
    """Inventory and report days against matched non-report days in the same season."""
    ctx.enter("commodity_fundamentals")
    rows: list[dict[str, Any]] = []
    events = [*ctx.events("inventory"), *ctx.events("usda")]
    if not events:
        ctx.unmeasured("commodity_fundamentals:events",
                       "no inventory or USDA rows reachable on this box")
        return _result(ctx, "commodity_fundamentals", rows)
    symbols = ctx.symbols(("class:Energy", "class:Soft Commodity", "prefix:XAG"))
    if not symbols:
        ctx.unmeasured("commodity_fundamentals:instruments", "no executable contract resolved")
        return _result(ctx, "commodity_fundamentals", rows)
    for symbol in symbols[:8]:
        frame = ctx.bars(symbol, "H1")
        if frame is None or len(frame) < MIN_OBS:
            ctx.unmeasured(f"commodity_fundamentals:{symbol}", "no H1 bars on this box")
            continue
        named = [e for e in events if symbol in (e.get("instruments") or [symbol])]
        if not named:
            continue
        engine = surprise_engine(frame, named, horizon_bars=4, label=f"inventory:{symbol}")
        if engine.get("n", 0) == 0:
            ctx.unmeasured(f"commodity_fundamentals:{symbol}:surprise",
                           "no expectation series is captured for these reports, so the "
                           "surprise is UNMEASURED and only the window statistic is published")
            engine = _window_stat(ctx, frame, named, 4, 4, f"inventory:{symbol}")
        engine["symbol"] = symbol
        rows.append(engine)
        if ctx.over():
            break
    return _result(ctx, "commodity_fundamentals", rows, extra={"n_events": len(events)})


# =============================================================================================
# 11. risk regimes
# =============================================================================================
def mine_risk_regime(ctx: Ctx) -> dict[str, Any]:
    """Regime labels built only from information knowable BEFORE the bar, then the split."""
    ctx.enter("risk_regime")
    rows: list[dict[str, Any]] = []
    credit = ctx.series("fred:BAMLH0A0HYM2")
    vix = ctx.series("fred:VIXCLS")
    if not credit:
        ctx.unmeasured("risk_regime:credit",
                       "no HY OAS series on this box; the credit state is derived from the "
                       "desk's own bars and the substitution is stamped on the row")
    if not vix:
        ctx.unmeasured("risk_regime:vix",
                       "no VIX series on this box; vol-of-vol is derived from realised "
                       "volatility instead and the substitution is stamped on the row")
    symbols = ctx.symbols(("class:Indices", "prefix:XAU", "class:Forex"))
    if not symbols:
        ctx.unmeasured("risk_regime:instruments", "no executable instrument resolved")
        return _result(ctx, "risk_regime", rows)
    for symbol in symbols[:10]:
        frame = ctx.bars(symbol, "H1")
        if frame is None or len(frame) < MIN_OBS * 4:
            ctx.unmeasured(f"risk_regime:{symbol}", "fewer than 240 H1 bars on this box")
            continue
        closes = frame["close"].resample("1D").last().dropna()
        if len(closes) < 120:
            ctx.unmeasured(f"risk_regime:{symbol}:daily", "fewer than 120 daily bars")
            continue
        ret = pd.Series(np.concatenate(([np.nan], np.diff(np.log(
            closes.to_numpy(dtype=float))))), index=closes.index)
        vol = ret.rolling(20, min_periods=10).std(ddof=1).shift(1)
        volvol = vol.rolling(20, min_periods=10).std(ddof=1).shift(1)
        table = pd.concat([ret.rename("r"), vol.rename("v"), volvol.rename("vv")],
                          axis=1).dropna()
        if len(table) < 90:
            ctx.unmeasured(f"risk_regime:{symbol}:panel", "fewer than 90 labelled days")
            continue
        lo, hi = table["v"].quantile(1 / 3), table["v"].quantile(2 / 3)
        label = np.where(table["v"] <= lo, "low_vol",
                         np.where(table["v"] >= hi, "high_vol", "mid_vol"))
        gen = _rng("risk_regime", symbol)
        y = table["r"].to_numpy(dtype=float)
        by_regime: dict[str, Any] = {}
        for state in ("low_vol", "mid_vol", "high_vol"):
            mask = label == state
            if int(mask.sum()) < 20:
                by_regime[state] = {"n": int(mask.sum()), "below_floor": True}
                continue
            by_regime[state] = {"n": int(mask.sum()), "mean": float(y[mask].mean()),
                                "vol": float(np.std(y[mask], ddof=1)),
                                "bootstrap": block_bootstrap_ci(y[mask], gen),
                                "below_floor": False}

        def _diff(vals: np.ndarray, labels: np.ndarray) -> float:
            sel = np.asarray(labels) == "high_vol"
            if sel.sum() < 2 or (~sel).sum() < 2:
                return float("nan")
            return float(vals[sel].mean() - vals[~sel].mean())

        rows.append({"symbol": symbol, "n": len(table), "by_regime": by_regime,
                     "high_minus_rest": _diff(y, label),
                     "p_permutation": permutation_p(_diff(y, label), y, label, _diff, gen, 200),
                     "volvol_mean": float(table["vv"].mean()),
                     "credit_state": UNMEASURED if not credit else "MEASURED",
                     "labels_knowable": "vol and vol-of-vol are shifted one day: the label uses "
                                        "only information available before the bar",
                     "control": "the unconditional distribution over the same span",
                     "null": PERMUTATION})
        if ctx.over():
            break
    return _result(ctx, "risk_regime", rows)


# =============================================================================================
# 12. calendar mismatches
# =============================================================================================
def mine_calendar_mismatch(ctx: Ctx) -> dict[str, Any]:
    """One venue shut, another open: what does that do to range, return and the reopening gap?"""
    ctx.enter("calendar_mismatch")
    rows: list[dict[str, Any]] = []
    events = ctx.events("holiday_liquidity")
    if not events:
        ctx.unmeasured("calendar_mismatch:events",
                       "no holiday_liquidity rows: the desk's holiday map covers US, UK and "
                       "Japan and other venues are UNMEASURED by name")
        return _result(ctx, "calendar_mismatch", rows)
    symbols = ctx.symbols(("class:Indices", "class:Forex"))
    if not symbols:
        ctx.unmeasured("calendar_mismatch:instruments", "no executable instrument resolved")
        return _result(ctx, "calendar_mismatch", rows)
    days = {s.strftime("%Y-%m-%d") for s in
            (_as_utc(e.get("at") or e.get("window_start_utc")) for e in events) if s is not None}
    for symbol in symbols[:10]:
        frame = ctx.bars(symbol, "H1")
        if frame is None or len(frame) < MIN_OBS:
            ctx.unmeasured(f"calendar_mismatch:{symbol}", "no H1 bars on this box")
            continue
        daily = frame["close"].resample("1D").agg(["first", "max", "min", "last"]).dropna()
        if len(daily) < 90:
            ctx.unmeasured(f"calendar_mismatch:{symbol}:daily", "fewer than 90 daily bars")
            continue
        stamps = [str(i.date()) for i in daily.index]
        mask = np.asarray([d in days for d in stamps])
        if int(mask.sum()) < 5:
            ctx.unmeasured(f"calendar_mismatch:{symbol}:overlap",
                           f"only {int(mask.sum())} holiday days land on bars this box holds")
            continue
        rng_pct = ((daily["max"] - daily["min"]) / daily["first"]).to_numpy(dtype=float)
        ret = np.log(daily["last"].to_numpy(dtype=float)
                     / daily["first"].to_numpy(dtype=float))
        gen = _rng("calendar", symbol)

        def _diff(vals: np.ndarray, labels: np.ndarray) -> float:
            sel = np.asarray(labels).astype(bool)
            if sel.sum() < 2 or (~sel).sum() < 2:
                return float("nan")
            return float(vals[sel].mean() - vals[~sel].mean())

        rows.append({
            "symbol": symbol, "n_mismatch_days": int(mask.sum()),
            "n_normal_days": int((~mask).sum()),
            "range_mismatch": float(rng_pct[mask].mean()),
            "range_normal": float(rng_pct[~mask].mean()),
            "range_difference": _diff(rng_pct, mask),
            "p_permutation_range": permutation_p(_diff(rng_pct, mask), rng_pct, mask, _diff,
                                                 gen, 200),
            "return_difference": _diff(ret, mask),
            "control": "the same symbol's days with both venues open",
            "null": PERMUTATION,
            "below_floor": bool(int(mask.sum()) < MIN_EVENTS),
        })
        if ctx.over():
            break
    return _result(ctx, "calendar_mismatch", rows, extra={"n_holiday_days": len(days)})


# =============================================================================================
# 13. the failure miner -- graveyard_resurrection's own tables, applied to this region
# =============================================================================================
_FALLBACK_GATE_CLASS: tuple[tuple[str, str], ...] = (
    ("cost", "cost_killed"), ("turnover", "cost_killed"), ("slippage", "execution_killed"),
    ("spread", "execution_killed"), ("regime", "regime_specific"),
    ("walk_forward", "unstable"), ("novelty", "redundant"), ("horizon", "wrong_horizon"),
    ("deflated", "no_edge"), ("sharpe", "no_edge"), ("reality", "no_edge"))
_FALLBACK_RESURRECTION: dict[str, tuple[str, str]] = {
    "cost_killed": ("repair", "lower_frequency_limit_entry"),
    "regime_specific": ("conditional", "regime_conditioned"),
    "wrong_direction": ("inverse", "mirrored_direction"),
    "wrong_asset": ("transfer", "sibling_instrument"),
    "wrong_horizon": ("repair", "longer_hold"), "unstable": ("repair", "wider_params"),
    "execution_killed": ("repair", "delayed_entry"),
    "forward_decay": ("conditional", "regime_conditioned_after_decay")}
_FALLBACK_BARREN: tuple[str, ...] = ("no_edge", "redundant")


def _graveyard() -> tuple[tuple[tuple[str, str], ...], dict[str, tuple[str, str]],
                          tuple[str, ...], str]:
    gr = _mod("graveyard_resurrection")
    if gr is not None and hasattr(gr, "GATE_CLASS") and hasattr(gr, "RESURRECTION"):
        return (tuple(gr.GATE_CLASS), dict(gr.RESURRECTION), tuple(gr.BARREN),
                "graveyard_resurrection")
    return (_FALLBACK_GATE_CLASS, _FALLBACK_RESURRECTION, _FALLBACK_BARREN,
            "local fallback (graveyard_resurrection did not import)")


def classify_failure(reason: str, gate: str = "") -> str:
    """The graveyard's own gate->class table. An unrecognised reason is named, never guessed."""
    table, _routes, _barren, _src = _graveyard()
    text = f"{reason} {gate}".lower()
    for token, cls in table:
        if token in text:
            return cls
    return UNMEASURED


def mine_failure(ctx: Ctx) -> dict[str, Any]:
    """Every judged macro cell classified and routed; no_edge and redundant lower the prior."""
    ctx.enter("failure")
    rows: list[dict[str, Any]] = []
    reg = _registry()
    _table, routes, barren, source = _graveyard()
    if reg is None or ctx.conn is None:
        ctx.unmeasured("failure:registry", "no registry connection on this box")
        return _result(ctx, "failure", rows, extra={"classifier": source})
    judged = [c for c in reg.candidates(limit=2000, conn=ctx.conn)
              if str(c.get("generator") or "").startswith(TAG)
              and str(c.get("status") or "") in ("judged", "rejected", "tested")]
    if not judged:
        ctx.unmeasured("failure:cells",
                       "no judged macro cell in the registry: the failure lane is UNMEASURED, "
                       "which is a verdict and not a zero")
        return _result(ctx, "failure", rows, extra={"classifier": source})
    classes: dict[str, int] = {}
    priors: list[dict[str, Any]] = []
    descendants: list[dict[str, Any]] = []
    for cell in judged:
        reason = str(cell.get("rejection_reason") or "")
        gate = str(cell.get("terminal_gate") or "")
        cls = classify_failure(reason, gate)
        classes[cls] = classes.get(cls, 0) + 1
        row: dict[str, Any] = {"candidate_id": cell.get("id"), "family": cell.get("family"),
                               "symbol": cell.get("symbol"), "failure_class": cls,
                               "terminal_gate": gate, "reason": reason[:160]}
        if cls == UNMEASURED:
            row["disposition"] = _disposition("DATA_BLOCKED", "DATA_BLOCKED")
            row["why"] = "the rejection reason matches no gate token in the graveyard's table"
            ctx.unmeasured(f"failure:{cell.get('id')}", row["why"])
        elif cls in barren:
            row["disposition"] = _disposition("ECONOMICALLY_INVALID", "ECONOMICALLY_INVALID")
            row["why"] = ("no_edge and redundant mean the GROUND is barren rather than the "
                          "expression wrong: the prior is lowered and no descendant is spawned")
            priors.append({"family": cell.get("family"), "symbol": cell.get("symbol"),
                           "class": cls, "action": "lower_prior"})
        else:
            kind, move = routes.get(cls, ("repair", "wider_params"))
            child = {"parent": cell.get("id"), "failure_class": cls, "kind": kind, "move": move,
                     "family": cell.get("family"), "symbol": cell.get("symbol")}
            descendants.append(child)
            row["disposition"] = _disposition("GENERATED", "GENERATED")
            row["descendant"] = child
            ctx.record_discovery(
                mechanism=f"failure_resurrection:{cls}",
                actor="global macro funds", information="price_only",
                economic_rationale=(
                    f"a macro cell died at {gate or 'an unnamed gate'} as {cls}; the graveyard's "
                    f"route for that class is a {kind} ({move}), which is a NEW cell with its "
                    "own trial rather than a re-read of the old one"),
                assets=[str(cell.get("symbol") or "")], horizons=[], sessions=["all"],
                regimes=[], required_data=["alpha_registry"],
                pit_requirements=["the parent's own data requirements carry over"],
                novelty=0.4, confidence=0.4,
                parent_discovery_ids=[str(cell.get("discovery_id") or "")]
                if cell.get("discovery_id") else [],
                falsifier=f"the {kind} cell dies at the same gate as its parent",
                payload={"child": child, "classifier": source})
        rows.append(row)
        if ctx.over():
            break
    return _result(ctx, "failure", rows,
                   extra={"classifier": source, "classes": classes, "n_judged": len(judged),
                          "descendants": descendants, "priors_lowered": priors,
                          "rule": "every failure generates questions; no_edge and redundant "
                                  "lower the prior instead of spawning"})


# =============================================================================================
# 14. the residual miner
# =============================================================================================
def _perm_helper() -> Callable[..., float] | None:
    sd = _mod("shadow_discovery")
    fn = getattr(sd, "_perm_p", None) if sd is not None else None
    return fn if callable(fn) else None


def mine_residual(ctx: Ctx) -> dict[str, Any]:
    """Actual minus model: the macro factors are removed, and what recurs is the discovery."""
    ctx.enter("residual")
    rows: list[dict[str, Any]] = []
    factors: dict[str, dict[str, float]] = {}
    for key, _what in RATE_FACTORS[:3]:
        points = ctx.series(key)
        if len(points) >= 60:
            factors[key] = dict(points)
    usd = ctx.symbols(("symbol:EURUSD",))
    gold = ctx.symbols(("symbol:XAUUSD",))
    if not factors:
        ctx.unmeasured("residual:factors",
                       "no rate factor with 60 observations on this box, so the residual is "
                       "taken against the price factors alone and the row says so")
    symbols = ctx.symbols(("class:Forex", "prefix:XAU", "class:Indices"))
    if not symbols:
        ctx.unmeasured("residual:instruments", "no executable instrument resolved")
        return _result(ctx, "residual", rows)
    price_factors: dict[str, pd.Series] = {}
    for name, picked in (("usd", usd), ("gold", gold)):
        for symbol in picked:
            frame = ctx.bars(symbol, "H1")
            if frame is None or len(frame) < MIN_OBS:
                continue
            closes = frame["close"].resample("1D").last().dropna()
            if len(closes) < 60:
                continue
            price_factors[name] = pd.Series(np.concatenate(
                ([np.nan], np.diff(np.log(closes.to_numpy(dtype=float))))),
                index=closes.index).rename(name)
            break
    perm = _perm_helper()
    for symbol in symbols[:10]:
        if symbol in (usd[:1] + gold[:1]):
            continue
        frame = ctx.bars(symbol, "H1")
        if frame is None or len(frame) < MIN_OBS:
            ctx.unmeasured(f"residual:{symbol}", "no H1 bars on this box")
            continue
        closes = frame["close"].resample("1D").last().dropna()
        if len(closes) < 90:
            ctx.unmeasured(f"residual:{symbol}:daily", "fewer than 90 daily bars")
            continue
        ret = pd.Series(np.concatenate(([np.nan], np.diff(np.log(
            closes.to_numpy(dtype=float))))), index=closes.index).rename("r")
        parts = [ret, *price_factors.values()]
        for key, table in factors.items():
            parts.append(pd.Series({pd.Timestamp(d, tz=UTC): v for d, v in table.items()}
                                   ).sort_index().diff().rename(key))
        panel = pd.concat(parts, axis=1).dropna()
        if len(panel) < 60:
            ctx.unmeasured(f"residual:{symbol}:panel",
                           f"the aligned factor panel is {len(panel)} days, below 60")
            continue
        y = panel["r"].to_numpy(dtype=float)
        x = np.column_stack([_z(panel[c].to_numpy(dtype=float))
                             for c in panel.columns if c != "r"])
        fit = ols(y, x)
        design = np.column_stack([np.ones(len(y)), x])
        beta = np.concatenate([[fit.get("intercept", 0.0)], np.asarray(fit["beta"] or [])])
        eps = y - design @ beta if beta.size == design.shape[1] else y - float(np.mean(y))
        gen = _rng("residual", symbol)
        eras = np.asarray([era_of(i) for i in panel.index])
        by_era = {}
        for era in sorted(set(eras)):
            mask = eras == era
            t, n = one_sample_t(eps[mask])
            by_era[era] = {"n": int(n), "t": t, "below_floor": bool(n < 30)}
        hours = np.asarray([i.dayofweek for i in panel.index])

        def _diff(vals: np.ndarray, labels: np.ndarray) -> float:
            sel = np.asarray(labels) == 0
            if sel.sum() < 2 or (~sel).sum() < 2:
                return float("nan")
            return float(vals[sel].mean() - vals[~sel].mean())

        stat = _diff(eps, hours)
        p_local = permutation_p(stat, eps, hours, _diff, gen, 200)
        p_shadow = None
        if perm is not None:
            try:
                null = np.asarray([_diff(eps, gen.permutation(hours)) for _ in range(200)])
                p_shadow = float(perm(stat, null[np.isfinite(null)]))
            except (TypeError, ValueError):
                p_shadow = None
        rows.append({"symbol": symbol, "n": len(panel),
                     "factors": [c for c in panel.columns if c != "r"],
                     "r2": fit.get("r2"), "residual_mean": float(np.mean(eps)),
                     "monday_minus_rest": None if not math.isfinite(stat) else float(stat),
                     "p_permutation": p_local, "p_shadow_discovery": p_shadow,
                     "by_era": by_era, "null": PERMUTATION,
                     "control": "the same residual on every other weekday",
                     "helper": "shadow_discovery._perm_p" if perm is not None
                               else "local permutation (shadow_discovery did not import)"})
        if ctx.over():
            break
    return _result(ctx, "residual", rows)


# =============================================================================================
# 15. the transfer miner -- ONE DISPOSITION PER OPERATOR, ALWAYS FOURTEEN
# =============================================================================================
def _tm_context(ctx: Ctx, tm: Any) -> Any:
    """A `transformation_miners.Context` built from what this box can actually see."""
    instruments: dict[str, list[str]] = {}
    for cls in ("Forex", "Commodities", "Indices", "Bonds", "Energy"):
        got = ctx.symbols((f"class:{cls}",))
        if got:
            instruments[cls.lower()] = got[:24]
    return tm.Context(instruments=instruments,
                      families=frozenset(getattr(tm, "CONTRACTS", {}) or ()),
                      bars_available=lambda s, c: ctx.bars(s, c) is not None,
                      lane_ok=lambda s: True, conn=ctx.conn)


def _parents(ctx: Ctx, limit: int = 5) -> list[dict[str, Any]]:
    reg = _registry()
    if reg is None or ctx.conn is None:
        return []
    rows = reg.discoveries(limit=500, conn=ctx.conn)
    mine = [r for r in rows if str(r.get("generator") or "").startswith(TAG)]
    return (mine or rows)[:limit]


def mine_transfer(ctx: Ctx) -> dict[str, Any]:
    """Every parent asked all fourteen operators, each answered with exactly one disposition."""
    ctx.enter("transfer")
    operators = _operators()
    tm = _mod("transformation_miners")
    tm_ctx = None
    tm_why = ""
    if tm is None:
        tm_why = "transformation_miners did not import on this box"
    else:
        try:
            tm_ctx = _tm_context(ctx, tm)
        except (TypeError, AttributeError, ValueError) as exc:
            tm_why = f"transformation_miners.Context refused this box: {type(exc).__name__}"
    parents = _parents(ctx)
    rows: list[dict[str, Any]] = []
    if not parents:
        ctx.unmeasured("transfer:parents",
                       "no discovery in the registry to expand; the operator table is still "
                       "published so the debt is visible")
    for parent in parents or [{}]:
        spec = {"discovery_id": parent.get("discovery_id", ""),
                "family": parent.get("mechanism") or "macro",
                "symbol": (json.loads(parent["assets_json"])[0]
                           if parent.get("assets_json") else ""),
                "chart": "H1", "session": "all", "params": {}}
        dispositions: list[dict[str, Any]] = []
        for operator in operators:
            impl = OPERATOR_IMPL.get(operator, "")
            entry: dict[str, Any] = {"parent": spec["discovery_id"], "operator": operator,
                                     "implementation": impl or None}
            if not impl:
                entry["disposition"] = _disposition("ECONOMICALLY_INVALID", "DATA_BLOCKED")
                entry["why"] = ("no transformation_miners implementation answers this operator; "
                                "the parent itself is the ORIGINAL cell and is already queued")
            elif tm_ctx is None or tm is None:
                entry["disposition"] = _disposition("DATA_BLOCKED", "DATA_BLOCKED")
                entry["why"] = tm_why or "the operator lane is unreachable on this box"
            elif not parents:
                entry["disposition"] = _disposition("DATA_BLOCKED", "DATA_BLOCKED")
                entry["why"] = "no parent discovery to expand"
            else:
                fn = (getattr(tm, "MINERS", {}) or {}).get(impl)
                if fn is None:
                    entry["disposition"] = _disposition("DATA_BLOCKED", "DATA_BLOCKED")
                    entry["why"] = f"transformation_miners has no miner named {impl!r}"
                else:
                    try:
                        children = list(fn(spec, tm_ctx))
                    except Exception as exc:
                        children = []
                        entry["error"] = f"{type(exc).__name__}: {exc}"
                    entry["n_children"] = len(children)
                    if children:
                        entry["disposition"] = _disposition("GENERATED", "GENERATED")
                        entry["why"] = f"{len(children)} child cells from {impl}"
                    elif entry.get("error"):
                        entry["disposition"] = _disposition("DATA_BLOCKED", "DATA_BLOCKED")
                        entry["why"] = f"the operator raised: {entry['error']}"
                    else:
                        entry["disposition"] = _disposition("ALREADY_TESTED", "DUPLICATE")
                        entry["why"] = (f"{impl} produced no child for this parent: its axis is "
                                        "already covered or its contract refuses this cell")
            dispositions.append(entry)
        rows.append({"parent": spec["discovery_id"], "n_operators": len(dispositions),
                     "dispositions": dispositions,
                     "complete": bool(len(dispositions) == len(operators))})
        if ctx.over():
            break
    return _result(ctx, "transfer", rows,
                   extra={"operators": list(operators), "n_operators": len(operators),
                          "dispositions_vocabulary": list(_dispositions()),
                          "rule": "one disposition per operator; silence is not a disposition"})


# =============================================================================================
# The registry of miners, and the time box
# =============================================================================================
MINERS: dict[str, Callable[[Ctx], dict[str, Any]]] = {
    "central_bank": mine_central_bank,
    "release": mine_release,
    "positioning": mine_positioning,
    "rates": mine_rates,
    "curve": mine_curve,
    "fiscal_auction": mine_fiscal_auction,
    "intervention": mine_intervention,
    "propagation": mine_propagation,
    "fixing": mine_fixing,
    "commodity_fundamentals": mine_commodity_fundamentals,
    "risk_regime": mine_risk_regime,
    "calendar_mismatch": mine_calendar_mismatch,
    "failure": mine_failure,
    "residual": mine_residual,
    "transfer": mine_transfer,
}


def run_miner(name: str, ctx: Ctx | None = None, **ctx_kwargs: Any) -> dict[str, Any]:
    """One miner inside its time box, with the uniform result. A raise is a RESULT, not a stop.

    A miner that raises costs the other fourteen nothing: the exception is named on the row and
    the pass continues, because a department that stops on one bad symbol measures nothing.
    """
    fn = MINERS.get(name)
    context = ctx if ctx is not None else make_ctx(**ctx_kwargs)
    if fn is None:
        return {"miner": name, "generator": f"{TAG}{name}", "region": REGION, "ok": False,
                "error": f"unknown miner {name!r}", "rows": [], "n_rows": 0,
                "unmeasured": [{"what": name, "why": "no such miner in this department"}],
                "notes": [], "discoveries": [], "seconds": 0.0}
    context.enter(name)
    started = time.monotonic()
    try:
        out = fn(context)
    except Exception as exc:
        return {"miner": name, "generator": f"{TAG}{name}", "region": REGION, "ok": False,
                "error": f"{type(exc).__name__}: {exc}", "rows": [], "n_rows": 0,
                "seconds": round(time.monotonic() - started, 3),
                "unmeasured": [{"what": name, "why": f"the miner raised {type(exc).__name__}"}],
                "notes": list(context.notes), "discoveries": list(context.recorded)}
    out.setdefault("ok", True)
    out["seconds"] = round(time.monotonic() - started, 3)
    out["over_budget"] = bool(out["seconds"] > context.budget_s)
    return out


def run_all(ctx: Ctx | None = None, only: Sequence[str] | None = None,
            **ctx_kwargs: Any) -> dict[str, Any]:
    """Every miner on the same context, independently. One weak miner costs the others nothing."""
    context = ctx if ctx is not None else make_ctx(**ctx_kwargs)
    wanted = [n for n in MINERS if only is None or n in set(only)]
    results = {name: run_miner(name, context) for name in wanted}
    return {"region": REGION, "tag": TAG, "n_miners": len(results),
            "results": results,
            "n_rows": sum(int(r.get("n_rows") or 0) for r in results.values()),
            "n_discoveries": len(context.recorded),
            "unmeasured": list(context.unmeasured_rows),
            "failed": [n for n, r in results.items() if not r.get("ok")]}
