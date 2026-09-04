"""What every proposer shares, so three sweeps do not carry three copies of one screen.

A PROPOSER runs a family over the desk's own bars, scores what it finds against the round trip,
deflates by everything it looked at, and donates the survivors into the miner-discovery contract
-- from which `miner_candidate_compiler` admits them as EXACT_RECIPE and the ordinary gauntlet
takes over. `factor_residual_engine` established the pattern; this is that pattern's screen and
donation step, lifted out so `plumbing_miner` and `transition_alpha` cannot drift from it.

THE SCREEN IS NOT THE GAUNTLET. It measures signals' forward returns at the family's own holding
period, net of cost, on non-overlapping trades. It exists to keep the gauntlet from being handed
hundreds of cells at a fixed 597-trial charge; the ten gates are unchanged and remain the only
thing that certifies.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
UNI = _DESK / "data" / "universe"
INTEL = _DESK / "data" / "intelligence"

#: Independent trades a cell needs before its mean is a number rather than an anecdote.
MIN_TRADES = 30
#: Deflated-t bar for PROPOSING. A proposer's threshold, not a gate.
PROPOSE_T = 2.0


def bars(sym: str) -> pd.DataFrame | None:
    path = UNI / f"{sym}_H1.parquet"
    if not path.exists():
        return None
    try:
        df = pd.read_parquet(path)
    except (OSError, ValueError, ImportError):
        return None
    if df.empty or "close" not in df.columns:
        return None
    df.index = pd.DatetimeIndex(pd.to_datetime(df.index, utc=True, errors="coerce"))
    return df[~df.index.isna()]


def universe_meta() -> dict:
    try:
        return json.loads((UNI / "universe.json").read_text("utf-8"))
    except (OSError, ValueError):
        return {}


def cost_frac(sym: str, meta: dict, close: pd.Series) -> float | None:
    """Round trip as a fraction of price, from the desk's corrected cost model."""
    from mt5desk.engine import Costs

    row = meta.get(sym)
    if not isinstance(row, dict):
        return None
    try:
        costs = Costs.from_symbol(row, mult=2.0)
        px = float(close.iloc[-1])
        if not math.isfinite(px) or px <= 0:
            return None
        return float((costs.per_oz_roundtrip() / costs.contract_oz) / px)
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return None


#: |t| of the previous-close-to-open gap, by stamp hour, above which that hour's OPEN is a
#: marking artifact rather than a price. No real market gaps the same direction every day at
#: t = 11; a bar that does is being marked (a swap adjustment, a session re-open print) and no
#: fill is available there at that price.
ARTIFACT_T = 5.0
#: Above this the hour is a MARKED price -- the broker's rollover print (EURUSD hour 0 at
#: t = -11.2, GBPUSD at -17.5) -- and no trade may hold across it, because the close on one side
#: and the open on the other are two different prices for the same instant. Between ARTIFACT_T
#: and this the hour is a systematic but modest gap (XAUUSD hour 9 at -5.4: the London-open
#: spread widening) whose cost the cost model carries; fills THERE are refused, trades ACROSS it
#: are not. Without the split every gold trade longer than a few hours crossed hour 9 and the
#: transition-alpha sweep proposed nothing for the wrong reason.
SEVERE_T = 10.0
#: Bars a fill may wait for a clean open when the signal's own fill bar is an artifact hour.
#: Two, because the reopen and the mark are adjacent hours on this feed; a signal that cannot
#: fill within two bars of firing is refused rather than filled late.
MAX_FILL_DELAY = 2


def artifact_hours(d: pd.DataFrame) -> dict[int, float]:
    """Stamp hours whose OPEN is systematically off the previous close -- unfillable prices.

    FOUND BY THE PLUMBING MINER ON ITS FIRST RUN, not designed in. EURUSD at broker hour 0: the
    open gaps -1.72bp from the prior close (t = -11.2) and the bar closes +1.09bp (t = +10.7);
    hour 1 continues +1.48bp (t = +11.9). That is the broker's rollover mark on the bid and its
    reversion, printed into the bars. A screen that fills at the next open bought that mark at
    t = 17 and the shuffled control proposed seven such cells, because a return shuffle leaves
    open-to-close structure inside each bar untouched.

    Measured per frame rather than hardcoded to hour 0: the mark lands wherever this broker's
    settlement lands, and a different feed would put it elsewhere.
    """
    if len(d) < 24 * 60:
        return {}
    gap = np.log(d["open"].astype(float) / d["close"].astype(float).shift(1))
    out: dict[int, float] = {}
    for h, s in gap.groupby(d.index.hour):
        s = s.dropna()
        if s.size < 100:
            continue
        sd = float(s.std(ddof=1))
        if sd <= 0:
            continue
        t = float(s.mean() / (sd / math.sqrt(s.size)))
        if abs(t) >= ARTIFACT_T:
            out[int(h)] = round(t, 2)
    # THE BAR AFTER A DAILY TRADING GAP IS A REOPEN, NOT A PRICE. A 23-hour contract (gold on this
    # offering) has one hour a day with no bar; the first bar after it opens on whatever the
    # reference market did in the gap. Its open is fillable but its "return" from the prior
    # close is the gap, and a cell that enters into or out of it is trading the reopen. Hours that
    # systematically follow a missing bar are refused on the same footing as marked opens.
    step = pd.Series(d.index[1:]) - pd.Series(d.index[:-1])
    after_gap = pd.Series(d.index[1:].hour)[step > pd.Timedelta(hours=1)]
    if after_gap.size >= 100:
        for h, n in after_gap.value_counts().items():
            if n >= 0.5 * (len(d) / 24):
                out.setdefault(int(h), float("nan"))
    return out


def screen(d: pd.DataFrame, signals: Sequence[Any], cost: float,
           unfillable: dict[int, float] | None = None) -> dict[str, Any] | None:
    """Forward return of each signal at its own TTL, net of cost, on non-overlapping trades.

    Entry is the OPEN of the bar after the signal, as the engine fills it. A signal inside a live
    trade's window is skipped, because the single-position engine could not have taken it. A
    signal whose fill bar opens at an artifact hour (see `artifact_hours`) is skipped too, and
    the count of such refusals is reported: a cell that only pays when filled at a marked price
    is not a cell.
    """
    if not signals:
        return None
    idx = d.index
    o = d["open"].astype(float).to_numpy()
    c = d["close"].astype(float).to_numpy()
    hours = idx.hour
    bad = set(unfillable or {})
    # MARKED OPENS VERSUS THE DAILY REOPEN, told apart by the map's own value. A finite t is a
    # marked price (the rollover print) and stays refused as before. NaN is the bar after the
    # daily trading gap: its open is a real, fillable price, but it is printed on the bid with
    # the reopen's wide spread -- measured 2026-09-04 on XAUUSD hour 1: gap t = +0.99 (unsigned,
    # so NOT a mark), yet open-to-close t = +5.6 on the bid as the spread normalises. A screen
    # that fills at that open books the spread reversion as edge, so a FILL there is still
    # refused. HOLDING THROUGH it is not: the gap is genuine exposure a position holder carries
    # in both directions, and treating it as a window breach had made every hold of a day or
    # more unscreenable on a 23-hour instrument -- the style-premia and tail sweeps reported
    # zero tests on gold for that reason alone, which is timidity by accident, not a gate.
    reopen = {h for h, t in (unfillable or {}).items()
              if t is None or not math.isfinite(float(t))}
    pos = {ts: i for i, ts in enumerate(idx)}
    pnl: list[float] = []
    last_exit = -1
    refused = 0
    delayed = 0
    for s in sorted(signals, key=lambda x: x.time):
        i = pos.get(s.time)
        if i is None or i + 1 >= len(o):
            continue
        entry = i + 1
        if entry <= last_exit:
            continue
        # A FILL AT THE REOPEN WAITS FOR THE NEXT CLEAN OPEN, at most MAX_FILL_DELAY bars, as a
        # pending order the desk declines to place into the reopen spread would. Only the reopen
        # earns the wait: a MARKED open (finite t) stays refused outright, because the mark and
        # its reversion sit in the adjacent hours and a late fill there is still inside the
        # artifact. The delay is counted so a cell that only pays when filled late is visible.
        moved = 0
        while (int(hours[entry]) in reopen and moved < MAX_FILL_DELAY
               and entry + 1 < len(o)):
            entry += 1
            moved += 1
        if int(hours[entry]) in bad:
            refused += 1
            continue
        delayed += int(moved > 0)
        # NOR MAY THE HOLDING WINDOW CROSS ONE. A trade entered at 22:00 and exited at the 23:00
        # close, on a feed whose 00:00 open is marked down 1.7bp, is harvesting the elevated
        # close before the mark -- the artifact by another route. Measured: after refusing only
        # artifact-hour FILLS, "short into hour 23" survived at t = +9.4 and the relabelled
        # control proposed as many cells as the real run. Any trade whose window contains an
        # artifact-hour open is refused, entry and exit alike.
        exit_ = min(entry + max(1, int(s.ttl_bars)), len(c) - 1)
        severe = {h for h, t in (unfillable or {}).items()
                  if (t is not None and math.isfinite(float(t)) and abs(float(t)) >= SEVERE_T)}
        if severe and any(int(hours[k]) in severe for k in range(entry + 1, exit_ + 1)):
            refused += 1
            continue
        # EXITING ON THE REOPEN BAR IS TRADING THE REOPEN: the close of that bar is where the
        # reopen spread finishes normalising, so a one-bar hold into it books the artifact.
        if reopen and int(hours[exit_]) in reopen and exit_ - entry <= 1:
            refused += 1
            continue
        if o[entry] <= 0:
            continue
        r = math.log(c[exit_] / o[entry]) * int(s.side)
        if not math.isfinite(r):
            continue
        pnl.append(r)
        last_exit = exit_
    if len(pnl) < MIN_TRADES:
        return None
    arr = np.asarray(pnl, dtype=float)
    sd = float(arr.std(ddof=1))
    if not math.isfinite(sd) or sd <= 0:
        return None
    gross = float(arr.mean())
    return {"n_independent": int(arr.size), "gross_per_trade": round(gross, 8),
            "net_per_trade": round(gross - cost, 8), "cost_frac": round(cost, 8),
            "t_gross": round(gross / (sd / math.sqrt(arr.size)), 3),
            "clears_cost": bool(gross > cost), "refused_unfillable": int(refused),
            "delayed_fills": int(delayed)}


def deflate(rows: list[dict]) -> list[dict]:
    """Charge every row for the whole sweep and mark the ones that clear it."""
    from research.multiplicity import deflate_t

    n = len(rows)
    # THE LIFETIME CHARGE, reported beside the sweep's own. The gate policy charges a fixed
    # trial count downstream; this makes the desk's whole history of the family visible on the
    # row so the winner's-curse shrinkage in the allocator can take the larger number.
    try:
        from libs.research.experiment_ledger import family_trials
    except Exception:
        def family_trials(_f: str) -> int:                       # type: ignore[misc]
            return 0
    for r in rows:
        r["n_tests_sweep"] = n
        r["t_deflated_sweep"] = round(deflate_t(float(r["t_gross"]), n), 3)
        fam = str(r.get("cell", "")).split(".")[1] if "." in str(r.get("cell", "")) else ""
        life = family_trials(fam) if fam else 0
        r["n_tests_lifetime"] = int(n + life)
        r["t_deflated_lifetime"] = round(deflate_t(float(r["t_gross"]), n + life), 3)
        r["proposed"] = bool(r.get("clears_cost") and r["t_deflated_sweep"] > PROPOSE_T
                             and int(r.get("n_independent", 0)) >= MIN_TRADES)
    return rows


def best_per_cell(rows: list[dict]) -> list[dict]:
    """One proposal per cell: shipping every variant of one winner smuggles the search back in."""
    best: dict[str, dict] = {}
    for r in sorted((x for x in rows if x.get("proposed")),
                    key=lambda x: -x["t_deflated_sweep"]):
        best.setdefault(str(r["cell"]), r)
    return sorted(best.values(), key=lambda x: -x["t_deflated_sweep"])


def candidate(source: str, symbol: str, family: str, params: dict, mechanism: str,
              title: str, evidence: dict) -> dict:
    return {"source": source, "kind": source, "symbol": symbol, "family": family,
            "params": params, "mechanism": mechanism, "title": title, "url": "",
            "evidence": {**evidence, "screen": "family signals, forward return at own TTL, "
                                                "net of round trip, non-overlapping, "
                                                "self-deflated"}}


def donate(source: str, candidates: list[dict], tests_run: int) -> Path | None:
    """Write the discovery contract. A control run must NEVER call this."""
    if not candidates:
        return None
    # POINT-IN-TIME BY CONSTRUCTION. Every proposer row leaves here carrying available_time,
    # ingested_time, source_version and a payload hash, so a joiner can refuse it for any
    # decision earlier than the desk could have known it. The stamp is applied in the one place
    # rows are written rather than by each proposer remembering to.
    try:
        from libs.data.pit import stamp as _pit_stamp
        candidates = [_pit_stamp(c, source) for c in candidates]
    except Exception:
        pass
    # PRE-REGISTERED BEFORE THE VERDICT. Each candidate's hypothesis card -- mechanism,
    # direction, variables, universe, horizon, parameters allowed, acceptance criterion,
    # falsifier -- is hashed and appended to the pre-registration ledger, and the hash rides on
    # the candidate. A verdict that later names a different card is a reinterpretation.
    try:
        from libs.research.preregistration import from_candidate, register
        for c in candidates:
            c.setdefault("prereg_hash", register(from_candidate(c), source=source))
    except Exception:
        pass
    out = INTEL / source
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M")
    path = out / f"discoveries_{stamp}.json"
    path.write_text(json.dumps({"source": source,
                                "generated_at": datetime.now(tz=UTC).isoformat(),
                                "tests_run": tests_run, "discoveries": candidates},
                               indent=1, default=str), "utf-8")
    return path


def identity(symbol: str, family: str, params: dict) -> str:
    return hashlib.sha256(json.dumps({"symbol": symbol, "family": family, "params": params},
                                     sort_keys=True, default=str).encode()).hexdigest()[:16]
