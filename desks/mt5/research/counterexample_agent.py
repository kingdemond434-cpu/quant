"""W6 -- THE ADVERSARY THAT ATTACKS A HYPOTHESIS BEFORE THE GAUNTLET SPENDS A TRIAL ON IT.

THE LEDGER ITEM (Tier-1 W6) lists fourteen search paradigms feeding one intake and names the one
the desk did not have: a COUNTEREXAMPLE AGENT. Every other paradigm on that list PROPOSES. This
one does the opposite job, and it is the job nothing on this desk was funded to do: take a
candidate somebody is about to spend a trial on, and try to break it.

WHY IT PAYS, IN THE DESK'S OWN NUMBERS. The deflated-Sharpe charge and the program-level SPA/PBO
tests divide ONE family-wise error budget across every hypothesis the desk tests; `deflated_sharpe`
rejected 42 of 42 judged cells at 597 trials on the 2026-09-06 campaign. A cell that dies to a
five-minute counterexample and a cell that dies to the ten gates are the same dead cell, but the
first one did not raise the bar for every FX and metals hypothesis behind it. The cheapest place to
kill a wrong idea is before it is charged.

THE FIVE ATTACKS, each a counterexample the claim must survive, each decided by ONE statistic that
is published with the verdict:

  placebo_symbol    the same rule on an instrument in a DIFFERENT asset class. If an unrelated
                    market pays the same, the statistic is generic and the mechanism is not what
                    earns it.
  placebo_date      the same rule with its entry times ROTATED around the bar index -- same
                    count, same holds, same instrument, wrong dates. The share of rotations that
                    match or beat the real timing is an empirical p-value on the timing itself.
  sign_flip         does the OPPOSITE rule earn the same? Under a symmetric evaluator flipping
                    every side returns exactly -t, so that arithmetic answers nothing. The
                    question that has content is whether the rule's CHOICE OF SIDE carries the
                    edge: a static always-long (or always-short) position over the same entry
                    times and the same holds is the opposite rule's honest stand-in, and a rule
                    the static position matches is harvesting drift, not direction. A ONE-SIDED
                    family is UNMEASURED here and says so -- its flip is its own mirror by
                    construction, and `placebo_date` is where a one-sided rule is attacked.
  neighbour_param   one step on one parameter. A CLIFF is a counterexample and a PLATEAU is not:
                    a parameter that works at 37 and fails at 30 and 45 was chosen by the data.
                    Decided by `search_controller.plateau_check`, the desk's own rule, not a
                    second opinion written here.
  excluded_window   drop the single best month. If the whole effect lived there, the effect is
                    that month.

WHAT IT MAY DO, AND WHAT IT MAY NEVER DO. Every verdict is written ON THE CANDIDATE'S REGISTRY
ROW as evidence -- `counterexample_verdict`, `counterexample_broken_by`, `counterexample_judged_at`
through `registry.mark_candidate` with the row's OWN status passed back unchanged, exactly as
`event_graph_lab` records a causal verdict. NO STATUS CHANGES. NOTHING IS BLOCKED, VETOED, CAPPED
OR WITHDRAWN. The sealed gauntlet and the promoter remain the only judges (L1.60), and the desk
never reduces its aggressiveness on a report's say-so. The POSITIVE signal is the output that
matters: the candidates whose attacks ALL survived are the ones the queue can prioritise, which
is more shots taken, not fewer.

UNMEASURED IS A VERDICT (L1.28a). A family with no constructor on this tree, a symbol with no
bars, a sample under the independent-trade floor: each is recorded with its reason. An attack
that could not run is never a survival.

    python desks/mt5/research/counterexample_agent.py --once --budget-s 600
    python desks/mt5/research/counterexample_agent.py --dry-run --max-attacks 5
"""
from __future__ import annotations

import argparse
import contextlib
import inspect
import json
import math
import os
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REPORT = DESK / "reports" / "COUNTEREXAMPLE_AGENT.json"
UNIVERSE = DESK / "data" / "universe"

SOURCE = "counterexample_agent"
BUDGET_S = 600.0
MAX_ATTACKS = 40
ATTACKS = ("placebo_symbol", "placebo_date", "sign_flip", "neighbour_param", "excluded_window")

#: Independent non-overlapping trades a series needs before its mean is a number rather than an
#: anecdote. The same floor `proposer_common.screen` uses, restated here because this organ needs
#: the per-trade series that the screen aggregates away.
MIN_TRADES = 30
#: Rotations of the entry index the placebo-date attack tries. Each is a different wrong answer
#: to "when"; the share that beat the real timing is the p-value.
ROTATIONS = 12
#: The placebo beat is a counterexample at this share of the baseline's t.
PLACEBO_SHARE = 0.75
#: Rotation p-value at or above which the timing carries nothing.
ROTATION_P = 0.20
#: A static one-sided position over the same windows earning this share of the rule's edge means
#: the rule's SIDES are not what earns.
FLIP_SHARE = 0.90
#: Trades each side needs before the sign flip will judge a family two-sided.
MIN_SIDE_TRADES = 10
#: Calendar months the trade series needs before the best one can be dropped.
MIN_MONTHS = 3
#: What the remainder must keep, after the best month is dropped, to be a plateau rather than one
#: month wearing a strategy's name.
EXCLUDED_SHARE = 0.25
#: Parameters attacked per candidate. Each costs two family evaluations.
MAX_PARAMS = 4

RULE = ("attack the hypothesis before the gauntlet is charged for it: five counterexamples, one "
        "statistic each, recorded as evidence and never as a veto")


# --------------------------------------------------------------------------------- plumbing
@dataclass(frozen=True)
class Sig:
    """One signal, reduced to what every attack needs: when, which way, how long."""

    time: Any
    side: int
    ttl_bars: int


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _row(name: str, present: bool, why: str) -> dict[str, Any]:
    return {"name": name, "status": "present" if present else "absent", "why": why}


def _write(path: Path, doc: Any) -> None:
    """Atomic, and it survives the read-only destination that broke the frontier fix on Windows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    try:
        os.replace(tmp, path)
    except PermissionError:                                             # pragma: no cover
        os.chmod(path, 0o644)
        os.replace(tmp, path)


def _params(raw: Any) -> dict[str, Any]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return {}
    return dict(raw) if isinstance(raw, dict) else {}


# ------------------------------------------------------------------------- bars and signals
def load_bars(symbol: str) -> pd.DataFrame | None:
    """The desk's own H1 bars. One door, so a test stands in for the whole universe."""
    try:
        from research import proposer_common as pc
    except Exception:                                                   # pragma: no cover
        return None
    return pc.bars(symbol)


def family_signals(d: pd.DataFrame, family: str, params: dict[str, Any]) -> tuple[list[Sig], str]:
    """The family's own signals on these bars, or ([], why) when it cannot be constructed.

    Parameters the constructor does not accept are DROPPED and named. A candidate row carries
    whatever its donor wrote; handing an unknown keyword to a family would turn "this rule has a
    parameter the desk renamed" into "this rule crashed", and the two are not the same fact.
    """
    try:
        from mt5desk.families import get_family_func
    except Exception as exc:
        return [], f"{type(exc).__name__}: {exc}"
    fn = get_family_func(str(family))
    if fn is None:
        return [], f"no constructor for family {family!r} on this tree"
    try:
        accepted = set(inspect.signature(fn).parameters)
    except (TypeError, ValueError):                                     # pragma: no cover
        accepted = set(params)
    kwargs = {k: v for k, v in params.items() if k in accepted and k != "df"}
    try:
        raw = fn(d, **kwargs) or []
    except Exception as exc:
        return [], f"{type(exc).__name__}: {exc}"
    out: list[Sig] = []
    for s in raw:
        t = getattr(s, "time", None)
        side = getattr(s, "side", 0)
        if t is None or not side:
            continue
        out.append(Sig(time=t, side=int(side), ttl_bars=max(1, int(getattr(s, "ttl_bars", 1)))))
    dropped = sorted(set(params) - accepted - {"df"})
    why = f"{len(out)} signal(s) from {family}" + (f"; dropped {dropped}" if dropped else "")
    return out, why


# ------------------------------------------------------------------------------- the ruler
def trades(d: pd.DataFrame, sigs: list[Sig]) -> tuple[list[Any], np.ndarray]:
    """Non-overlapping signed log returns, and the entry timestamp of each.

    THE SCREEN'S RULE, RESTATED TO EXPOSE THE SERIES IT AGGREGATES AWAY. Entry is the OPEN of the
    bar after the signal, as the engine fills it; exit is the close `ttl_bars` later; a signal
    inside a live trade's window is skipped because a single-position engine could not have taken
    it. `proposer_common.screen` applies the identical rule and returns the summary -- this organ
    needs the per-trade series, because dropping the best MONTH and rotating the entry DATES are
    both operations on individual trades.

    NO ARTIFACT-HOUR MAP IS APPLIED, and that is deliberate rather than an omission: a
    counterexample is a COMPARISON, and a filter applied to the baseline but not (identically) to
    every attack would manufacture the verdict. The desk's artifact refusal belongs to the screen
    that PROPOSES; the ten gates remain the only judges of truth.
    """
    if not sigs or d.empty or "open" not in d.columns or "close" not in d.columns:
        return [], np.zeros(0, dtype=float)
    idx = d.index
    o = d["open"].astype(float).to_numpy()
    c = d["close"].astype(float).to_numpy()
    pos = {ts: i for i, ts in enumerate(idx)}
    times: list[Any] = []
    out: list[float] = []
    last_exit = -1
    for s in sorted(sigs, key=lambda x: x.time):
        i = pos.get(s.time)
        if i is None:
            continue
        entry = i + 1
        if entry >= len(o) or entry <= last_exit:
            continue
        exit_ = min(entry + max(1, int(s.ttl_bars)), len(c) - 1)
        if exit_ <= entry or o[entry] <= 0 or c[exit_] <= 0:
            continue
        r = math.log(c[exit_] / o[entry]) * int(s.side)
        if not math.isfinite(r):
            continue
        out.append(r)
        times.append(idx[entry])
        last_exit = exit_
    return times, np.asarray(out, dtype=float)


def stat(r: np.ndarray) -> dict[str, Any] | None:
    """(n, mean, t) for a trade series, or None below the independent-trade floor."""
    if r.size < MIN_TRADES:
        return None
    sd = float(r.std(ddof=1))
    if not math.isfinite(sd) or sd <= 0:
        return None
    mean = float(r.mean())
    return {"n": int(r.size), "mean_per_trade": round(mean, 8),
            "t": round(mean / (sd / math.sqrt(r.size)), 4)}


def _verdict(name: str, status: str, why: str, **detail: Any) -> dict[str, Any]:
    return {"attack": name, "status": status, "why": why, **detail}


# --------------------------------------------------------------------------------- attacks
def placebo_symbol(d: pd.DataFrame, sigs: list[Sig], base: dict[str, Any], *, family: str,
                   params: dict[str, Any], symbol: str,
                   placebo: str | None) -> dict[str, Any]:
    if not placebo:
        return _verdict("placebo_symbol", "UNMEASURED",
                        f"no instrument in another asset class with bars beside {symbol}")
    pd_bars = load_bars(placebo)
    if pd_bars is None or len(pd_bars) < 500:
        return _verdict("placebo_symbol", "UNMEASURED",
                        f"placebo {placebo} has no usable bars on this tree", placebo=placebo)
    psigs, why = family_signals(pd_bars, family, params)
    if not psigs:
        return _verdict("placebo_symbol", "UNMEASURED",
                        f"the rule produced no signal on {placebo}: {why}", placebo=placebo)
    _t, r = trades(pd_bars, psigs)
    s = stat(r)
    if s is None:
        return _verdict("placebo_symbol", "UNMEASURED",
                        f"{placebo} yielded {r.size} independent trade(s), below the floor of "
                        f"{MIN_TRADES}", placebo=placebo)
    tb, tp = float(base["t"]), float(s["t"])
    share = round(tp / tb, 4) if tb else None
    broken = bool(tb > 0 and tp >= PLACEBO_SHARE * tb)
    return _verdict("placebo_symbol", "BROKEN" if broken else "SURVIVED",
                    (f"{placebo} (a different asset class) scores t={tp:+.2f} against the "
                     f"claim's t={tb:+.2f} on {symbol}"
                     + (f" -- {share:.2f} of it, at or above the {PLACEBO_SHARE:.0%} bar, so the "
                        f"statistic is generic" if broken
                        else f" -- {share if share is None else f'{share:.2f}'} of it, below the "
                             f"{PLACEBO_SHARE:.0%} bar")),
                    placebo=placebo, statistic="t_placebo/t_base", value=share,
                    t_placebo=tp, n_placebo=s["n"])


def placebo_date(d: pd.DataFrame, sigs: list[Sig], base: dict[str, Any], *,
                 rotations: int = ROTATIONS, rng: np.random.Generator | None = None
                 ) -> dict[str, Any]:
    """Rotate the entry index. Same count, same holds, same bars, wrong dates."""
    idx = list(d.index)
    n = len(idx)
    if n < 200 or len(sigs) < 2:
        return _verdict("placebo_date", "UNMEASURED",
                        f"{n} bar(s) and {len(sigs)} signal(s): too little to rotate")
    g = rng if rng is not None else np.random.default_rng(17)
    pos = {ts: i for i, ts in enumerate(idx)}
    anchors = [pos[s.time] for s in sigs if s.time in pos]
    if len(anchors) < 2:
        return _verdict("placebo_date", "UNMEASURED", "no signal lands on a known bar")
    offsets = sorted({int(x) for x in g.integers(n // 10, n - n // 10, size=int(rotations) * 2)})
    ts_list: list[float] = []
    for off in offsets[:int(rotations)]:
        moved = [Sig(time=idx[(pos[s.time] + off) % n], side=s.side, ttl_bars=s.ttl_bars)
                 for s in sigs if s.time in pos]
        _t, r = trades(d, moved)
        s2 = stat(r)
        if s2 is not None:
            ts_list.append(float(s2["t"]))
    if len(ts_list) < 4:
        return _verdict("placebo_date", "UNMEASURED",
                        f"only {len(ts_list)} rotation(s) cleared the {MIN_TRADES}-trade floor")
    tb = float(base["t"])
    beat = sum(1 for x in ts_list if x >= tb)
    p = round(beat / len(ts_list), 4)
    broken = bool(p >= ROTATION_P)
    return _verdict("placebo_date", "BROKEN" if broken else "SURVIVED",
                    (f"{beat} of {len(ts_list)} rotated-date placebos matched or beat the real "
                     f"timing (t={tb:+.2f}), an empirical p of {p:.2f}"
                     + (f" at or above the {ROTATION_P:.2f} bar -- the DATES carry nothing"
                        if broken else f", below the {ROTATION_P:.2f} bar")),
                    statistic="share of rotations with t >= t_base", value=p,
                    rotations=len(ts_list), null_t_mean=round(float(np.mean(ts_list)), 4),
                    null_t_sd=round(float(np.std(ts_list, ddof=1)), 4) if len(ts_list) > 1
                    else None)


def sign_flip(d: pd.DataFrame, sigs: list[Sig], base: dict[str, Any]) -> dict[str, Any]:
    """Does the opposite rule earn the same? Asked of the SIDES, which is where it has content."""
    sides = {s.side for s in sigs}
    longs = sum(1 for s in sigs if s.side > 0)
    shorts = sum(1 for s in sigs if s.side < 0)
    if len(sides) < 2 or min(longs, shorts) < MIN_SIDE_TRADES:
        return _verdict("sign_flip", "UNMEASURED",
                        (f"the family emits {longs} long and {shorts} short signal(s): a "
                         f"one-sided rule's flip is its own mirror by construction "
                         f"(t_flip = -t_base exactly under a symmetric evaluator), which is "
                         f"arithmetic and not a counterexample -- `placebo_date` is where a "
                         f"one-sided rule is attacked"),
                        longs=longs, shorts=shorts, t_flip=round(-float(base["t"]), 4))
    flat = [Sig(time=s.time, side=1, ttl_bars=s.ttl_bars) for s in sigs]
    _t, raw = trades(d, flat)
    s_static = stat(raw)
    if s_static is None:
        return _verdict("sign_flip", "UNMEASURED",
                        f"the static always-long stand-in yielded {raw.size} trade(s), below "
                        f"the floor of {MIN_TRADES}")
    edge = abs(float(base["mean_per_trade"]))
    drift = abs(float(s_static["mean_per_trade"]))
    share = round(drift / edge, 4) if edge > 0 else None
    broken = bool(edge > 0 and drift >= FLIP_SHARE * edge)
    return _verdict("sign_flip", "BROKEN" if broken else "SURVIVED",
                    (f"a static one-sided position over the same {s_static['n']} entry times and "
                     f"holds earns {drift:.6f} per trade against the rule's {edge:.6f}"
                     + (f" ({share:.2f}, at or above the {FLIP_SHARE:.0%} bar) -- the SIDES carry "
                        f"no information and the 'edge' is drift" if broken
                        else f" ({share if share is None else f'{share:.2f}'}, below the "
                             f"{FLIP_SHARE:.0%} bar), so the rule's choice of side is what earns")),
                    statistic="|static one-sided mean| / |rule mean|", value=share,
                    t_flip=round(-float(base["t"]), 4), longs=longs, shorts=shorts)


def _neighbours(family: str, key: str, value: Any) -> list[Any]:
    """TWO steps either side of a parameter, off the family's own grid where it has one.

    Two rather than one, because `plateau_check` judges the peak's IMMEDIATE neighbours and
    refuses to judge at all when the peak sits at the edge of the grid it was handed. A
    three-point grid centred on the claim puts the peak at an edge the moment one neighbour
    scores higher -- which is common and is not a cliff -- so the grid is widened until the
    claim's own value has a measured neighbourhood on both sides.
    """
    try:
        from mt5desk.families import get_param_grid
        grid = [g for g in (get_param_grid(str(family)) or {}).get(key, [])
                if isinstance(g, (int, float)) and not isinstance(g, bool)]
    except Exception:                                                   # pragma: no cover
        grid = []
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return []
    if len(grid) >= 5:
        ordered = sorted(set(grid))
        nearest = min(range(len(ordered)), key=lambda i: abs(ordered[i] - value))
        return [ordered[i] for i in (nearest - 2, nearest - 1, nearest + 1, nearest + 2)
                if 0 <= i < len(ordered) and ordered[i] != value]
    if isinstance(value, int):
        return [v for v in (value - 2, value - 1, value + 1, value + 2) if v >= 1]
    step = abs(value) * 0.2 or 0.1
    return [round(value - 2 * step, 6), round(value - step, 6),
            round(value + step, 6), round(value + 2 * step, 6)]


def neighbour_param(d: pd.DataFrame, base: dict[str, Any], *, family: str,
                    params: dict[str, Any], max_params: int = MAX_PARAMS) -> dict[str, Any]:
    """A CLIFF is a counterexample; a PLATEAU is not. Decided by the desk's own plateau rule."""
    try:
        from libs.research.search_controller import plateau_check
    except Exception as exc:                                            # pragma: no cover
        return _verdict("neighbour_param", "UNMEASURED", f"{type(exc).__name__}: {exc}")
    numeric = [k for k, v in params.items()
               if isinstance(v, (int, float)) and not isinstance(v, bool)][:int(max_params)]
    if not numeric:
        return _verdict("neighbour_param", "UNMEASURED",
                        "the candidate declares no numeric parameter to step")
    tb = float(base["t"])
    tested: list[dict[str, Any]] = []
    for key in numeric:
        scores: dict[int, float] = {}
        values: list[Any] = []
        for rank, value in enumerate(sorted([*_neighbours(family, key, params[key]),
                                             params[key]])):
            sigs, _why = family_signals(d, family, {**params, key: value})
            if not sigs:
                continue
            _t, r = trades(d, sigs)
            s = stat(r)
            if s is None:
                continue
            scores[rank] = float(s["t"])
            values.append(value)
        if len(scores) < 3:
            tested.append({"param": key, "status": "UNMEASURED",
                           "why": f"{len(scores)} of 3 grid point(s) cleared the trade floor"})
            continue
        ok, why = plateau_check(scores)
        # PLATEAU / CLIFF / EDGE, and the third is not the second. `plateau_check` refuses the
        # peak that sits at the edge of the grid because its neighbourhood is unmeasured on one
        # side -- that is an absent measurement, and calling it a counterexample would break a
        # claim on the strength of a grid this organ chose.
        status = "PLATEAU" if ok else ("EDGE" if "EDGE" in why else "CLIFF")
        worst = min(scores.values())
        tested.append({"param": key, "status": status, "why": why,
                       "values": values, "t": [round(v, 4) for v in scores.values()],
                       "worst_share": round(worst / tb, 4) if tb else None})
    cliffs = [r for r in tested if r["status"] == "CLIFF"]
    measured = [r for r in tested if r["status"] in ("PLATEAU", "CLIFF")]
    if not measured:
        edges = [r for r in tested if r["status"] == "EDGE"]
        return _verdict("neighbour_param", "UNMEASURED",
                        (f"{len(edges)} parameter peak(s) sat at the edge of the stepped grid "
                         f"and the rest could not be stepped with enough trades: the "
                         f"neighbourhood is unmeasured, which is not a cliff" if edges
                         else "no parameter could be stepped with enough trades on either side"),
                        params_tested=tested)
    if cliffs:
        return _verdict("neighbour_param", "BROKEN",
                        f"{len(cliffs)} of {len(measured)} stepped parameter(s) sit on a CLIFF: "
                        + "; ".join(f"{r['param']} -- {r['why']}" for r in cliffs[:3]),
                        statistic="plateau_check over one step either side",
                        value=cliffs[0].get("worst_share"), params_tested=tested)
    return _verdict("neighbour_param", "SURVIVED",
                    f"all {len(measured)} stepped parameter(s) sit on a plateau",
                    statistic="plateau_check over one step either side",
                    value=min([float(r["worst_share"]) for r in measured
                               if r.get("worst_share") is not None], default=None),
                    params_tested=tested)


def excluded_window(times: list[Any], r: np.ndarray, base: dict[str, Any]) -> dict[str, Any]:
    """Drop the single best month. If the whole effect lived there, the effect IS that month."""
    if r.size < MIN_TRADES or len(times) != r.size:
        return _verdict("excluded_window", "UNMEASURED",
                        f"{r.size} trade(s) with {len(times)} stamp(s): the series cannot be "
                        f"split by month")
    months: dict[str, list[int]] = {}
    for i, t in enumerate(times):
        try:
            key = pd.Timestamp(t).strftime("%Y-%m")
        except (TypeError, ValueError):                                 # pragma: no cover
            continue
        months.setdefault(key, []).append(i)
    if len(months) < MIN_MONTHS:
        return _verdict("excluded_window", "UNMEASURED",
                        f"{len(months)} calendar month(s), below the floor of {MIN_MONTHS}")
    totals = {m: float(r[ix].sum()) for m, ix in months.items()}
    best = max(totals, key=lambda m: totals[m])
    total = float(r.sum())
    keep = np.asarray([r[i] for i in range(r.size) if i not in set(months[best])], dtype=float)
    s = stat(keep)
    share = round(totals[best] / total, 4) if total else None
    if s is None:
        return _verdict("excluded_window", "UNMEASURED",
                        f"dropping {best} leaves {keep.size} trade(s), below the floor of "
                        f"{MIN_TRADES}", best_month=best, best_month_share=share)
    tb, tk = float(base["t"]), float(s["t"])
    kept = round(tk / tb, 4) if tb else None
    broken = bool(tb > 0 and (tk <= 0 or tk < EXCLUDED_SHARE * tb))
    return _verdict("excluded_window", "BROKEN" if broken else "SURVIVED",
                    (f"{best} holds {share if share is None else f'{share:.0%}'} of the total "
                     f"return over {len(months)} month(s); without it t falls from {tb:+.2f} to "
                     f"{tk:+.2f}"
                     + (f" -- below {EXCLUDED_SHARE:.0%} of the claim, so the effect IS that "
                        f"month" if broken else ", which the claim survives")),
                    statistic="t without the best month / t_base", value=kept,
                    best_month=best, best_month_share=share, months=len(months),
                    n_kept=s["n"])


# ------------------------------------------------------------------------ one candidate
def placebo_for(symbol: str, universe: tuple[str, ...]) -> str | None:
    """An instrument the mechanism cannot reach: a different ASSET CLASS, from the registry."""
    try:
        from research.universe_policy import asset_class_of
    except Exception:                                                   # pragma: no cover
        return None
    mine = asset_class_of(symbol)
    for other in universe:
        if other == symbol:
            continue
        cls = asset_class_of(other)
        if cls and mine and cls != mine and cls != "unclassified":
            return other
    return None


def attack(row: dict[str, Any], *, universe: tuple[str, ...] = (),
           seed: int = 0) -> dict[str, Any]:
    """Every attack on one candidate. Never raises: a broken input is an UNMEASURED verdict."""
    symbol = str(row.get("symbol") or "")
    family = str(row.get("family") or "")
    params = _params(row.get("params_json") if "params_json" in row else row.get("params"))
    out: dict[str, Any] = {"candidate_id": str(row.get("id") or ""), "symbol": symbol,
                           "family": family, "params": params,
                           "status_unchanged": str(row.get("status") or ""),
                           "attacks": [], "verdict": "UNMEASURED", "broken_by": []}
    d = load_bars(symbol)
    if d is None or len(d) < 500:
        out["why"] = f"{symbol}: fewer than 500 H1 bars on this tree"
        return out
    sigs, why = family_signals(d, family, params)
    out["signals"] = len(sigs)
    if not sigs:
        out["why"] = why
        return out
    times, r = trades(d, sigs)
    base = stat(r)
    if base is None:
        out["why"] = (f"{r.size} independent trade(s), below the floor of {MIN_TRADES}: the "
                      f"claim has no baseline to attack")
        return out
    out["baseline"] = base
    rng = np.random.default_rng(seed + abs(hash(out["candidate_id"])) % (2**31))
    verdicts = [
        placebo_symbol(d, sigs, base, family=family, params=params, symbol=symbol,
                       placebo=placebo_for(symbol, universe)),
        placebo_date(d, sigs, base, rng=rng),
        sign_flip(d, sigs, base),
        neighbour_param(d, base, family=family, params=params),
        excluded_window(times, r, base),
    ]
    out["attacks"] = verdicts
    broken = [v["attack"] for v in verdicts if v["status"] == "BROKEN"]
    survived = [v["attack"] for v in verdicts if v["status"] == "SURVIVED"]
    out["broken_by"] = broken
    out["survived"] = survived
    out["unmeasured"] = [v["attack"] for v in verdicts if v["status"] == "UNMEASURED"]
    if broken:
        out["verdict"] = "BROKEN"
        out["why"] = f"broken by {', '.join(broken)}"
    elif survived:
        out["verdict"] = "ALL_SURVIVED"
        out["why"] = (f"survived {len(survived)} attack(s); {len(out['unmeasured'])} could not "
                      f"be run")
    else:
        out["why"] = "no attack could be run against this candidate"
    return out


# -------------------------------------------------------------------------- registry doors
def queued(limit: int, conn: Any = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """The newest queued/claimed/donated candidates -- what a trial is about to be spent on."""
    try:
        from libs.moat import registry as reg
    except Exception as exc:
        return [], _row("registry", False, f"{type(exc).__name__}: {exc}")
    own = conn is None
    try:
        c = conn if conn is not None else reg.connect()
    except Exception as exc:                                            # pragma: no cover
        return [], _row("registry", False, f"{type(exc).__name__}: {exc}")
    try:
        cur = c.execute(
            "SELECT id, symbol, family, params_json, status, origin, generator, created_at "
            "FROM research_candidates WHERE status IN ('queued','claimed','donated') "
            "AND family IS NOT NULL AND family != '' AND symbol IS NOT NULL AND symbol != '' "
            "ORDER BY created_at DESC LIMIT ?", (int(limit),))
        rows = [dict(x) for x in cur.fetchall()]
    except Exception as exc:
        return [], _row("registry", False, f"{type(exc).__name__}: {exc}")
    finally:
        if own:
            with contextlib.suppress(Exception):
                c.close()
    return rows, _row("registry", bool(rows),
                      f"{len(rows)} queued candidate(s) read (limit {limit})" if rows
                      else "no queued candidate in the registry")


def record(results: list[dict[str, Any]], *, dry_run: bool, conn: Any = None) -> dict[str, Any]:
    """Evidence on the candidate's own row. STATUS IS PASSED BACK UNCHANGED.

    The row's current status goes straight back into `mark_candidate`, exactly as
    `event_graph_lab` records a causal verdict: this organ writes three evidence columns and an
    immutable event, and changes nothing a judge owns.
    """
    out: dict[str, Any] = {"rows": 0, "events": 0, "skipped": 0, "errors": []}
    if dry_run:
        out["skipped"] = len(results)
        return out
    try:
        from libs.moat import registry as reg
    except Exception as exc:
        out["errors"] = [f"{type(exc).__name__}: {exc}"]
        return out
    own = conn is None
    try:
        c = conn if conn is not None else reg.connect()
    except Exception as exc:                                            # pragma: no cover
        out["errors"] = [f"{type(exc).__name__}: {exc}"]
        return out
    try:
        for res in results:
            cid = str(res.get("candidate_id") or "")
            if not cid:
                out["skipped"] += 1
                continue
            try:
                if reg.mark_candidate(
                        cid, str(res.get("status_unchanged") or "queued"), conn=c,
                        counterexample_verdict=str(res.get("verdict") or "UNMEASURED"),
                        counterexample_broken_by=",".join(res.get("broken_by") or []),
                        counterexample_judged_at=_now()):
                    out["rows"] += 1
                reg.record_event(cid, "counterexample", actor=SOURCE, conn=c,
                                 detail={"verdict": res.get("verdict"),
                                         "broken_by": res.get("broken_by"),
                                         "survived": res.get("survived"),
                                         "unmeasured": res.get("unmeasured"),
                                         "baseline": res.get("baseline"), "rule": RULE})
                out["events"] += 1
            except Exception as exc:
                out["errors"].append(f"{cid}: {type(exc).__name__}: {exc}")
    finally:
        if own:
            with contextlib.suppress(Exception):
                c.close()
    return out


def universe_symbols(directory: Path = UNIVERSE, limit: int = 400) -> tuple[str, ...]:
    """Instruments with H1 bars on this tree, for the placebo to be drawn from."""
    try:
        names = sorted(p.name[:-len("_H1.parquet")] for p in directory.glob("*_H1.parquet"))
    except OSError:                                                     # pragma: no cover
        return ()
    return tuple(names[:limit])


# ------------------------------------------------------------------------------- the report
def build(*, max_attacks: int = MAX_ATTACKS, budget_s: float = BUDGET_S, dry_run: bool = False,
          seed: int = 0, conn: Any = None) -> dict[str, Any]:
    started = time.monotonic()
    rows, reg_in = queued(int(max_attacks), conn=conn)
    inputs = [reg_in]
    syms = universe_symbols()
    inputs.append(_row("universe", bool(syms),
                       f"{len(syms)} instrument(s) with H1 bars" if syms
                       else "no H1 parquet on this tree: the placebo symbol cannot be drawn"))

    results: list[dict[str, Any]] = []
    stopped = ""
    for row in rows:
        if time.monotonic() - started > float(budget_s):
            stopped = (f"budget of {budget_s:g}s spent after {len(results)} of {len(rows)} "
                       f"candidate(s)")
            break
        try:
            results.append(attack(row, universe=syms, seed=seed))
        except Exception as exc:                                        # pragma: no cover
            results.append({"candidate_id": str(row.get("id") or ""), "verdict": "UNMEASURED",
                            "why": f"{type(exc).__name__}: {exc}", "attacks": [],
                            "broken_by": []})

    per_attack: dict[str, dict[str, int]] = {
        a: {"SURVIVED": 0, "BROKEN": 0, "UNMEASURED": 0} for a in ATTACKS}
    for res in results:
        for v in res.get("attacks") or []:
            bucket = per_attack.setdefault(str(v["attack"]),
                                           {"SURVIVED": 0, "BROKEN": 0, "UNMEASURED": 0})
            bucket[str(v["status"])] = bucket.get(str(v["status"]), 0) + 1

    written = record(results, dry_run=dry_run, conn=conn)
    all_survived = [{"candidate_id": r["candidate_id"], "symbol": r.get("symbol"),
                     "family": r.get("family"), "survived": r.get("survived"),
                     "baseline_t": (r.get("baseline") or {}).get("t")}
                    for r in results if r.get("verdict") == "ALL_SURVIVED"]
    report: dict[str, Any] = {
        "at": _now(), "source": SOURCE, "rule": RULE, "dry_run": bool(dry_run),
        "budget_s": budget_s, "max_attacks": int(max_attacks), "seed": seed,
        "inputs": inputs, "stopped": stopped or None,
        "attacks": list(ATTACKS),
        "thresholds": {"placebo_share": PLACEBO_SHARE, "rotation_p": ROTATION_P,
                       "flip_share": FLIP_SHARE, "excluded_share": EXCLUDED_SHARE,
                       "min_trades": MIN_TRADES, "min_months": MIN_MONTHS,
                       "rotations": ROTATIONS},
        "per_attack": per_attack,
        "counts": {
            "candidates_read": len(rows), "candidates_attacked": len(results),
            "all_survived": len(all_survived),
            "broken": sum(1 for r in results if r.get("verdict") == "BROKEN"),
            "unmeasured": sum(1 for r in results if r.get("verdict") == "UNMEASURED"),
            "registry_rows_written": written["rows"], "events_written": written["events"],
        },
        "all_survived": all_survived[:80],
        "results": results[:120],
        "recorded": written,
        "authority": ("evidence only: no status changed, nothing blocked, vetoed or withdrawn -- "
                      "the sealed gauntlet and the promoter remain the only judges, and the "
                      "candidates whose attacks all survived are what the queue prioritises ON"),
        "elapsed_s": round(time.monotonic() - started, 2),
    }
    report["summary"] = summary(report)
    return report


def summary(report: dict[str, Any]) -> list[str]:
    c = report["counts"]
    out = [f"{c['candidates_attacked']} candidate(s) attacked: {c['all_survived']} ALL_SURVIVED, "
           f"{c['broken']} BROKEN, {c['unmeasured']} UNMEASURED",
           "  " + "; ".join(f"{a}: {v['SURVIVED']}S/{v['BROKEN']}B/{v['UNMEASURED']}U"
                            for a, v in report["per_attack"].items())]
    if report.get("stopped"):
        out.append(f"  stopped: {report['stopped']}")
    out.append(f"  registry evidence rows {c['registry_rows_written']}, "
               f"events {c['events_written']}"
               + (" (dry run: nothing recorded)" if report["dry_run"] else ""))
    for r in report["all_survived"][:8]:
        out.append(f"  ALL_SURVIVED {r['family']} on {r['symbol']} (t={r['baseline_t']})")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="attack a hypothesis before the gauntlet is charged")
    ap.add_argument("--once", action="store_true", help="one pass (the only mode)")
    ap.add_argument("--budget-s", type=float, default=BUDGET_S)
    ap.add_argument("--max-attacks", type=int, default=MAX_ATTACKS)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true",
                    help="measure and print; write nothing, record nothing")
    ap.add_argument("--out", default=str(REPORT))
    a = ap.parse_args(argv)

    report = build(max_attacks=int(a.max_attacks), budget_s=float(a.budget_s),
                   dry_run=bool(a.dry_run), seed=int(a.seed))
    for line in report["summary"]:
        print(line)
    if a.dry_run:
        print("dry run: nothing written")
        return 0
    _write(Path(a.out), report)
    print(f"  -> {a.out}")
    try:
        from libs.ops import events as ev
        ev.emit("LEG_DONE", leg=SOURCE, outcome="ok",
                attacked=report["counts"]["candidates_attacked"],
                all_survived=report["counts"]["all_survived"],
                broken=report["counts"]["broken"])
    except Exception:
        pass
    return 0


if __name__ == "__main__":                                              # pragma: no cover
    raise SystemExit(main())
