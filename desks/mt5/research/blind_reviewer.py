"""BLIND REVIEW -- a certificate is a claim; this reads it back off the tape with fresh eyes.

WHAT A CERTIFICATE IS, AND WHAT IT IS NOT. Ten gates passed means ten judges agreed about ONE
computation of one number. Every gate in `external_gauntlet` reads the same daily R series, built
by the same call from the same signals: if the family was called wrong, the inputs rebuilt wrong,
the cost charged wrong or the fill assumed wrong, all ten agree with each other about something
that was never a measurement of the market. `libs/validation/hostile.py` records what that class
costs -- an FVG cell at t = +9.0 that was a same-bar limit-fill ambiguity and went to t = -6.0 when
the line was fixed, invisible to every test that reads the R series because the R series was
faithfully reporting a fill nobody could have got. And until this organ, nothing on the desk took
a CERTIFIED cell back to the bars and asked whether the number comes back: the gauntlet mints, the
forward clock waits, the promoter enrols, and none of them re-derive.

WHAT THIS DOES, per certified cell, in order:

    1  reload `<SYMBOL>_<TF>.parquet` from the universe store (chart from the params, else H1 by
       absence -- `research/frontier_identity.timeframe_of`, the desk-wide spelling)
    2  call the family through the ONE call path the forward clock and the live executor share
       (`mt5desk.family_call.signals`, session filter included), with runtime inputs rebuilt by
       `mt5desk.family_inputs` -- the same reconstruction `build_cell` and the gateway use
    3  replay those signals through the desk's own engine and recompute n / expectancy / t / PF
    4  attack its own reproduction with the cheap hostile roster (`hostile.run_all` with an
       `evaluate` closure that redoes 2-3 on whatever bars it is handed)
    5  publish PASS / VETO / UNMEASURED with the reproduced numbers beside the certificate's

THE BLINDNESS IS STRUCTURAL, NOT A PROMISE. `load_certificates` is the only door from the registry
into this module and it hands downstream exactly two things: `shadow_spec` (what the code needs to
RUN -- symbol, family, params, selector, side, chart) and the certificate's NUMBERS. `_num`
refuses a string by construction, so no gate verdict text, no `message`, no mechanism note and no
hypothesis prose can reach a reviewer function even if a future row carries it: there is no
parameter to pass it through. Nothing here opens the docket, the seat outputs, the hypothesis
files or the gate `why` fields. The generator's story is read LAST and only as a `rationale_seen_
after` note beside a verdict that was already reached -- persuasion cannot move a number that was
computed before it arrived.

THE VERDICT RULE, deliberately coarse, because a reviewer that vetoes on a 10% disagreement is
measuring the two engines' cost models rather than the claim:

    VETO         the reproduced expectancy disagrees in SIGN with the certificate's, OR the
                 reproduced t is below half the certified t, OR the hostile roster BLOCKS
                 (`timestamp_permutation`, `delayed_entry`, a sign-flipped `subperiod_removal`,
                 `worst_year_removal` -- the four whose measured failure means the number is not
                 a measurement of the market)
    UNMEASURED   the bars, the family, the recorded parameters or the runtime inputs could not be
                 loaded, or the reproduction made fewer than three trades. Absence never resolves
                 to a clean verdict (L1.28a) and never to a veto either.
    PASS         measured, and none of the above fired.

SIGN IS THE ONLY MAGNITUDE-FREE COMPARISON THERE IS, which is why the sign rule leads. The
certificates on this desk record `expected_value.ev`, the mean of the DAILY R series; this
reviewer reproduces the mean of the PER-TRADE R series. Different numbers -- and the same total R
over a positive denominator, so their signs agree by construction. The certified t is read off the
row when one records it and is otherwise implied from the certificate's own daily Sharpe and day
count (`t = sharpe * sqrt(days)`, `sharpe_ratio` being mean/sd per period): a daily-series t and a
per-trade t are the same statistic asymptotically (total R over sd*sqrt(n)), and a half-t
threshold is wide enough to absorb the difference. The basis of every number travels with it.

WHAT IT MAY NOT DO. A VETO withholds a certificate from PROMOTION -- `research/promoter.py` reads
`latest_verdicts()` and refuses a LIVE row for a cell whose latest ledger verdict is VETO. It never
closes a position, resizes a sleeve, touches the heat floor or reaches an order path. That boundary
is growth governance, not caution: this organ withdraws nothing and sizes nothing, a vetoed cell is
UNPROVEN rather than refuted, and the answer to a veto is more evidence, never a smaller book
(GROWTH GOVERNANCE Rule 1). An UNMEASURED cell blocks nothing at all -- the promoter's own gates
already fail closed on absence, and vetoing on a missing parquet would be a risk reduction with no
measurement behind it.

BOUNDED BY CONSTRUCTION. `--max-cells` (12) per run, least-recently-reviewed first from the
append-only ledger, 120 s per cell, one bars frame resident at a time -- the box that runs this
also runs the live terminal and has 8 GB.

    python desks/mt5/research/blind_reviewer.py [--dry-run] [--max-cells N] [--cell KEY]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SURVIVORS = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
UNIVERSE = DESK / "data" / "universe"
LEDGER = DESK / "data" / "blind_review_ledger.jsonl"
OUT = DESK / "reports" / "BLIND_REVIEW.json"

PASS, VETO, UNMEASURED = "PASS", "VETO", "UNMEASURED"

#: Cells per run, and the wall clock one cell may cost. The hostile roster re-runs the strategy
#: ~35 times (20 permutations, three delays, five fifths, the years), so a cell is the unit that
#: has to be bounded rather than the run.
MAX_CELLS = 12
CELL_BUDGET_S = 120.0
#: Below this much of the budget left, the roster is not STARTED. Starting it and being cut off
#: mid-way would publish a partial adversary set as if it were the roster's finding.
HOSTILE_MIN_S = 20.0

#: `hostile`'s own floors, restated so this module refuses the same frames it does.
MIN_TRADES = 3
MIN_BARS = 60

#: Half. A reviewer that vetoes on a 10% gap is prosecuting two cost models, not a claim.
T_RATIO = 0.5

#: Every string this module is allowed to write ABOUT a certificate's numbers -- labels it wrote
#: itself, never a word the certificate wrote. The blindness is that no prose crosses.
STAT_BASES = frozenset({"recorded_per_trade_r", "gate_expected_value_daily_r",
                        "recorded", "implied_from_daily_sharpe"})

RULE = ("VETO when the reproduced expectancy disagrees in sign with the certificate's, or the "
        f"reproduced t is below {T_RATIO:g}x the certified t, or the hostile roster blocks. "
        "UNMEASURED when bars, family, parameters or inputs cannot be loaded, or the "
        f"reproduction made fewer than {MIN_TRADES} trades -- absence is never a clean verdict "
        "and never a veto. A VETO withholds a certificate from PROMOTION and touches nothing "
        "that is already live.")

#: The adversaries AND the one `t`. `hostile.stats_from_r` is the desk's single constructor for a
#: trade statistic, so this module computes none of its own: two implementations of one statistic
#: diverging silently is the defect this desk keeps paying for. Without it a cell is UNMEASURED.
try:
    from libs.validation import hostile as _hostile
except Exception:                                      # pragma: no cover - import environment
    _hostile = None                                    # type: ignore[assignment]


# ------------------------------------------------------------------------------ blind readers

def _num(x: Any) -> float | None:
    """A finite number, or None. A STRING IS NEVER PARSED: that refusal is the blindness."""
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        return None
    f = float(x)
    return f if math.isfinite(f) else None


def _first_num(row: Any, names: Sequence[str]) -> float | None:
    if not isinstance(row, dict):
        return None
    for name in names:
        v = _num(row.get(name))
        if v is not None:
            return v
    return None


def _gate_num(gates: dict[str, Any], gate: str, field_: str) -> float | None:
    g = gates.get(gate)
    return _num(g.get(field_)) if isinstance(g, dict) else None


def certified_spec(row: Any) -> dict[str, Any]:
    """The EXECUTABLE half of a certificate: `shadow_spec` and nothing else.

    `params` comes back None when the certificate never recorded one -- `certificate_hygiene`
    calls such a row UNRUNNABLE, and guessing the parameterisation that passed would review a
    strategy nobody certified.
    """
    spec = row.get("shadow_spec") if isinstance(row, dict) else None
    if not isinstance(spec, dict):
        return {}
    params = spec.get("params")
    params = dict(params) if isinstance(params, dict) else None
    side_txt = str(spec.get("side") or "LONG").upper()
    return {"symbol": str(spec.get("symbol") or ""), "family": str(spec.get("family") or ""),
            "params": params, "selector": spec.get("selector"),
            "side": -1 if side_txt.startswith("S") else 1,
            "timeframe": _timeframe_of(spec, params)}


def _timeframe_of(spec: dict[str, Any], params: dict[str, Any] | None) -> str:
    """The cell's chart, by the desk's own rule: its own, its params', else H1 by absence."""
    try:
        from research.frontier_identity import timeframe_of
        return str(timeframe_of({"timeframe": spec.get("timeframe"), "params": params or {}}))
    except Exception:                                  # pragma: no cover - import environment
        for src in (spec, params or {}):
            if isinstance(src, dict) and src.get("timeframe"):
                return str(src["timeframe"]).upper()
        return "H1"


def certified_stats(row: Any) -> dict[str, Any]:
    """The certificate's NUMBERS. Every value is a number, a count, or a label from STAT_BASES.

    No verdict text, no message, no mechanism note: `_num` cannot return a string, so the prose
    has no route into this dict and therefore none into anything downstream of it.
    """
    gates = row.get("gates") if isinstance(row, dict) else None
    gates = gates if isinstance(gates, dict) else {}
    days = _first_num(row, ("days", "n_days"))
    sharpe = _gate_num(gates, "in_sample_screen", "sharpe")
    out: dict[str, Any] = {
        "n": _first_num(row, ("n", "n_trades", "trades")),
        "days": days, "sharpe": sharpe,
        "pf": _first_num(row, ("pf", "profit_factor")),
        "gates_passed": sum(1 for g in gates.values()
                            if isinstance(g, dict) and g.get("passed") is True),
        "gates_total": len(gates),
    }
    exp = _first_num(row, ("expectancy", "mean_r", "exp_r"))
    if exp is not None:
        out["expectancy"], out["expectancy_basis"] = exp, "recorded_per_trade_r"
    else:
        ev = _gate_num(gates, "expected_value", "ev")
        out["expectancy"] = ev
        out["expectancy_basis"] = "gate_expected_value_daily_r" if ev is not None else None
    t = _first_num(row, ("t", "t_stat", "t_value"))
    if t is not None:
        out["t"], out["t_basis"] = t, "recorded"
    elif sharpe is not None and days is not None and days > 0:
        out["t"], out["t_basis"] = sharpe * math.sqrt(days), "implied_from_daily_sharpe"
    else:
        out["t"], out["t_basis"] = None, None
    return out


def load_certificates(path: Path | None = None) -> dict[str, tuple[dict, dict]]:
    """`<hunt>.<cell>` -> (spec, stats). THE ONLY DOOR from the registry into this module."""
    try:
        doc = json.loads((path or SURVIVORS).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    rows = doc.get("survivors") if isinstance(doc, dict) else None
    out: dict[str, tuple[dict, dict]] = {}
    for key, row in (rows or {}).items():
        if isinstance(row, dict):
            out[str(key)] = (certified_spec(row), certified_stats(row))
    return out


# ------------------------------------------------------------------------------- reproduction

def load_bars(symbol: str, timeframe: str, universe: Path | None = None) -> Any:
    """`<SYMBOL>_<TF>.parquet`, normalised onto ITS OWN bar clock; None when the chart is absent.

    `families._h1` is the desk's normaliser (tz-aware UTC, no silent resample of a finer chart);
    a tree without it falls back to the same two rules rather than to a different frame.
    """
    import pandas as pd
    pq = (universe or UNIVERSE) / f"{symbol}_{str(timeframe).upper()}.parquet"
    if not pq.exists():
        return None
    try:
        frame = pd.read_parquet(pq)
    except Exception:
        return None
    try:
        from mt5desk import families
        frame = families._h1(frame)
    except Exception:                                  # pragma: no cover - import environment
        if "time" in frame.columns:
            frame = frame.set_index("time")
        frame.index = pd.DatetimeIndex(frame.index)
        if frame.index.tz is None:
            frame.index = frame.index.tz_localize("UTC")
    if not isinstance(frame.index, pd.DatetimeIndex) or len(frame) == 0:
        return None
    return frame


def resolve_family(family: str) -> tuple[Any, str | None]:
    """(constructor, population) -- `executables.resolve_family`'s answer, never a second one."""
    try:
        from mt5desk import executables
        return executables.resolve_family(family), executables.population_of(family)
    except Exception:                                  # pragma: no cover - import environment
        return None, None


def call_params(spec: dict[str, Any], bars: Any) -> tuple[dict[str, Any] | None, str]:
    """The keyword params this cell is called with -- `family_inputs`, the gateway's own call."""
    params = spec.get("params")
    if not isinstance(params, dict):
        return None, "shadow_spec.params was never recorded; this certificate is unrunnable"
    try:
        from mt5desk.family_inputs import resolve, strip_identity_keys
    except Exception as exc:                           # pragma: no cover - import environment
        return None, f"family_inputs unavailable ({type(exc).__name__}: {exc})"
    try:
        call = strip_identity_keys(str(spec.get("family") or ""), params)
        extra, why = resolve(str(spec.get("symbol") or ""), str(spec.get("family") or ""),
                             params, bars)
    except Exception as exc:
        return None, f"input reconstruction raised ({type(exc).__name__}: {exc})"
    if extra is None:
        return None, f"runtime inputs unavailable: {why}"
    call.update(extra)
    return call, "ok"


def _costs_for(symbol: str, universe: Path | None = None) -> tuple[Any, str]:
    """The desk's own cost model for this symbol, and where its numbers came from."""
    try:
        from mt5desk.engine import Costs
    except Exception:                                  # pragma: no cover - import environment
        return None, "no_cost_model"
    try:
        meta = json.loads(((universe or UNIVERSE) / "universe.json").read_text(encoding="utf-8"))
        row = meta.get(symbol) if isinstance(meta, dict) else None
    except (OSError, ValueError):
        row = None
    if isinstance(row, dict):
        return Costs.from_symbol(row), "universe_registry"
    # NAMED, NOT HIDDEN: the defaults are gold's contract, so a symbol the registry does not know
    # is replayed almost cost-free -- which biases this reviewer toward agreement. Say so.
    return Costs.from_symbol({}), "engine_defaults"


def _cost_px(costs: Any) -> float:
    """Round-trip cost in PRICE units -- `engine.run_backtest`'s own `per_oz_roundtrip/contract`."""
    try:
        return float(costs.per_oz_roundtrip()) / float(costs.contract_oz)
    except Exception:
        return 0.0


def _engine_replay(frame: Any, sigs: list[Any], costs: Any) -> list[float]:
    from mt5desk.engine import run_backtest
    return [float(t.r_multiple) for t in run_backtest(frame, list(sigs), costs).trades]


def _replay2_replay(frame: Any, sigs: list[Any], costs: Any) -> list[float]:
    from libs.validation import replay2
    return [float(t.r) for t in replay2.replay(frame, list(sigs), cost_price_units=_cost_px(costs))]


def minimal_replay(frame: Any, sigs: list[Any], costs: Any) -> list[float]:
    """The contract hand-rolled, for a tree where neither engine imports: next-open entry,
    intrabar stop and target with the STOP assumed first, TTL exit at the next open, one position
    at a time, R against the distance to the stop. Labelled `minimal_replay` wherever it is used,
    because it models no trigger, no banking and no trail -- a breakout cell replayed here is a
    different trade from the one the certificate was earned on."""
    o = [float(x) for x in frame["open"]]
    hi = [float(x) for x in frame["high"]]
    lo = [float(x) for x in frame["low"]]
    at = {ts: i for i, ts in enumerate(frame.index)}
    cost, out, busy = _cost_px(costs), [], -1
    for s in sorted(sigs, key=lambda x: x.time):
        i = at.get(s.time)
        if i is None or i + 1 >= len(o) or i + 1 <= busy:
            continue
        j0, side = i + 1, int(s.side)
        entry, stop, target = o[j0], float(s.stop), float(s.target)
        risk = abs(entry - stop)
        if not (risk > 0) or not math.isfinite(risk):
            continue
        exit_i, exit_px = None, None
        for j in range(j0, min(j0 + max(1, int(s.ttl_bars)), len(o))):
            hit_stop = lo[j] <= stop if side > 0 else hi[j] >= stop
            hit_tgt = hi[j] >= target if side > 0 else lo[j] <= target
            if hit_stop or hit_tgt:
                exit_i, exit_px = j, (stop if hit_stop else target)
                break
        if exit_i is None or exit_px is None:
            exit_i = min(j0 + max(1, int(s.ttl_bars)), len(o) - 1)
            exit_px = o[exit_i]
        out.append(((exit_px - entry) * side - cost) / risk)
        busy = exit_i
    return [float(r) for r in out]


def replay_backend(prefer: str | None = None) -> tuple[str, Callable[[Any, list[Any], Any],
                                                                    list[float]]]:
    """Which replay reproduces this certificate, chosen ONCE and named in the record.

    `engine.run_backtest` leads: it minted every certificate on this desk and is the only replay
    that honours the whole `Signal` contract -- trigger, banking, trail, pyramid. `replay2` is the
    contract-written second engine and models none of those, so a breakout cell scored there
    disagrees with its certificate for a reason that is about the replay rather than about the
    claim -- exactly the false VETO this organ must not manufacture.
    """
    order: list[tuple[str, str, Callable[[Any, list[Any], Any], list[float]]]] = [
        ("engine.run_backtest", "mt5desk.engine", _engine_replay),
        ("replay2", "libs.validation.replay2", _replay2_replay),
    ]
    for name, module, fn in order:
        if prefer not in (None, name):
            continue
        try:
            __import__(module)
            return name, fn
        except Exception:                              # pragma: no cover - import environment
            continue
    return "minimal_replay", minimal_replay


def _profit_factor(rs: Sequence[float]) -> float | None:
    wins = sum(float(r) for r in rs if float(r) > 0)
    losses = -sum(float(r) for r in rs if float(r) < 0)
    return float(wins / losses) if losses > 0 else None


def make_evaluate(fn: Any, *, side: int, params: dict[str, Any], costs: Any,
                  replay: Callable[[Any, list[Any], Any], list[float]]) -> Callable[[Any], Any]:
    """`bars -> TradeStats`: steps 2 and 3, redone on whatever frame the caller hands in.

    This is the closure `hostile.run_all` injects into every adversary, which is what makes the
    roster an attack on the STRATEGY rather than on a return series it was given.
    """
    def evaluate(frame: Any) -> Any:
        from mt5desk.family_call import signals as family_signals
        sigs = family_signals(fn, frame, side=int(side), params=dict(params))
        return _hostile.stats_from_r(replay(frame, list(sigs), costs))
    return evaluate


# ------------------------------------------------------------------------------- the verdict

def judge(certified: dict[str, Any], reproduced: dict[str, Any],
          hostile: dict[str, Any]) -> tuple[str, list[str]]:
    """PASS / VETO / UNMEASURED, from numbers only. Pure, so the rule can be tested directly."""
    n = reproduced.get("n")
    exp, t = _num(reproduced.get("expectancy")), _num(reproduced.get("t"))
    if not isinstance(n, int) or n < MIN_TRADES or exp is None:
        return UNMEASURED, [f"the reproduction produced {n if n is not None else 0} trade(s); "
                            f"{MIN_TRADES} are needed before an expectancy or a t means anything"]
    why: list[str] = []
    c_exp = _num(certified.get("expectancy"))
    if c_exp is not None and c_exp != 0.0 and ((c_exp > 0) != (exp > 0)):
        why.append(f"expectancy disagrees in SIGN: certificate {c_exp:+.4f} "
                   f"({certified.get('expectancy_basis')}), reproduced {exp:+.4f} per-trade R "
                   f"on {n} trade(s)")
    c_t = _num(certified.get("t"))
    if c_t is not None and c_t > 0.0 and (t is None or t < T_RATIO * c_t):
        why.append(f"reproduced t={t if t is not None else float('nan'):.2f} is below "
                   f"{T_RATIO:g}x the certified t={c_t:.2f} ({certified.get('t_basis')})")
    if hostile.get("blocking") is True:
        why.append("the hostile roster BLOCKS: " + ", ".join(hostile.get("blocked_by") or []))
    if why:
        return VETO, why
    return PASS, [f"reproduced expectancy {exp:+.4f} per-trade R on {n} trade(s), t="
                  f"{t if t is not None else float('nan'):.2f}; the claim comes back"]


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _record(key: str, stats: dict[str, Any], verdict: str, why: list[str], *,
            reproduced: dict[str, Any] | None = None, hostile: dict[str, Any] | None = None,
            basis: str | None = None, seconds: float = 0.0,
            rationale: str | None = None) -> dict[str, Any]:
    row = {"at": _now(), "cell": key, "verdict": verdict, "why": why,
           "certified": dict(stats), "reproduced": reproduced or {},
           "hostile": hostile or {"status": UNMEASURED, "why": "not reached"},
           "basis": basis, "seconds": round(float(seconds), 2)}
    if rationale:
        # READ LAST, ON PURPOSE. The verdict above was computed before this string existed.
        row["rationale_seen_after"] = str(rationale)[:500]
    return row


def review_cell(key: str, spec: dict[str, Any], stats: dict[str, Any], *,
                budget_s: float = CELL_BUDGET_S, seed: int = 0, universe: Path | None = None,
                replay: str | None = None, rationale: str | None = None) -> dict[str, Any]:
    """One certified cell, reproduced from `spec` and judged against `stats`. Nothing else in."""
    t0 = time.monotonic()

    def done(verdict: str, why: list[str], **kw: Any) -> dict[str, Any]:
        return _record(key, stats, verdict, why, seconds=time.monotonic() - t0,
                       rationale=rationale, **kw)

    symbol, family = str(spec.get("symbol") or ""), str(spec.get("family") or "")
    if _hostile is None:                               # pragma: no cover - import environment
        return done(UNMEASURED, ["libs.validation.hostile is not importable; its `stats_from_r` "
                                 "is this desk's one trade statistic and nothing here fakes it"])
    if not symbol or not family:
        return done(UNMEASURED, ["the shadow_spec names no symbol or no family"])
    fn, population = resolve_family(family)
    if fn is None:
        return done(UNMEASURED, [f"no constructor for family {family!r} on this tree"])
    if population == "hunt16":
        return done(UNMEASURED, [f"{family!r} is a hunt16 family: its parameterisation lives in "
                                 "the sweep's WINDOWS/day-state, not in the certificate, so "
                                 "reproducing it here would review a lookalike strategy"])
    bars = load_bars(symbol, str(spec.get("timeframe") or "H1"), universe)
    if bars is None or len(bars) < MIN_BARS:
        return done(UNMEASURED, [f"{symbol}_{spec.get('timeframe')} bars unavailable or shorter "
                                 f"than {MIN_BARS} rows"])
    call, why = call_params(spec, bars)
    if call is None:
        return done(UNMEASURED, [why])
    costs, cost_basis = _costs_for(symbol, universe)
    name, backend = replay_backend(replay)
    evaluate = make_evaluate(fn, side=int(spec.get("side") or 1), params=call, costs=costs,
                             replay=backend)
    basis = f"{name}/{cost_basis}"
    try:
        real = evaluate(bars)
    except Exception as exc:
        return done(UNMEASURED, [f"the reproduction raised ({type(exc).__name__}: {exc})"],
                    basis=basis)
    rs = list(getattr(real, "per_trade_r", []) or [])
    reproduced = {"n": int(real.n), "expectancy": _num(real.expectancy),
                  "mean_r": _num(real.mean_r), "t": _num(real.t_stat), "pf": _profit_factor(rs),
                  "n_bars": len(bars), "cost_price_units": round(_cost_px(costs), 8)}
    if time.monotonic() - t0 > budget_s:
        return done(UNMEASURED, [f"budget: the reproduction alone took past {budget_s:g}s"],
                    reproduced=reproduced, basis=basis)
    hostile_out = _run_hostile(evaluate, bars, seed=seed,
                               remaining=budget_s - (time.monotonic() - t0))
    verdict, reasons = judge(stats, reproduced, hostile_out)
    return done(verdict, reasons, reproduced=reproduced, hostile=hostile_out, basis=basis)


def _run_hostile(evaluate: Callable[[Any], Any], bars: Any, *, seed: int,
                 remaining: float) -> dict[str, Any]:
    """The cheap roster, summarised.

    THE BUDGET GATES THE START, NOT THE ROSTER: `run_all` is one call and is not interruptible, so
    a cell that begins it finishes it. Measured on XAUUSD H1 (50,255 bars, 2,117 trades) the
    reproduction costs ~2 s and the roster ~50-90 s, which is why the floor below refuses to open
    a roster on the last seconds of a budget rather than pretending it can stop one.
    """
    if _hostile is None:                               # pragma: no cover - import environment
        return {"status": UNMEASURED, "why": "libs.validation.hostile is not importable"}
    if remaining < HOSTILE_MIN_S:
        return {"status": UNMEASURED, "why": f"budget: {remaining:.0f}s left, the roster is not "
                                             f"started under {HOSTILE_MIN_S:g}s"}
    try:
        report = _hostile.run_all(evaluate, bars, seed=int(seed))
    except Exception as exc:
        return {"status": UNMEASURED, "why": f"the roster raised ({type(exc).__name__}: {exc})"}
    return {"status": "MEASURED", "blocking": bool(report.blocking),
            "blocked_by": list(report.blocked_by), "n_passed": report.n_passed,
            "n_failed": report.n_failed, "n_unmeasured": report.n_unmeasured,
            "tests": {v.name: ("UNMEASURED" if v.passed is None else
                               ("PASS" if v.passed else "FAIL")) for v in report.verdicts}}


# ----------------------------------------------------------------------------------- ledger

def ledger_rows(path: Path | None = None) -> list[dict[str, Any]]:
    """Every recorded review, oldest first. An unreadable line is skipped, never guessed at."""
    p = path or LEDGER
    try:
        text = p.read_text(encoding="utf-8")
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("cell"):
            out.append(row)
    return out


def latest_verdicts(ledger_path: Path | None = None) -> dict[str, str]:
    """`cell -> the latest recorded verdict`. THE CONSUMER CONTRACT.

    `research/promoter.py` reads this and refuses to write a LIVE row for a cell whose latest
    verdict is VETO. Latest by ledger ORDER, which is append order: a cell reviewed again after a
    veto is governed by the newer reading, so a veto is reversible by evidence and by nothing
    else. A cell absent from the ledger is absent from this mapping -- never reported as PASS,
    because "not reviewed" is not a verdict (L1.28a).
    """
    return {str(r["cell"]): str(r.get("verdict") or UNMEASURED)
            for r in ledger_rows(ledger_path)}


def append_ledger(rows: Sequence[dict[str, Any]], path: Path | None = None) -> int:
    p = path or LEDGER
    if not rows:
        return 0
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, default=str) + "\n")
    return len(rows)


def order_cells(keys: Sequence[str], ledger_path: Path | None = None) -> list[str]:
    """Least-recently-reviewed first; never reviewed leads, ties broken by name for determinism."""
    last: dict[str, str] = {}
    for row in ledger_rows(ledger_path):
        last[str(row["cell"])] = str(row.get("at") or "")
    return sorted(keys, key=lambda k: (k in last, last.get(k, ""), k))


def _write_atomic(path: Path, payload: dict[str, Any]) -> None:
    """Atomic where the filesystem allows it; `os.replace` onto a read-only file is WinError 5."""
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, indent=1, default=str)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(body, encoding="utf-8")
    for attempt in range(2):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt or not path.exists():
                break
            try:
                os.chmod(path, 0o666)
            except OSError:
                break
        except OSError:
            break
    path.write_text(body, encoding="utf-8")


# -------------------------------------------------------------------------------------- run

def build(*, max_cells: int = MAX_CELLS, cell: str | None = None, survivors: Path | None = None,
          ledger: Path | None = None, universe: Path | None = None,
          budget_s: float = CELL_BUDGET_S, seed: int = 0,
          replay: str | None = None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Review this run's cells and return (artifact, ledger rows). Writes nothing."""
    certs = load_certificates(survivors)
    keys = ([cell] if cell is not None
            else order_cells(list(certs), ledger)[:max(0, int(max_cells))])
    rows: list[dict[str, Any]] = []
    for key in keys:
        entry = certs.get(key)
        if entry is None:
            rows.append(_record(key, {}, UNMEASURED,
                                ["the survivors registry holds no certificate of that key"]))
            continue
        spec, stats = entry
        rows.append(review_cell(key, spec, stats, budget_s=budget_s, seed=seed,
                                universe=universe, replay=replay))
    seen = set(latest_verdicts(ledger)) | {str(r["cell"]) for r in rows}
    reviewed_ever = len(seen & set(certs))
    doc = {
        "at": _now(),
        "n_reviewed": len(rows),
        "n_pass": sum(1 for r in rows if r["verdict"] == PASS),
        "n_veto": sum(1 for r in rows if r["verdict"] == VETO),
        "n_unmeasured": sum(1 for r in rows if r["verdict"] == UNMEASURED),
        "vetoed": [{"cell": r["cell"], "why": r["why"]} for r in rows if r["verdict"] == VETO],
        "reviewed": rows,
        "coverage": {"certified": len(certs), "reviewed_ever": reviewed_ever,
                     "never_reviewed": len(certs) - reviewed_ever},
        "rule": RULE,
    }
    return doc, rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Blind re-review of certified cells.")
    ap.add_argument("--max-cells", type=int, default=MAX_CELLS,
                    help=f"cells per run, least-recently-reviewed first (default {MAX_CELLS})")
    ap.add_argument("--cell", default=None, help="review one certificate key and stop")
    ap.add_argument("--budget", type=float, default=CELL_BUDGET_S,
                    help=f"seconds per cell (default {CELL_BUDGET_S:g})")
    ap.add_argument("--seed", type=int, default=0, help="hostile roster seed")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the verdicts; write neither the artifact nor the ledger")
    a = ap.parse_args(argv)
    doc, rows = build(max_cells=a.max_cells, cell=a.cell, budget_s=a.budget, seed=a.seed)
    print(f"blind review: {doc['n_reviewed']} cell(s) -- {doc['n_pass']} PASS, "
          f"{doc['n_veto']} VETO, {doc['n_unmeasured']} UNMEASURED  "
          f"[coverage {doc['coverage']['reviewed_ever']}/{doc['coverage']['certified']}, "
          f"{doc['coverage']['never_reviewed']} never reviewed]")
    for r in rows:
        rep, cert = r.get("reproduced") or {}, r.get("certified") or {}
        print(f"  {r['verdict']:<10} {r['cell'][:52]:<52} "
              f"cert exp={cert.get('expectancy')} t={_fmt(cert.get('t'))} | "
              f"repro n={rep.get('n')} exp={_fmt(rep.get('expectancy'), 4)} "
              f"t={_fmt(rep.get('t'))} [{r.get('basis')}] {r['seconds']:.1f}s")
        for line in r.get("why") or []:
            print(f"             - {line}")
    if a.dry_run:
        print("-> dry run: nothing written")
        return 0
    append_ledger(rows)
    _write_atomic(OUT, doc)
    print(f"-> {OUT}")
    print(f"-> {LEDGER} (+{len(rows)} row(s))")
    return 0


def _fmt(x: Any, places: int = 2) -> str:
    v = _num(x)
    return "-" if v is None else f"{v:.{places}f}"


if __name__ == "__main__":
    raise SystemExit(main())
