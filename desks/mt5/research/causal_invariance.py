"""INVARIANCE ACROSS ENVIRONMENTS -- the one causal property that changes what gets tested first.

THE GAP THE LEDGER NAMED (Tier-1 B16): *"a causal label changes nothing on the promotion path;
no invariance-across-environments test."* `causal_discovery.py` orients edges between INSTRUMENTS
and `world_causal_graph.py` maps drivers onto them, and both are read by reports. Neither asks the
question a causal claim is actually FOR, which Peters/Buhlmann/Meinshausen put plainly: a causal
relationship is one whose coefficient does not change when the environment does. A correlation
that is a different number in Asia than in London, or in 2023 than in 2025, was never a mechanism
-- it was a fit to whichever environment happened to dominate the sample.

WHAT IS MEASURED, PER CELL. A cell is (symbol, family, params) -- the same identity the gauntlet,
the forward clock and the gateway use. Its EFFECT in an environment is the mean signed forward
log return over the family's own holding horizon at every signal the family fired in that
environment. Three environment axes, all of them exogenous to the rule:

    session   Asia / London / NY / off-hours, by the bar's own UTC hour
    year      the calendar year of the bar
    regime    volatility tercile of the trailing realised range, measured on the SAME series so
              the split exists on any instrument without a regime artifact having to be present

THE STATISTIC AND ITS NULL. The observed dispersion is the signal-count-weighted variance of the
per-environment effects around the pooled effect. That number alone means nothing -- a cell with
few signals per environment has a large dispersion by construction -- so it is compared against
its own permutation null: the environment labels are shuffled among the SAME per-signal effects
`N_PERM` times, and the null is the dispersion that shuffling produces. The p-value is the share
of permutations whose dispersion is at least the observed one.

    p_excess large    the effect moves no more across environments than random relabelling moves
                      it -> INVARIANT
    p_excess small    the effect moves MORE than chance -> NON_INVARIANT: the cell is an
                      environment-specific fit, and the environment it was fitted to is named
    too few signals   UNMEASURED, which is a verdict and never a pass (L1.28a)

SIGN STABILITY IS REPORTED SEPARATELY AND BINDS SEPARATELY, because an effect whose MAGNITUDE
wanders is a sizing problem and an effect whose SIGN flips is a different strategy in each
environment. A cell agreeing with its own pooled sign in fewer than `SIGN_MIN` of its
environments is NON_INVARIANT whatever the permutation test says.

WHAT IT CHANGES, AND WHAT IT DELIBERATELY DOES NOT. The verdict rides the candidate at INTAKE:
`miner_candidate_compiler.expand_axes` reads it and DEPRIORITISES a non-invariant cell -- it
sorts later in the queue, it is never dropped. That is the only shape this gate may take under
the principal's never-reduce-aggressiveness order: a refusal would destroy candidates on a
statistic computed from the desk's own past, and the desk has been wrong about that before
(L1.25). The cost of the delay is billed like every other rail, in
`research/missed_growth.py::measure_causal_invariance` against the `causal_invariance` entry in
`libs/portfolio/rails.py` -- GROWTH_GOVERNANCE requires a missed-growth line for any new refusal,
and a deprioritisation is a refusal measured in hours rather than in candidates.

NOTHING HERE TOUCHES THE SEALED JUDGE. `external_gauntlet.py`, `promoter.py`,
`allocator_proof.py` and `state_admission.py` are not read, not imported and not modified; the
ten gates decide exactly what they decided before (L1.60: no screen may apply a threshold of its
own). This changes the ORDER work is done in and publishes a field beside the certificate. It
does not move a bar.

    python desks/mt5/research/causal_invariance.py --once --budget-s 600
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(DESK / "mt5desk"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

UNI = DESK / "data" / "universe"
SLEEVES = DESK / "data" / "sleeves.json"
SURVIVORS = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
OUT = DESK / "reports" / "CAUSAL_INVARIANCE.json"

#: Signals a cell needs before any verdict is possible, and per environment before that
#: environment counts as one. Below these the dispersion is noise and the honest answer is
#: UNMEASURED -- a cell that fired nine times is not invariant and is not non-invariant.
MIN_SIGNALS = 30
MIN_PER_ENV = 6
MIN_ENVS = 3
#: Permutations of the environment labels. 400 puts the resolution of the p-value at 1/401,
#: which is finer than the 0.05 the verdict turns on, and costs milliseconds per cell.
N_PERM = 400
ALPHA = 0.05
#: Share of a cell's environments that must agree with its pooled sign. Two thirds: a cell whose
#: sign flips in more than a third of the environments it trades in is two strategies.
SIGN_MIN = 2.0 / 3.0
#: Bars read per symbol. The year axis needs several years to exist at all.
BARS = 40_000

SESSIONS = (("asia", 0, 8), ("london", 8, 13), ("ny", 13, 21), ("late", 21, 24))


def _read(p: Path) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def cell_key(symbol: str, family: str, params: dict[str, Any] | None = None) -> str:
    """The cell's identity, stable across runs and independent of dict ordering."""
    blob = json.dumps(params or {}, sort_keys=True, default=str)
    h = hashlib.sha256(blob.encode("utf-8")).hexdigest()[:8]
    return f"{symbol}|{family}|{h}"


def _bars(symbol: str) -> Any:
    try:
        import pandas as pd
    except ImportError:
        return None
    p = UNI / f"{symbol}_H1.parquet"
    if not p.exists():
        return None
    try:
        df = pd.read_parquet(p).tail(BARS)
    except (OSError, ValueError):
        return None
    return df if "close" in df.columns and len(df) > 500 else None


def _env_labels(times: list[Any], df: Any) -> dict[str, list[str]]:
    """Three environment labels per signal time: session, year, volatility regime.

    The regime axis is measured off the SAME series rather than read from a regime artifact, so
    a cell on an instrument the regime monitor has never looked at still gets a third axis. The
    terciles are computed over the whole window, which makes them a property of the instrument's
    history and not of the cell's signals."""
    import numpy as np
    import pandas as pd

    rng = (df["high"].astype(float) - df["low"].astype(float)) \
        if {"high", "low"} <= set(df.columns) else df["close"].astype(float).diff().abs()
    vol = rng.rolling(48, min_periods=12).mean()
    finite = vol.dropna()
    if len(finite) < 100:
        lo = hi = float("nan")
    else:
        lo, hi = float(np.nanquantile(finite, 1 / 3)), float(np.nanquantile(finite, 2 / 3))

    idx = df.index
    pos = {t: i for i, t in enumerate(idx)}
    out: dict[str, list[str]] = {"session": [], "year": [], "regime": []}
    for t in times:
        ts = pd.Timestamp(t)
        hour = int(ts.hour)
        sess = next((n for n, a, b in SESSIONS if a <= hour < b), "late")
        out["session"].append(sess)
        out["year"].append(str(ts.year))
        i = pos.get(t)
        v = float(vol.iloc[i]) if (i is not None and i < len(vol)) else float("nan")
        if math.isnan(v) or math.isnan(lo):
            out["regime"].append("unknown")
        else:
            out["regime"].append("calm" if v <= lo else ("storm" if v >= hi else "normal"))
    return out


def _effects(symbol: str, family: str, params: dict[str, Any],
             side: int) -> tuple[list[float], list[Any], str]:
    """(signed forward log return per signal, signal times, why it is empty).

    The effect is the family's OWN horizon: `Signal.ttl_bars` when the family declares one, and
    the desk's default hold otherwise. Signed by the signal's side, so a short that made money
    is a positive effect and the sign of the pooled effect is the sign of the edge."""
    df = _bars(symbol)
    if df is None:
        return [], [], f"no usable {symbol}_H1 bars"
    try:
        import numpy as np
        from mt5desk import executables, family_call
    except ImportError as exc:
        return [], [], f"desk modules unavailable: {exc}"
    fn = executables.resolve_family(family)
    if fn is None:
        return [], [], f"no code on this tree answers to family {family!r}"
    try:
        sigs = family_call.signals(fn, df, side=side, params=dict(params or {}))
    except Exception as exc:
        return [], [], f"{family} raised on {symbol}: {type(exc).__name__}: {exc}"
    if not sigs:
        return [], [], f"{family} fired no signal on {symbol}"
    close = np.log(df["close"].astype(float).to_numpy())
    pos = {t: i for i, t in enumerate(df.index)}
    eff: list[float] = []
    times: list[Any] = []
    for s in sigs:
        t = getattr(s, "time", None)
        i = pos.get(t)
        if i is None:
            continue
        ttl = int(getattr(s, "ttl_bars", 0) or 0) or 12
        j = min(i + ttl, len(close) - 1)
        if j <= i:
            continue
        sd = int(getattr(s, "side", side) or side)
        eff.append(float((close[j] - close[i]) * (1.0 if sd > 0 else -1.0)))
        times.append(t)
    return eff, times, "" if eff else f"{family} on {symbol}: no signal landed on a readable bar"


def _dispersion(eff: list[float], labels: list[str]) -> tuple[float, dict[str, dict[str, float]]]:
    """Signal-count-weighted variance of the per-environment means around the pooled mean."""
    groups: dict[str, list[float]] = {}
    for e, lab in zip(eff, labels, strict=False):
        groups.setdefault(lab, []).append(e)
    keep = {k: v for k, v in groups.items() if len(v) >= MIN_PER_ENV}
    if len(keep) < MIN_ENVS:
        return float("nan"), {}
    n = sum(len(v) for v in keep.values())
    pooled = sum(sum(v) for v in keep.values()) / n
    d = sum(len(v) * (sum(v) / len(v) - pooled) ** 2 for v in keep.values()) / n
    detail = {k: {"n": len(v), "effect": sum(v) / len(v)} for k, v in keep.items()}
    return d, detail


def invariance(eff: list[float], labels: list[str], *, seed: int = 0,
               n_perm: int = N_PERM) -> dict[str, Any]:
    """The test on ONE environment axis: dispersion, its permutation null, and sign stability."""
    d, detail = _dispersion(eff, labels)
    if math.isnan(d):
        return {"status": "UNMEASURED", "n_env": len(detail),
                "why": (f"fewer than {MIN_ENVS} environments carry {MIN_PER_ENV}+ signals on "
                        f"this axis")}
    rnd = random.Random(seed)  # noqa: S311 -- a permutation null, not a key
    shuffled = list(labels)
    hits = 0
    for _ in range(n_perm):
        rnd.shuffle(shuffled)
        dp, _det = _dispersion(eff, shuffled)
        if not math.isnan(dp) and dp >= d:
            hits += 1
    p_excess = (hits + 1) / (n_perm + 1)
    pooled = sum(eff) / len(eff)
    sgn = 1.0 if pooled >= 0 else -1.0
    agree = sum(1 for v in detail.values() if (v["effect"] >= 0) == (sgn >= 0))
    sign_stability = agree / len(detail)
    return {
        "status": "OK",
        "dispersion": round(d, 12),
        "p_excess": round(p_excess, 5),
        "pooled_effect": round(pooled, 8),
        "sign_stability": round(sign_stability, 4),
        "n_env": len(detail),
        "n_signals": len(eff),
        "environments": {k: {"n": v["n"], "effect": round(v["effect"], 8)}
                         for k, v in sorted(detail.items())},
        "invariant": bool(p_excess >= ALPHA and sign_stability >= SIGN_MIN),
        "why": (f"per-environment effects vary {'no more' if p_excess >= ALPHA else 'MORE'} than "
                f"random relabelling (p_excess {p_excess:.3f} vs alpha {ALPHA}); "
                f"{agree}/{len(detail)} environments agree with the pooled sign"),
    }


def judge_cell(symbol: str, family: str, params: dict[str, Any], side: int = 1, *,
               seed: int = 0) -> dict[str, Any]:
    """The cell's verdict across all three axes. NON_INVARIANT if ANY axis says so."""
    key = cell_key(symbol, family, params)
    eff, times, why = _effects(symbol, family, params, side)
    base = {"cell": key, "symbol": symbol, "family": family, "params": params,
            "side": "LONG" if side > 0 else "SHORT"}
    if len(eff) < MIN_SIGNALS:
        return {**base, "verdict": "UNMEASURED", "n_signals": len(eff),
                "why": why or (f"{len(eff)} signal(s); {MIN_SIGNALS} are needed before an "
                               f"environment split means anything")}
    df = _bars(symbol)
    axes = _env_labels(times, df)
    per_axis = {ax: invariance(eff, labs, seed=seed) for ax, labs in axes.items()}
    measured = [a for a, r in per_axis.items() if r.get("status") == "OK"]
    if not measured:
        return {**base, "verdict": "UNMEASURED", "n_signals": len(eff), "axes": per_axis,
                "why": "no environment axis carries enough signals to split on"}
    broken = [a for a in measured if not per_axis[a].get("invariant")]
    verdict = "NON_INVARIANT" if broken else "INVARIANT"
    return {
        **base, "verdict": verdict, "n_signals": len(eff), "axes": per_axis,
        "measured_axes": measured, "broken_axes": broken,
        "why": (f"the effect is stable across {', '.join(measured)}" if not broken else
                f"the effect changes with {', '.join(broken)}: "
                + "; ".join(f"{a} {per_axis[a]['why']}" for a in broken)),
    }


def _cells() -> list[tuple[str, str, dict[str, Any], int]]:
    """Every cell worth judging: the live roster first, then the certified canon.

    The roster first because a non-invariant LIVE sleeve is the expensive kind -- it is the one
    holding capital -- and the canon after because those are the cells the compiler's
    deprioritisation will actually re-order."""
    out: list[tuple[str, str, dict[str, Any], int]] = []
    seen: set[str] = set()

    def _add(sym: str, fam: str, params: dict[str, Any], side: int) -> None:
        if not sym or not fam:
            return
        k = cell_key(sym, fam, params)
        if k not in seen:
            seen.add(k)
            out.append((sym, fam, params, side))

    doc = _read(SLEEVES)
    rows = doc if isinstance(doc, list) else ((doc or {}).get("sleeves") or [])
    for r in rows:
        if not isinstance(r, dict) or str(r.get("status", "")).upper() != "LIVE":
            continue
        params = {k: r[k] for k in ("timeframe", "session", "stop_atr", "target_atr", "max_hold")
                  if r.get(k) is not None}
        _add(str(r.get("symbol") or ""), str(r.get("family") or ""), params,
             -1 if str(r.get("direction", "")).upper() == "SHORT" else 1)

    sdoc = _read(SURVIVORS) or {}
    for _k, v in (sdoc.get("survivors") or {}).items():
        spec = v.get("shadow_spec") if isinstance(v, dict) else None
        if not isinstance(spec, dict):
            continue
        params = {k: spec[k] for k in ("selector", "condition") if spec.get(k)}
        _add(str(spec.get("symbol") or ""), str(spec.get("family") or ""), params,
             -1 if str(spec.get("side", "")).upper() == "SHORT" else 1)
    return out


def verdict_for(symbol: str, family: str) -> dict[str, Any] | None:
    """The published verdict for (symbol, family), or None when nothing has judged it.

    THE CONSUMER'S DOOR. `miner_candidate_compiler.expand_axes` calls exactly this, keyed on the
    pair rather than the full cell, because the compiler is expanding a MECHANISM onto charts and
    sessions and the invariance question is about the mechanism. None is UNMEASURED and changes
    nothing -- absence is never a demotion."""
    doc = _read(OUT)
    if not isinstance(doc, dict):
        return None
    by_pair = doc.get("by_pair")
    if isinstance(by_pair, dict):
        row = by_pair.get(f"{symbol}|{family}")
        return row if isinstance(row, dict) else None
    return None


def build(budget_s: float = 600.0, *, seed: int = 0) -> dict[str, Any]:
    started = time.monotonic()
    cells = _cells()
    rows: list[dict[str, Any]] = []
    for sym, fam, params, side in cells:
        if time.monotonic() - started > budget_s:
            break
        try:
            rows.append(judge_cell(sym, fam, params, side, seed=seed))
        except Exception as exc:                               # a bad cell never stops the pass
            rows.append({"cell": cell_key(sym, fam, params), "symbol": sym, "family": fam,
                         "verdict": "UNMEASURED",
                         "why": f"{type(exc).__name__}: {exc}"})
    counts: dict[str, int] = {}
    for r in rows:
        counts[str(r["verdict"])] = counts.get(str(r["verdict"]), 0) + 1
    # THE PAIR INDEX IS WHAT THE COMPILER READS. A pair judged in several cells takes the
    # WORST verdict it earned anywhere: a mechanism that is environment-specific on one of its
    # instruments is environment-specific, and letting the best cell speak for the pair would
    # turn the test into a search for the environment that agrees with it.
    rank = {"NON_INVARIANT": 2, "UNMEASURED": 1, "INVARIANT": 0}
    by_pair: dict[str, dict[str, Any]] = {}
    for r in rows:
        key = f"{r.get('symbol')}|{r.get('family')}"
        prev = by_pair.get(key)
        if prev is None or rank.get(str(r["verdict"]), 0) > rank.get(str(prev["verdict"]), 0):
            by_pair[key] = {"verdict": r["verdict"], "cell": r.get("cell"),
                            "broken_axes": r.get("broken_axes") or [],
                            "why": str(r.get("why"))[:240]}
    return {
        "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "status": "OK" if rows else "UNMEASURED",
        "n_cells": len(rows), "n_offered": len(cells), "counts": counts,
        "alpha": ALPHA, "n_perm": N_PERM, "sign_min": round(SIGN_MIN, 4),
        "min_signals": MIN_SIGNALS, "min_per_env": MIN_PER_ENV, "min_envs": MIN_ENVS,
        "axes": ["session", "year", "regime"],
        "cells": rows,
        "by_pair": by_pair,
        "consumers": [
            "desks/mt5/research/miner_candidate_compiler.py expand_axes -> a NON_INVARIANT pair's"
            " cells sort LATER (priority + 1) and carry `causal_invariance`; nothing is dropped",
            "desks/mt5/research/forward_reconcile.py -> the verdict is published beside each "
            "certificate's forward row",
            "desks/mt5/research/missed_growth.py measure_causal_invariance -> the delay this gate "
            "causes is billed in forward log-wealth against libs/portfolio/rails.py "
            "`causal_invariance`",
        ],
        "boundary": (
            "THE SEALED JUDGE IS NOT TOUCHED. The ten gates decide exactly what they decided "
            "before; this changes the ORDER cells are tested in and publishes a field. No cell is "
            "ever refused on this statistic (principal's never-reduce-aggressiveness order), and "
            "L1.60 forbids a screen applying a threshold of its own in either direction."),
        "why": ("a causal claim is one whose coefficient does not change when the environment "
                "does. Until this ran, the desk's causal organs oriented edges between "
                "instruments and nothing asked whether a CELL's effect survived a change of "
                "session, year or volatility regime -- which is the only causal question that "
                "predicts whether the edge will still be there next quarter."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=600.0)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(argv)
    doc = build(budget_s=a.budget_s, seed=a.seed)
    try:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    except OSError as exc:
        print(f"causal invariance: could not write {OUT}: {exc}")
        return 1
    c = doc["counts"]
    print(f"causal invariance: {doc['n_cells']} of {doc['n_offered']} cell(s) judged -- "
          + ", ".join(f"{k} {v}" for k, v in sorted(c.items())))
    for r in doc["cells"]:
        if r["verdict"] == "NON_INVARIANT":
            print(f"  NON_INVARIANT {r['symbol']:<9} {r['family']:<28} "
                  f"breaks on {', '.join(r.get('broken_axes') or [])}")
    print(f"  {len(doc['by_pair'])} (symbol, family) pair(s) indexed for the compiler's intake")
    print(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
