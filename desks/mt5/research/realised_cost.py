"""WHAT EACH ACCOUNT ACTUALLY PAYS TO TRADE EACH SYMBOL -- realised execution cost, per fill.

THE GAP (2026-11-03). The allocator's execution cost was a MODEL: `libs/portfolio/execution_cost`
prices a sleeve at its fill hour off `data/cost_surface.json`, a spread x hour surface built from
bars. `fill_recorder` had been writing what every order really paid -- the price asked, the price
got, the spread at that instant, the commission -- into `data/fill_corpus.jsonl` since 2026-09-23,
and nothing turned those fills into a cost the allocator could read. The model was never checked
against the venue, and the venue's answer never reached capital.

WHAT THIS ORGAN PUBLISHES, per ACCOUNT x SYMBOL (and x UTC decision hour where a bucket holds
`MIN_HOUR_N` fills), never pooled across accounts:

    n fills                       FILLED corpus rows of that book and symbol, one per execution
    slip                          (fill - asked) x direction, worse > 0: fraction of price and R
    spread paid                   the spread at decision as a fraction of price -- a round trip
                                  crosses it once (half on entry, half on exit)
    commission                    the venue's charge as a fraction of notional and in R (cost > 0)
    total round-trip cost         slip + spread + commission, fraction of price and R -- MEASURED
                                  only on a fill that carries all three; a missing component is
                                  never a zero
    latency                       decision -> send and send -> ack, ms
    shrink                        the realised mean and its weight w = n / (n + SHRINK_K). The
                                  realised mean is WINSORIZED (each fill clipped at the cell's
                                  own p5/p95, p10/p90 under 20 fills) so one extreme fill cannot
                                  set the cost; the raw mean is published beside it

MEASURED AGAINST WHAT THE REPLAY CHARGED, PER FILL (Auditor HOLD on e8c6a11af / 59ae9ea7c). A
realised cost is only a credit or a debit against the cost the sleeve's R ALREADY carries, and that
is not `BASE_COST_R` nor the surface's `BASE_COST_R x ratio` -- both rest on an unmeasured scalar.
It is what `external_gauntlet` charged: its own `costs_for(sym, meta)` -- the POOLED median spread
from TODAY's registry (median_spread_pts x tick_size) plus the replay's commission -- as
`per_oz_roundtrip() / contract_oz` in price, divided by the trade's own stop distance -- exactly
the term `engine.run_backtest` subtracts from each trade's R. So per fill this report records

    replay_charged_cost_r   the gauntlet's pooled charge for that symbol, in R of this stop
    diff_r                  realised total_cost_r - replay_charged_cost_r (dearer > 0)

and per account x symbol `vs_replay`: the winsorized mean of diff_r and the charged mean. That
cell is MEASURED only when it holds `MIN_DIFF_N` fills AND every counted fill carries both terms;
otherwise it is UNMEASURED with the reason, and the allocator keeps its modelled bias.

UNMEASURED IS A VERDICT (L1.28a). An account with no fills, or a cell whose fills carry no total
cost, is UNMEASURED with the reason -- never a zero cost and never "cheap".

TWO-SIDED BY CONSTRUCTION. Realised cost can sit above OR below the model; the allocator applies
both directions (GROWTH_GOVERNANCE Rule 2: a venue that fills cheaper than modelled earns capital).
The part of the evidence the shrinkage withholds is published by the allocator, both directions,
and carried into MISSED_GROWTH.json by `missed_growth.realised_cost_lines`.

READ ONLY. It reads the corpus and writes one report; it sizes, routes and vetoes nothing.

    python desks/mt5/research/realised_cost.py --once
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.execution import fill_corpus as fc  # noqa: E402
from libs.portfolio.execution_cost import REALISED_K, REALISED_MIN_N  # noqa: E402

CORPUS = DESK / "data" / "fill_corpus.jsonl"
FILL_REPORT = DESK / "reports" / "FILL_RECORDER.json"
OUT = DESK / "reports" / "REALISED_COST.json"
UNIVERSE = DESK / "data" / "universe" / "universe.json"
SCHEMA = "realised-cost/2"

#: The empirical-Bayes prior strength, in fills: at n = K a cell's realised mean and the model
#: weigh equally. Declared here and in `execution_cost.REALISED_K` (one constant, imported).
SHRINK_K = REALISED_K
#: Fills an hour bucket needs before it is published (a bucket of two is a quote, not a cost).
MIN_HOUR_N = 5
#: Fills a cell needs before its winsorizing clip widens from p10/p90 to p5/p95.
WINSOR_FULL_N = 20
#: Fills a cell needs before its realised-minus-replay difference is MEASURED: one favourable
#: slip must not produce a credit. One constant, shared with `execution_cost.apply_realised`.
MIN_DIFF_N = REALISED_MIN_N
BOOKS: tuple[str, ...] = ("fusion", "e8", "ftmo")
UNMEASURED = "UNMEASURED"
MEASURED = "MEASURED"


def _f(x: Any) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def book_of(row: dict[str, Any]) -> str | None:
    """Which account a corpus row belongs to, on POSITIVE evidence only.

    `fill_recorder` stamps `book` since 2026-11-03; rows written before carry it implicitly --
    an `e8|` / `ftmo|` intent or record id is a prop lane's, and a row whose sources are the
    Fusion gateway's own ledgers is Fusion's. Anything else (the execution twin's rows, which
    duplicate the recorder's fills without a ledger join) is UNATTRIBUTED and is counted, never
    folded into an account."""
    b = str(row.get("book") or "").strip().lower()
    if b in BOOKS:
        return b
    for key in ("record_id", "intent_id"):
        v = str(row.get(key) or "")
        for book in ("e8", "ftmo"):
            if v.startswith(f"{book}|"):
                return book
    src = set(row.get("sources") or [])
    if src & {"e8_intents.jsonl"}:
        return "e8"
    if src & {"order_intents.jsonl", "live_ledger.jsonl"}:
        return "fusion"
    return None


def fill_cost(row: dict[str, Any]) -> dict[str, float | None]:
    """One fill's friction. Signs: cost > 0. MT5 books commission NEGATIVE, so its cost is
    -commission; a rebate is a negative cost and stays one."""
    slip_frac, slip_r = _f(row.get("slip_frac")), _f(row.get("slip_r"))
    spread_frac = _f(row.get("spread_frac_at_decision"))
    stop_frac = _f(row.get("stop_frac"))
    if stop_frac is not None and stop_frac <= 0:
        stop_frac = None
    comm_r = _f(row.get("commission_r"))
    comm_cost_r = (-comm_r) if comm_r is not None else None
    comm_frac = (comm_cost_r * stop_frac) if (comm_cost_r is not None and stop_frac) else None
    spread_r = (spread_frac / stop_frac) if (spread_frac is not None and stop_frac) else None
    total_frac = (slip_frac + spread_frac + comm_frac
                  if (slip_frac is not None and spread_frac is not None
                      and comm_frac is not None) else None)
    total_r = (slip_r + spread_r + comm_cost_r
               if (slip_r is not None and spread_r is not None
                   and comm_cost_r is not None) else None)
    return {"slip_frac": slip_frac, "slip_r": slip_r, "spread_frac": spread_frac,
            "spread_r": spread_r, "commission_frac": comm_frac, "commission_r": comm_cost_r,
            "total_cost_frac": total_frac, "total_cost_r": total_r,
            "latency_decision_to_send_ms": _f(row.get("latency_decision_to_send_ms")),
            "latency_send_to_ack_ms": _f(row.get("latency_send_to_ack_ms"))}


#: (replay_charged_cost_r or None, basis or the reason it could not be priced), per fill row.
Pricer = Callable[[dict[str, Any]], tuple[float | None, str]]


def replay_charged_cost_r(row: dict[str, Any], costs: Any) -> float | None:
    """The R the replay charged this trade: `engine.run_backtest` subtracts
    `costs.per_oz_roundtrip() / costs.contract_oz` (price units) over the trade's own
    `|entry - stop|`. The fill's stop distance is `stop_frac x fill_price`, the same denominator
    `fill_cost` reads every realised term in. None without a positive stop and fill."""
    fill, stop_frac = _f(row.get("fill_price")), _f(row.get("stop_frac"))
    if fill is None or fill <= 0 or stop_frac is None or stop_frac <= 0:
        return None
    try:
        per_price = float(costs.per_oz_roundtrip()) / float(costs.contract_oz)
    except (AttributeError, TypeError, ValueError, ZeroDivisionError):
        return None
    v = per_price / (stop_frac * fill)
    return v if math.isfinite(v) else None


def _unpriced(why: str) -> Pricer:
    def price(_row: dict[str, Any]) -> tuple[float | None, str]:
        return None, why
    return price


def gauntlet_pricer(meta: dict[str, Any] | None = None, eg: Any = None) -> Pricer:
    """Per fill, the cost `external_gauntlet` charged that symbol, in R of the fill's own stop.

    THE POOLED CHARGE, REPRODUCED BY IMPORT, NEVER BY COPY. The replay a sleeve's R came from was
    charged at the POOLED median spread (`execution_cost`'s own docstring: the surface ratio is
    "spread at hour / the pooled spread the replay actually charged"), which is the gauntlet's
    `costs_for(sym, meta)` = `Costs.from_symbol(meta[sym])`: TODAY's registry
    `median_spread_pts x tick_size x contract_size` plus two `commission_per_lot` sides carried
    into price by `quote_per_account`. In R that is

        replay_charged_cost_r = (median_spread_pts x tick_size + commission in price) / |entry-stop|

    -- the spread over the stop plus the replay's commission in R, the exact term
    `engine.run_backtest` subtracts. An unimportable gauntlet or an unreadable registry prices
    nothing, and says so (UNMEASURED by name, never a zero)."""
    try:
        if eg is None:
            sp = str(DESK / "scripts")
            if sp not in sys.path:
                sys.path.insert(0, sp)
            import external_gauntlet as eg  # type: ignore[import-not-found,no-redef,unused-ignore]
        charge = eg.costs_for
    except Exception as exc:
        return _unpriced(f"UNMEASURED: external_gauntlet unimportable "
                         f"({type(exc).__name__}: {str(exc)[:120]})")
    if meta is None:
        try:
            meta = json.loads(UNIVERSE.read_text("utf-8"))
        except (OSError, ValueError) as exc:
            return _unpriced(f"UNMEASURED: universe.json unreadable ({type(exc).__name__})")
    if not isinstance(meta, dict):
        return _unpriced("UNMEASURED: universe.json is not a symbol map")
    reg: dict[str, Any] = meta

    def price(row: dict[str, Any]) -> tuple[float | None, str]:
        sym = str(row.get("symbol") or "")
        row_meta = reg.get(sym)
        if not isinstance(row_meta, dict):
            return None, f"UNMEASURED: {sym or '?'} is not in the registry the gauntlet prices off"
        if not isinstance(row_meta.get("median_spread_pts"), (int, float)) \
                or not float(row_meta.get("tick_size") or 0.0) > 0:
            return None, f"UNMEASURED: {sym} carries no pooled median_spread_pts x tick_size"
        try:
            costs = charge(sym, reg)
        except Exception as exc:
            return None, f"UNMEASURED: gauntlet costs_for raised {type(exc).__name__}"
        r = replay_charged_cost_r(row, costs)
        if r is None:
            return None, "UNMEASURED: no stop geometry (fill_price x stop_frac) to express it in R"
        return r, "external_gauntlet.costs_for: pooled median spread + commission"

    return price


def latest_fills(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """The FILLED executions, one row each, with their book. The corpus keeps the LAST row per
    key; an open market order recorded off the venue's answer (`intent_fill`) and the same
    order joined to its closed deal later are ONE fill, so a fill is keyed by (book, intent) --
    or (book, deal) when no intent survived -- and the joined row wins."""
    last: dict[str, dict[str, Any]] = {}
    for r in rows:
        last[fc.record_from_row(r).key] = r
    census = {"corpus_rows": len(rows), "keys": len(last), "filled": 0, "unattributed": 0,
              "duplicates_collapsed": 0}
    best: dict[tuple[str, str], dict[str, Any]] = {}
    for r in last.values():
        if str(r.get("status") or "") != "FILLED":
            continue
        census["filled"] += 1
        book = book_of(r)
        if book is None:
            census["unattributed"] += 1
            continue
        iid = str(r.get("intent_id") or "")
        k = (book, f"i:{iid}" if iid else f"d:{r.get('deal')}|{r.get('record_id')}")
        prev = best.get(k)
        if prev is not None:
            census["duplicates_collapsed"] += 1
            joined_prev = (prev.get("join_keys") or {}).get("basis") != "intent_fill"
            if joined_prev:
                continue
        best[k] = {**r, "_book": book}
    return list(best.values()), census


def _stats(xs: list[float]) -> dict[str, Any]:
    if not xs:
        return {"n": 0, "mean": None, "median": None, "p90": None, "status": UNMEASURED}
    s = sorted(xs)
    n = len(s)
    med = s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])
    p90 = s[min(n - 1, max(0, math.ceil(0.9 * n) - 1))]
    return {"n": n, "mean": round(sum(s) / n, 8), "median": round(med, 8),
            "p90": round(p90, 8), "status": MEASURED}


def _hour(row: dict[str, Any]) -> int | None:
    stamp = str(row.get("decided_at") or row.get("sent_at") or "")
    if not stamp:
        return None
    try:
        t = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    t = t if t.tzinfo else t.replace(tzinfo=UTC)
    return t.astimezone(UTC).hour


def _rank(s: list[float], q: float) -> float:
    """Nearest-rank quantile of a sorted list (the same rule `_stats` uses for p90)."""
    return s[min(len(s) - 1, max(0, math.ceil(q * len(s)) - 1))]


def winsorized_mean(xs: list[float], what: str = "total_cost_r") -> tuple[float | None, str]:
    """(mean of xs clipped at their own quantiles, the method). p5/p95 from WINSOR_FULL_N fills,
    p10/p90 below it -- a thin cell clips harder because one outlier is a larger share of it.
    The clip bounds come from the cell itself, never from another account or a constant."""
    if not xs:
        return None, "none: no fill carries a whole round-trip cost"
    s = sorted(xs)
    lo_q, hi_q = (0.05, 0.95) if len(s) >= WINSOR_FULL_N else (0.10, 0.90)
    lo, hi = _rank(s, lo_q), _rank(s, hi_q)
    clipped = [min(max(x, lo), hi) for x in s]
    return (sum(clipped) / len(clipped),
            f"winsorized mean: each fill's {what} clipped at this cell's own "
            f"p{round(lo_q * 100)}/p{round(hi_q * 100)} (nearest rank, n={len(s)}; "
            f"p5/p95 from n>={WINSOR_FULL_N})")


def shrink(mean: float | None, n: int, prior: float, k: float = SHRINK_K
           ) -> tuple[float | None, float]:
    """(w x mean + (1 - w) x prior, w) with w = n / (n + k). None mean -> the prior stands, w 0."""
    if mean is None or n <= 0:
        return None, 0.0
    w = n / (n + float(k))
    return w * float(mean) + (1.0 - w) * float(prior), w


def vs_replay(costs: list[dict[str, Any]], charged: list[tuple[float | None, str]],
              fills: list[dict[str, Any]]) -> dict[str, Any]:
    """The cell's realised-minus-replay-charged difference, MEASURED or UNMEASURED with why.

    COUNTED fills are those carrying a whole realised round trip. The cell is MEASURED only when
    it counts `MIN_DIFF_N` of them AND every one also carries the replay's charge -- a cell where
    some fills could not be priced by the gauntlet is not a partial measurement, it is a sample
    selected by what could be priced, so it stays UNMEASURED and the modelled bias stands."""
    per_fill: list[dict[str, Any]] = []
    diffs: list[float] = []
    charged_xs: list[float] = []
    realised_xs: list[float] = []
    n_counted = n_missing = 0
    reasons: dict[str, int] = {}
    for r, c, (ch, basis) in zip(fills, costs, charged, strict=True):
        tot = c["total_cost_r"]
        if tot is None:
            continue
        n_counted += 1
        d = (float(tot) - float(ch)) if ch is not None else None
        per_fill.append({"record_id": r.get("record_id"), "realised_cost_r": round(tot, 8),
                         "replay_charged_cost_r": (round(ch, 8) if ch is not None else None),
                         "diff_r": (round(d, 8) if d is not None else None),
                         "replay_basis": basis})
        if ch is None or d is None:
            n_missing += 1
            reasons[basis] = reasons.get(basis, 0) + 1
            continue
        diffs.append(d)
        charged_xs.append(float(ch))
        realised_xs.append(float(tot))
    dmean, method = winsorized_mean(diffs, "diff_r")
    out: dict[str, Any] = {
        "n": len(diffs), "n_counted": n_counted, "n_unpriced_by_replay": n_missing,
        "min_n": MIN_DIFF_N,
        "diff_mean_r": (round(dmean, 8) if dmean is not None else None),
        "raw_diff_mean_r": (round(sum(diffs) / len(diffs), 8) if diffs else None),
        "diff_method": method,
        "charged_mean_r": (round(sum(charged_xs) / len(charged_xs), 8) if charged_xs else None),
        "realised_mean_r": (round(sum(realised_xs) / len(realised_xs), 8)
                            if realised_xs else None),
        "fills": per_fill,
        "rule": ("diff_r = realised total_cost_r - replay_charged_cost_r per fill, both over the "
                 "trade's own stop distance; replay_charged_cost_r is external_gauntlet's "
                 "Costs for the symbol at the fill's broker hour (per_oz_roundtrip/contract_oz "
                 "over |entry - stop|, the term engine.run_backtest subtracts)")}
    if n_counted == 0:
        out["status"] = UNMEASURED
        out["why"] = "UNMEASURED: no fill carries a whole realised round-trip cost"
    elif n_missing:
        out["status"] = UNMEASURED
        out["why"] = (f"UNMEASURED: {n_missing} of {n_counted} counted fill(s) carry no "
                      f"replay-charged cost ({'; '.join(sorted(reasons))}); a difference over "
                      "the priceable subset is not the cell's")
    elif n_counted < MIN_DIFF_N:
        out["status"] = UNMEASURED
        out["why"] = (f"UNMEASURED: {n_counted} fill(s) < the {MIN_DIFF_N}-fill floor; one "
                      "favourable slip must not produce a credit")
    else:
        out["status"], out["why"] = MEASURED, ""
    return out


def cell(fills: list[dict[str, Any]], pricer: Pricer | None = None) -> dict[str, Any]:
    costs = [fill_cost(r) for r in fills]
    price = pricer or _unpriced("UNMEASURED: no replay pricer supplied")
    charged = [price(r) for r in fills]
    col = {k: [c[k] for c in costs if c[k] is not None] for k in costs[0]} if costs else {}
    out: dict[str, Any] = {"n_fills": len(fills)}
    for k in ("slip_frac", "slip_r", "spread_frac", "commission_frac", "commission_r",
              "total_cost_frac", "total_cost_r", "latency_decision_to_send_ms",
              "latency_send_to_ack_ms"):
        out[k] = _stats([float(x) for x in col.get(k, []) if x is not None])
    tot = out["total_cost_r"]
    wmean, method = winsorized_mean([float(x) for x in col.get("total_cost_r", [])
                                     if x is not None])
    n_tot = int(tot["n"])
    w = (n_tot / (n_tot + float(SHRINK_K))) if (wmean is not None and n_tot > 0) else 0.0
    out["shrink"] = {"n": n_tot, "k": SHRINK_K, "weight": round(w, 6),
                     # one 4,000-point fill must not set a cell's cost, so each fill is clipped
                     # at the cell's own quantiles first
                     "realised_mean_cost_r": (round(wmean, 8) if wmean is not None else None),
                     "raw_mean_cost_r": tot["mean"], "mean_method": method,
                     "baseline": ("vs_replay: the allocator shrinks the realised-minus-replay-"
                                  "charged difference toward its modelled bias "
                                  "(execution_cost.apply_realised); UNMEASURED there, no bias")}
    out["vs_replay"] = vs_replay(costs, charged, fills)
    out["status"] = MEASURED if tot["n"] else UNMEASURED
    if not tot["n"]:
        missing = [k for k in ("slip_r", "spread_frac", "commission_r")
                   if not out[k]["n"]]
        out["why"] = (f"{len(fills)} fill(s), none carrying slip, spread and commission "
                      f"together (absent here: {', '.join(missing) or 'stop geometry'}); a "
                      "missing component is not a zero cost")
    hours: dict[str, dict[str, Any]] = {}
    by_h: dict[int, list[dict[str, Any]]] = {}
    for r, c in zip(fills, costs, strict=True):
        h = _hour(r)
        if h is not None and c["total_cost_r"] is not None:
            by_h.setdefault(h, []).append(c)
    for h, cs in sorted(by_h.items()):
        if len(cs) < MIN_HOUR_N:
            continue
        hours[f"{h:02d}"] = {
            "n": len(cs),
            "total_cost_r": _stats([float(c["total_cost_r"] or 0.0) for c in cs]),
            "total_cost_frac": _stats([float(c["total_cost_frac"]) for c in cs
                                       if c["total_cost_frac"] is not None])}
    out["hours_utc"] = hours
    return out


def build(rows: list[dict[str, Any]] | None = None, *, fill_report: dict[str, Any] | None = None,
          now: datetime | None = None, pricer: Pricer | None = None) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    rows = fc.read_rows(CORPUS) if rows is None else rows
    fills, census = latest_fills(rows)
    if pricer is None and fills:
        pricer = gauntlet_pricer()
    accounts: dict[str, Any] = {}
    n_cells = n_measured = n_vs_replay = 0
    for book in BOOKS:
        mine = [r for r in fills if r["_book"] == book]
        if not mine:
            accounts[book] = {"status": UNMEASURED, "n_fills": 0, "symbols": {},
                              "why": f"no FILLED corpus row belongs to the {book} book on this "
                                     "host: its realised cost is unknown, not zero"}
            continue
        by_sym: dict[str, list[dict[str, Any]]] = {}
        for r in mine:
            by_sym.setdefault(str(r.get("symbol") or "?"), []).append(r)
        syms = {s: cell(v, pricer) for s, v in sorted(by_sym.items())}
        n_cells += len(syms)
        meas = [s for s, c in syms.items() if c["status"] == MEASURED]
        n_measured += len(meas)
        n_vs_replay += sum(1 for c in syms.values() if c["vs_replay"]["status"] == MEASURED)
        accounts[book] = {"status": MEASURED if meas else UNMEASURED, "n_fills": len(mine),
                          "n_symbols": len(syms), "n_symbols_measured": len(meas),
                          "symbols": syms}
    fr = fill_report
    if fr is None:
        try:
            fr = json.loads(FILL_REPORT.read_text("utf-8"))
        except (OSError, ValueError):
            fr = None
    upstream = (fr or {}).get("realised_fills") if isinstance(fr, dict) else None
    status = MEASURED if n_measured else UNMEASURED
    return {
        "schema": SCHEMA, "measured_at": now.isoformat(timespec="seconds"),
        "status": status,
        "why": ("" if n_measured else
                "no account x symbol cell carries a fill with slip, spread and commission all "
                "measured: the allocator keeps the modelled cost everywhere"),
        "n_fills_used": len(fills), "n_cells": n_cells, "n_cells_measured": n_measured,
        "n_cells_vs_replay_measured": n_vs_replay, "min_diff_n": MIN_DIFF_N,
        "upstream_realised_fills": upstream,
        "corpus_census": census, "accounts": accounts,
        "shrink_k": SHRINK_K, "min_hour_n": MIN_HOUR_N,
        "missed_growth_source": ("pf_allocation.json execution_cost_realised.missed_growth: the "
                                 "withheld share of (diff_mean - modelled bias), both ways"),
        "units": {"*_frac": "fraction of price (cost > 0)",
                  "*_r": "R per trade: the position's own |entry - stop| (cost > 0)",
                  "diff_r": "realised total_cost_r - replay_charged_cost_r (dearer > 0)",
                  "hours_utc": "UTC hour of the decision"},
        "consumers": ["libs/portfolio/execution_cost.apply_realised via "
                      "pf_allocator._execution_costs (cost_bias_r = w x vs_replay.diff_mean_r + "
                      "(1 - w) x modelled bias, per account x symbol, only where vs_replay is "
                      "MEASURED; stale > 48h falls back)",
                      "research/missed_growth.realised_cost_lines (realised_execution_cost, "
                      "via pf_allocation.json)",
                      "research/health_board (RED when stale, or zero cells while fills flow)"],
        "boundary": "READ ONLY: reads the fill corpus, writes this report; sizes nothing.",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    doc = build()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    tmp = a.out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    tmp.replace(a.out)
    print(f"realised_cost: {doc['status']} -- {doc['n_cells_measured']}/{doc['n_cells']} "
          f"account x symbol cells measured ({doc['n_cells_vs_replay_measured']} against the "
          f"replay's own charge) from {doc['n_fills_used']} fill(s) -> {a.out}")
    for book, blk in doc["accounts"].items():
        print(f"  {book:<7} {blk['status']:<10} fills {blk['n_fills']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
