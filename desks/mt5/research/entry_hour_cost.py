"""ENTRY-HOUR COST: every gate and every forward clock charges the spread of the hour it TRADES.

THE DEFECT, measured 2026-10-13 on the desk's own artifacts. `universe.json` carries ONE
`median_spread_pts` per symbol and `Costs.from_symbol` charged it at every fill. The gauntlet
priced a cell at its single MODAL fill hour (and its 3x stress arm at the POOLED scalar again),
and every forward clock (`shadow_forward.per_symbol_costs`) priced every trade at the pooled
scalar. On the exotic crosses the broker-00 rollover book is a different instrument:

    symbol   pooled   hour-00 p50   hour-01 p50          (data/cost_surface.json, broker clock)
    USDZAR     329        3534          1496
    GBPNOK     276        4074           967
    CHFNOK     267        4511          1066
    GBPMXN     300        4621           768
    EURCHF     0.5          46            16

and fourteen registry rows (USDJPY, EURUSD, GBPUSD, AUDUSD, ...) read a spread of ZERO, so their
clocks ran on the engine's 0.05 floor -- free.

WHAT THIS DOES. It turns the surface into a per-(weekday, hour) spread TABLE on the cost model
(`Costs.spread_per_lot_by_hour`), and the engine charges each trade the spread of the slot where
it crosses the ask, on the same clock the bars carry. MT5 bars are bid bars, so:

    long  trade cost = spread(ENTRY dow, hour) + 2 x commission + swap x nights crossed
    short trade cost = spread(EXIT dow, hour)  + 2 x commission + swap x nights crossed

(commission and swap are unchanged). A long entering at the broker-00/01 rollover on a ZAR
cross pays the rollover book in full -- the hour where the venue refused the desk's sends with
retcode 10016 -- never the pooled price.

THE CLOCK. The surface is built from the H1 parquets' own index hours, which are Fusion's server
clock (NY+7: UTC+3 in the northern summer, UTC+2 in winter; `fusion_spread_tape` measured the
offset), and every replay the engine runs reads those same bar stamps. So the lookup key IS the
build key; no conversion is applied and none may be, or hour 00 (the rollover) is charged to the
wrong hour. A caller holding a UTC time must convert to the broker clock before asking.

THE FALLBACK LADDER, and it never goes down to zero or to a cheaper number:

  1. day-of-week x hour cell, priced bars >= MIN_DOW_OBS -- shrunk toward its hour cell;
  2. hour cell MEASURED (>= MIN_OBS priced bars)            -- its p50;
  3. hour cell THIN (MIN_THIN_OBS..MIN_OBS)                 -- shrunk toward its PARENT,
     (n x thin + K x parent) / (n + K), n_eff = n + K stated;
  4. no hour measurement                                    -- the parent's UPPER quantile (p75;
     p90 under stress), never its median;
  where PARENT = the symbol-session cell when MEASURED, else the symbol level. Every parent is
  built from priced (non-zero) bars, so none is zero.
  5. symbol absent from the surface                         -- the registry's pooled spread when
     it is positive AND fresh, labelled REGISTRY_FALLBACK; otherwise UNMEASURED.

UNMEASURED is a verdict, never a price: `costs_at_entry_hour` returns no cost model (None) with a
basis string that starts with "UNMEASURED", and `field_status` names every
zero, missing or stale spread/swap/commission field so a certificate or clock priced on one is
queued for repricing instead of being treated as free.

IT ONLY MAKES THE BAR TRUER. No trial is added, no gate is lowered, and nothing here vetoes a
cell: it changes the number a cell is charged, and the existing gates judge the result.
"""
from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_DESK = Path(__file__).resolve().parent.parent
SURFACE_PATH = _DESK / "data" / "cost_surface.json"
#: The same schema measured from Fusion's own TICKS (`recorders/tape_features.py`, trading box
#: only). Where it holds a MEASURED cell it outranks the bar-spread surface: a tick is the quote
#: the order meets, a bar's `spread` column is one reading per bar.
TICK_SURFACE_PATH = _DESK / "data" / "cost_surface_tick.json"

#: Pseudo-observations of the parent mixed into a thin cell: a cell with n = K is believed half.
#: A quarter of `cost_surface.MIN_OBS` (200), so a cell one bar short of MEASURED is ~80% its own.
K_SHRINK = 50.0

#: Priced bars in an hour's last-365-day window before it is preferred (`cost_surface`).
MIN_RECENT_OBS = 100

#: Bars of a dow x hour cell before it is used at all (mirrors `cost_surface.MIN_DOW_OBS`).
MIN_DOW_OBS = 40

#: STALENESS, defined from the registry's own stamps. A spread field is stamped by
#: `_provenance.median_spread_pts.at` (else the row's `updated_at`); swap fields by the row's
#: `updated_at` (the collector writes swap_long/swap_short with the row). Past these ages the
#: field is STALE and prices as UNMEASURED:
#:   * spread 30 days -- the surface itself is held to a 72 h freshness bar
#:     (`run_desk_integrity`), and a month-old registry median predates at least one account
#:     regime change on this desk (2026-08-17: majors moved from a ~13 pt book to 0 + commission);
#:   * swap 30 days -- the broker's financing rates move with policy rates and the desk captures
#:     them hourly (`reports/BROKER_SWAPS_FRESHNESS.json`, stale_after_h 26); a registry copy a
#:     month behind that tape is not the rate the account is charged.
SPREAD_STALE_DAYS = 30.0
SWAP_STALE_DAYS = 30.0

COST_FIELDS = ("spread", "swap", "commission")

#: THE SURFACE ITSELF MUST BE CURRENT AND OF THE REVISION THIS READER WAS WRITTEN FOR (audit
#: 2026-10-13). The committed surface was a revision-1 build of 2026-09-23 (MT5-CostState not
#: running): no recent-regime, weekday or session parents, the pre-2021 fixed-spread placeholders
#: still in (AUDCHF 160 pts). Priced through this ladder it reads as a measurement it is not. A
#: surface with `schema_revision` below MIN_SCHEMA_REVISION, no parseable `built_at`, or one older
#: than SURFACE_MAX_AGE_H (the 72 h bar `run_desk_integrity` already holds it to) prices NOTHING
#: here: every hour is UNMEASURED and the consumer falls to its own named fallback.
MIN_SCHEMA_REVISION = 2
SURFACE_MAX_AGE_H = 72.0

_SURFACE_CACHE: dict[str, Any] = {}


def load_surface(path: Path | None = None) -> dict[str, Any] | None:
    """The committed surface, read once per process per path; None when absent or unreadable."""
    p = Path(path or SURFACE_PATH)
    key = str(p)
    if key not in _SURFACE_CACHE:
        try:
            doc = json.loads(p.read_text("utf-8"))
            _SURFACE_CACHE[key] = doc if isinstance(doc, dict) else None
        except (OSError, ValueError):
            _SURFACE_CACHE[key] = None
    return _SURFACE_CACHE[key]


def surface_usable(surface: dict[str, Any] | None,
                   now: datetime | None = None) -> tuple[bool, str]:
    """(usable, why) for a cost-surface document: revision >= 2, stamped, at most 72 h old."""
    if not isinstance(surface, dict):
        return False, "no cost surface"
    try:
        rev = int(surface.get("schema_revision") or 1)
    except (TypeError, ValueError):
        rev = 1
    if rev < MIN_SCHEMA_REVISION:
        return False, (f"cost surface is schema revision {rev} (< {MIN_SCHEMA_REVISION}); "
                       "rebuild with `python -m research.cost_surface` on the trading box")
    age = _age_days(surface.get("built_at"), now or datetime.now(UTC))
    if age is None:
        return False, "cost surface carries no parseable built_at"
    if age * 24.0 > SURFACE_MAX_AGE_H:
        return False, (f"cost surface is {age * 24.0:.0f} h old (> {SURFACE_MAX_AGE_H:g} h, "
                       f"built {surface.get('built_at')})")
    return True, "fresh"


def surface_stamp(path: Path | None = None, now: datetime | None = None) -> dict[str, Any]:
    """What a ledger row priced on the surface must carry: built_at, sha256, revision, usable.

    The sha is of the file's bytes with line endings normalised (a Windows checkout and a Linux
    one hold the same surface)."""
    import hashlib

    p = Path(path or SURFACE_PATH)
    try:
        raw = p.read_bytes()
    except OSError:
        return {"cost_surface_sha": None, "cost_surface_built_at": None,
                "cost_surface_usable": False, "cost_surface_why": "no cost surface file"}
    doc = load_surface(p)
    ok, why = surface_usable(doc, now)
    return {"cost_surface_sha": hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()[:16],
            "cost_surface_built_at": (doc or {}).get("built_at"),
            "cost_surface_revision": (doc or {}).get("schema_revision", 1),
            "cost_surface_usable": ok, "cost_surface_why": why}


def _num(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f else None


def _session_of(hour: int) -> str:
    try:
        from research.cost_surface import session_of  # type: ignore[import-not-found]
    except ImportError:  # pragma: no cover - path variant
        from desks.mt5.research.cost_surface import session_of  # type: ignore[import-not-found]
    return str(session_of(hour))


def _parent(row: dict[str, Any], hour: int, q: str) -> tuple[float | None, str, float | None]:
    """(median, label, upper) of the thin hour's parent: symbol-session, else symbol level."""
    upper_q = "p90" if q == "p90" else "p75"
    sess = (row.get("sessions") or {}).get(_session_of(hour)) or {}
    if sess.get("status") == "MEASURED":
        return _num(sess.get(q)), f"session:{_session_of(hour)}", _num(sess.get(upper_q))
    sym = row.get("symbol_level") or {}
    if sym.get("status") == "MEASURED":
        return _num(sym.get(q)), "symbol", _num(sym.get(upper_q))
    # A schema-1 surface carries no parents: the symbol's own worst measured hour is the upper
    # bound the old fallback should always have been (never the pooled scalar, never zero).
    vals = [_num(c.get(q)) for c in (row.get("hours") or {}).values()
            if isinstance(c, dict) and c.get("status") == "MEASURED"]
    vals = [v for v in vals if v is not None and v > 0]
    if vals:
        return max(vals), "worst_measured_hour", max(vals)
    return None, "none", None


def hour_spread_pts(surface: dict[str, Any] | None, symbol: str, hour: int,
                    q: str = "p50") -> tuple[float | None, dict[str, Any]]:
    """The spread in POINTS charged at broker `hour` for `symbol`, and how it was reached.

    `q` is "p50" (the base charge) or "p90" (the stress charge). None only when the symbol has
    no row and no parent at all -- the caller must then read UNMEASURED, never zero.
    """
    h = int(hour) % 24
    if surface is not None:
        ok, why = surface_usable(surface)
        if not ok:
            return None, {"basis": f"UNMEASURED: {why}"}
    tick = load_surface(TICK_SURFACE_PATH) if surface is None or surface is load_surface() \
        else None
    if tick is not None and not surface_usable(tick)[0]:
        tick = None
    tcell = ((((tick or {}).get("symbols") or {}).get(symbol) or {}).get("hours") or {}
             ).get(str(h)) or {}
    if tcell.get("status") == "MEASURED" and (_num(tcell.get(q)) or 0) > 0:
        n_t = int(tcell.get("n_nonzero") or tcell.get("n") or 0)
        return float(tcell[q]), {"basis": "tick_hour", "n": n_t, "n_eff": n_t}
    row = ((surface or {}).get("symbols") or {}).get(symbol)
    if not isinstance(row, dict):
        return None, {"basis": "UNMEASURED: symbol absent from the cost surface"}
    cell = (row.get("hours") or {}).get(str(h)) or {}
    n = int(cell.get("n_nonzero") or 0)
    # RECENCY-PREFERRED: the last year's priced bars at this hour, when there are enough of them.
    # NZDJPY hour 0 reads 42/100 over eight years and 87/119 over the last twelve months; the
    # long-run cell understates the regime the sleeve actually trades in by ~2x.
    rn = int(cell.get("r365_n") or 0)
    rv = _num(cell.get(f"r365_{q}"))
    if rn >= MIN_RECENT_OBS and rv is not None and rv > 0:
        return rv, {"basis": "hour_recent365", "n": rn, "n_eff": rn}
    # A MEASURED cell whose quantile is 0 is not a price (it would charge the 0.05 floor): it
    # falls through to the thin/parent ladder like any unpriced hour.
    if cell.get("status") == "MEASURED" and (_num(cell.get(q)) or 0) > 0:
        return float(cell[q]), {"basis": "hour", "n": n, "n_eff": n}
    parent, plabel, upper = _parent(row, h, q)
    thin = _num(cell.get(f"thin_{q}"))
    if thin is not None and thin > 0 and parent is not None and parent > 0:
        v = (n * thin + K_SHRINK * parent) / (n + K_SHRINK)
        return round(v, 3), {"basis": f"hour_thin_shrunk_to_{plabel}", "n": n,
                             "n_eff": n + K_SHRINK}
    if upper is not None and upper > 0:
        return float(upper), {"basis": f"{plabel}_upper_quantile", "n": n, "n_eff": 0}
    return None, {"basis": "UNMEASURED: no hour cell and no parent on the surface"}


def dow_hour_spread_pts(surface: dict[str, Any] | None, symbol: str, dow: int, hour: int,
                        q: str = "p50") -> tuple[float | None, dict[str, Any]]:
    """The (weekday, hour) charge: the dow cell shrunk toward its hour charge, never below zero.

    `dow` is Monday=0 on the broker clock (the same `dayofweek` the surface was built with).
    """
    base, info = hour_spread_pts(surface, symbol, hour, q)
    row = ((surface or {}).get("symbols") or {}).get(symbol) or {}
    cell = ((row.get("dow_hours") or {}).get(str(int(dow))) or {}).get(str(int(hour) % 24))
    if base is None or not isinstance(cell, list) or len(cell) < 3:
        return base, info
    idx = 1 if q == "p90" else 0
    v, n = _num(cell[idx]), int(cell[2] or 0)
    if v is None or v <= 0 or n < MIN_DOW_OBS:
        return base, info
    out = (n * v + K_SHRINK * base) / (n + K_SHRINK)
    return round(out, 3), {"basis": f"dow_shrunk_to_{info.get('basis')}", "n": n,
                           "n_eff": n + K_SHRINK}


def spread_table_pts(surface: dict[str, Any] | None, symbol: str,
                     q: str = "p50") -> tuple[tuple[float, ...] | None, dict[str, Any]]:
    """168 charges (dow*24 + hour) in points, or None with the reason when any hour is unpriced."""
    vals: list[float] = []
    bases: dict[str, int] = {}
    for dw in range(7):
        for h in range(24):
            v, info = dow_hour_spread_pts(surface, symbol, dw, h, q)
            if v is None:
                return None, {"basis": str(info.get("basis")), "hour": h, "dow": dw}
            vals.append(float(v))
            b = str(info.get("basis"))
            bases[b] = bases.get(b, 0) + 1
    return tuple(vals), {"basis": "fill_hour_surface_table", "cells_by_basis": bases,
                         "q": q, "schema": (surface or {}).get("schema")}


# ----------------------------------------------------------------------------------------------
# Zero / missing / stale cost fields.
# ----------------------------------------------------------------------------------------------

def _age_days(stamp: Any, now: datetime) -> float | None:
    if not stamp:
        return None
    try:
        t = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=UTC)
    return (now - t).total_seconds() / 86400.0


def commission_per_lot() -> float | None:
    """The desk's ONE commission number (measured from the account's deals), or None."""
    try:
        from libs.portfolio.fusion_cost import COMMISSION_PER_LOT_PER_SIDE
    except ImportError:
        return None
    v = _num(COMMISSION_PER_LOT_PER_SIDE)
    return v if v is not None and v > 0 else None


def field_status(row: dict[str, Any] | None, now: datetime | None = None) -> dict[str, str]:
    """{"spread"|"swap"|"commission": "MEASURED" | "ZERO" | "MISSING" | "STALE"} for one row.

    ZERO for a spread is unpriced (a raw quote of 0 is not the cost of a round trip, and a 0 lets
    a non-edge certify). ZERO for a swap is a stored rate of exactly 0 on BOTH sides -- a real
    instrument with no financing at all is possible but must be evidenced, never assumed.
    """
    now = now or datetime.now(UTC)
    row = row if isinstance(row, dict) else {}
    out: dict[str, str] = {}
    sp = row.get("median_spread_pts")
    if sp is None or _num(sp) is None:
        out["spread"] = "MISSING"
    elif float(sp) <= 0:
        out["spread"] = "ZERO"
    else:
        stamp = (((row.get("_provenance") or {}).get("median_spread_pts") or {}).get("at")
                 or row.get("updated_at"))
        age = _age_days(stamp, now)
        out["spread"] = ("STALE" if age is None or age > SPREAD_STALE_DAYS else "MEASURED")
    sl, ss = row.get("swap_long"), row.get("swap_short")
    if _num(sl) is None or _num(ss) is None:
        out["swap"] = "MISSING"
    elif float(sl) == 0 and float(ss) == 0:
        out["swap"] = "ZERO"
    else:
        age = _age_days(row.get("updated_at"), now)
        out["swap"] = "STALE" if age is None or age > SWAP_STALE_DAYS else "MEASURED"
    out["commission"] = "MEASURED" if commission_per_lot() is not None else "MISSING"
    return out


def unmeasured_fields(registry: dict[str, Any] | None,
                      now: datetime | None = None) -> dict[str, Any]:
    """The JUDGE_COVERAGE block: every symbol with a zero/missing/stale cost field, by field."""
    now = now or datetime.now(UTC)
    reg = registry if isinstance(registry, dict) else {}
    rows = reg.get("symbols") if isinstance(reg.get("symbols"), dict) else reg
    by_field: dict[str, dict[str, list[str]]] = {f: {} for f in COST_FIELDS}
    flagged: set[str] = set()
    hard: set[str] = set()
    n_rows = 0
    for sym, row in sorted((rows or {}).items()):
        if not isinstance(row, dict):
            continue
        n_rows += 1
        for f, st in field_status(row, now).items():
            if st != "MEASURED":
                by_field[f].setdefault(st, []).append(str(sym))
                flagged.add(str(sym))
                if st in ("ZERO", "MISSING"):
                    hard.add(str(sym))
    return {
        "n_symbols": len(flagged),
        # The subset that is not merely old: a stored zero or an absent field.
        "n_symbols_zero_or_missing": len(hard),
        "n_registry_rows": n_rows,
        "by_field": by_field,
        "counts": {f: {st: len(v) for st, v in d.items()} for f, d in by_field.items()},
        "stale_rule": (f"spread stale after {SPREAD_STALE_DAYS:g} d from "
                       "_provenance.median_spread_pts.at (else updated_at); swap stale after "
                       f"{SWAP_STALE_DAYS:g} d from updated_at; commission is the desk constant "
                       "fusion_cost.COMMISSION_PER_LOT_PER_SIDE"),
        "rule": ("a symbol listed here prices as UNMEASURED: a certificate or clock priced on "
                 "it is queued for repricing, never treated as free"),
    }


def charged_vs_hour(surface: dict[str, Any] | None, registry: dict[str, Any] | None,
                    ratio: float = 2.0) -> dict[str, Any]:
    """Every symbol whose CHARGED scalar differs from an hour's own charge by more than `ratio`.

    "Charged" is what a flat consumer pays: the registry's `median_spread_pts`, and the
    surface's stored `pooled_median_spread_pts` (a revision-1 surface copied it from the registry
    at build time and never checked it). For each, the hours whose entry-hour charge (this
    module's ladder, p50) sits outside [1/ratio, ratio] of it are listed, so a rollover sleeve
    priced flat is named with the hour that makes it wrong. `pooled_vs_hourly` separately lists
    symbols whose stored pooled value disagrees with the median of their own hourly p50s.
    """
    reg = registry if isinstance(registry, dict) else {}
    reg = reg.get("symbols", reg) if isinstance(reg.get("symbols"), dict) else reg
    by_symbol: dict[str, Any] = {}
    pooled_bad: list[dict[str, Any]] = []
    for sym, row in sorted(((surface or {}).get("symbols") or {}).items()):
        if not isinstance(row, dict):
            continue
        hours = row.get("hours") or {}
        hp50 = sorted(float(c["p50"]) for c in hours.values()
                      if isinstance(c, dict) and c.get("status") == "MEASURED"
                      and _num(c.get("p50")) is not None)
        own = hp50[len(hp50) // 2] if hp50 else None
        stored = _num(row.get("pooled_median_spread_pts"))
        if own and (stored is None or stored <= 0 or not (1 / ratio <= stored / own <= ratio)):
            pooled_bad.append({"symbol": sym, "stored_pooled_pts": stored,
                               "median_hourly_p50_pts": own,
                               "ratio": round(stored / own, 3) if stored else None})
        entry: dict[str, Any] = {}
        for label, charged in (("registry", _num((reg.get(sym) or {}).get("median_spread_pts"))),
                               ("surface_pooled", stored)):
            bad: dict[str, Any] = {}
            for h in range(24):
                v, _ = hour_spread_pts(surface, sym, h)
                if v is None:
                    continue
                if charged is None or charged <= 0:
                    bad[str(h)] = {"hour_pts": v, "charged_pts": charged, "x": None}
                elif not (1 / ratio <= v / charged <= ratio):
                    bad[str(h)] = {"hour_pts": v, "charged_pts": charged,
                                   "x": round(v / charged, 2)}
            if bad:
                entry[label] = bad
        if entry:
            by_symbol[sym] = entry
    under = sorted(s for s, e in by_symbol.items()
                   if any((c.get("x") or 0) > ratio for c in (e.get("registry") or {}).values()))
    roll = sorted(s for s, e in by_symbol.items()
                  if any(h in (e.get("registry") or {}) and
                         ((e["registry"][h].get("x") or 0) > ratio) for h in ("23", "0", "1")))
    return {"ratio": ratio, "n_symbols": len(by_symbol),
            "n_undercharged_some_hour": len(under), "undercharged_some_hour": under,
            "n_undercharged_at_rollover": len(roll), "undercharged_at_rollover": roll,
            "n_pooled_vs_hourly_mismatch": len(pooled_bad), "pooled_vs_hourly": pooled_bad,
            "by_symbol": by_symbol}


# ----------------------------------------------------------------------------------------------
# The cost model every consumer builds.
# ----------------------------------------------------------------------------------------------

def attach_table(symbol: str, meta_row: dict[str, Any], base: Any, mult: float = 1.0, *,
                 q: str = "p50", surface: dict[str, Any] | None = None) -> tuple[Any, str]:
    """(costs, basis): `base` (a `Costs.from_symbol` result) with the surface's spread table.

    For call sites that must keep calling the sanctioned constructor themselves (the forward
    clock's test pins it). `mult` must be the spread multiple `base` was built with.

    UNLIKE `costs_at_entry_hour`, an UNMEASURED spread here returns `base` unchanged -- the flat
    registry model the forward clock priced on before this module existed -- with the basis
    saying UNMEASURED. Withholding the price would stop ~430 running clocks whose registry
    spread is STALE or ZERO (measured 2026-10-14); the label, stamped on every ledger row, is
    what queues them for repricing. This is a disclosed flat price, not a new one.
    """
    row = meta_row if isinstance(meta_row, dict) else {}
    surf = surface if surface is not None else load_surface()
    table, info = spread_table_pts(surf, symbol, q)
    cs = float(row.get("contract_size", 1e5) or 1e5)
    ts = float(row.get("tick_size", 0.0) or 0.0)
    if table is not None and ts > 0:
        per_lot = tuple(max(p * ts * cs * float(mult), 0.05) for p in table)
        return replace(base, spread_per_lot_by_hour=per_lot), str(info["basis"])
    st = field_status(row)["spread"]
    if st == "MEASURED":
        return base, "REGISTRY_FALLBACK:pooled_median_spread"
    why = info.get("basis") if table is None else "tick_size missing"
    return base, f"UNMEASURED(spread={st}):{why}"


def costs_at_entry_hour(symbol: str, meta_row: dict[str, Any], mult: float = 1.0, *,
                        commission: float | None = None, q: str = "p50",
                        surface: dict[str, Any] | None = None,
                        now: datetime | None = None) -> tuple[Any | None, str]:
    """(Costs or None, basis). The cost model with its per-(dow, hour) spread table attached.

    `mult` scales the spread table exactly as it scales the flat spread in `from_symbol`.
    When the surface cannot price the symbol, the flat registry spread is used ONLY when it is
    positive and fresh (basis REGISTRY_FALLBACK). Otherwise the costs are None and the basis
    starts with "UNMEASURED": NO PRICE IS RETURNED (audit 2026-10-13). A zero registry spread
    used to price at the engine's 0.05 floor and a NaN one at NaN R -- both are fake prices; the
    caller must publish the UNMEASURED basis and not replay on it.
    """
    from mt5desk.engine import Costs

    row = meta_row if isinstance(meta_row, dict) else {}
    kw: dict[str, Any] = {"mult": mult}
    if commission is not None:
        kw["commission_per_lot"] = commission
    base = Costs.from_symbol(row, **kw)
    surf = surface if surface is not None else load_surface()
    table, info = spread_table_pts(surf, symbol, q)
    st = field_status(row, now)
    # Swap/commission states are published by `field_status` / `unmeasured_fields`, not folded
    # into the spread basis: a reader keying on "fill_hour" must still see which spread it got.
    flags: list[str] = []
    if table is not None:
        cs = float(row.get("contract_size", 1e5) or 1e5)
        ts = float(row.get("tick_size", 0.0) or 0.0)
        if ts > 0:
            per_lot = tuple(max(p * ts * cs * float(mult), 0.05) for p in table)
            return replace(base, spread_per_lot_by_hour=per_lot), str(info["basis"])
        flags.append("tick_size=MISSING")
    if st["spread"] == "MEASURED":
        return base, "REGISTRY_FALLBACK:pooled_median_spread"
    flags.insert(0, f"spread={st['spread']}")
    return None, f"UNMEASURED({', '.join(flags)}):{info.get('basis')}"


def stress_costs(base: Any, symbol: str, meta_row: dict[str, Any], mult: float,
                 surface: dict[str, Any] | None = None) -> Any:
    """The stress arm: the base table x `mult`, never below the hour's measured p90 table.

    A 3x stress of the pooled scalar is CHEAPER than the real rollover fill on every exotic in
    the table above, so the stress arm reads the same surface as the base arm.
    """
    stressed = base.stressed(mult)
    tab = getattr(stressed, "spread_per_lot_by_hour", None)
    if not tab:
        return stressed
    p90, _ = costs_at_entry_hour(symbol, meta_row, 1.0, q="p90",
                                 commission=base.commission_per_lot, surface=surface)
    t90 = getattr(p90, "spread_per_lot_by_hour", None)
    if not t90 or len(t90) != len(tab):
        return stressed
    return replace(stressed, spread_per_lot_by_hour=tuple(max(a, b) for a, b in zip(tab, t90,
                                                                                     strict=True)))


def gauntlet_costs(symbol: str, meta: dict[str, Any], sigs: Any = None,
                   timeframe: str = "H1") -> tuple[Any, str, int | None]:
    """The sealed gauntlet's ONE call: (costs, cost_basis, modal fill hour for the record)."""
    hour = None
    try:
        import external_gauntlet as _eg  # type: ignore[import-not-found]
        hour = _eg._modal_fill_hour(sigs, timeframe)
    except Exception:
        hour = None
    row = (meta or {}).get(symbol) or {}
    costs, basis = costs_at_entry_hour(symbol, row)
    if costs is None:
        # THE SEALED CALLER NEEDS A COST MODEL, and the gauntlet's pre-patch pricing for this
        # symbol was exactly this flat registry model -- so the cell is built as it is today and
        # its `cost_basis` says UNMEASURED, which the certificate carries. No cheaper number than
        # today's is introduced; a gauntlet that refuses UNMEASURED cells is the patch's call.
        from mt5desk.engine import Costs
        costs = Costs.from_symbol(row)
    return costs, basis, hour


def charged_spread_pts(costs: Any, meta_row: dict[str, Any], entry_ts: Any,
                       exit_ts: Any, side: int = 1) -> float | None:
    """The points one trade was charged (a long at entry, a short at exit), for audits."""
    tab = getattr(costs, "spread_per_lot_by_hour", None)
    cs = float((meta_row or {}).get("contract_size", 1e5) or 1e5)
    ts = float((meta_row or {}).get("tick_size", 0.0) or 0.0)
    if not tab or ts <= 0:
        return None
    from mt5desk.engine import spread_at

    per_lot = spread_at(costs, entry_ts if side > 0 else exit_ts)
    return per_lot / (ts * cs)


#: Shrinkage constant for measured entry slip: an hour cell with n clean fills keeps weight
#: n / (n + SLIP_K) and the rest goes to the symbol's pooled clean slip. With SLIP_K = 10 a cell
#: needs 10 fills to carry half its own weight (the same count markout flags `n_small` below).
SLIP_K = 10.0


def hour_slip_pts(markout: dict[str, Any] | None, symbol: str, hour: int,
                  k: float = SLIP_K) -> tuple[float, dict[str, Any]]:
    """Measured entry slip in POINTS at broker `hour` for `symbol`, from markout.json's
    `slip_breakdown` (clean rows only; positive = cost). READ-ONLY: no charge reads this yet.

    Rule: v = w * cell_mean + (1 - w) * symbol_mean, w = n / (n + k), n = the cell's clean fills.
    An empty cell is the symbol's pooled mean. A symbol with no clean measured fill returns 0.0
    with status UNMEASURED -- 0 because no slip was measured, never because none exists; a reader
    that charges it must carry the status. Negative only where fills measured price improvement.
    """
    sb = (markout or {}).get("slip_breakdown") or {}
    sym = ((sb.get("by_symbol") or {}).get(symbol) or {}).get("clean") or {}
    s_pts = sym.get("pts") or {}
    s_mean, s_n = _num(s_pts.get("mean")), int(s_pts.get("n") or 0)
    if s_mean is None or s_n <= 0:
        return 0.0, {"status": "UNMEASURED", "basis": "UNMEASURED: no clean markout fill for "
                     f"{symbol}; 0 charged by default, not measured", "n": 0}
    cell = ((((sb.get("by_symbol_hour") or {}).get(symbol) or {}).get(str(int(hour) % 24))
             or {}).get("clean") or {}).get("pts") or {}
    c_mean, n = _num(cell.get("mean")), int(cell.get("n") or 0)
    if c_mean is None or n <= 0:
        return s_mean, {"status": "MEASURED", "basis": "symbol_pooled", "n": 0, "n_symbol": s_n,
                        "weight_hour": 0.0}
    w = n / (n + float(k))
    return w * c_mean + (1.0 - w) * s_mean, {
        "status": "MEASURED", "basis": "hour_shrunk_to_symbol", "n": n, "n_symbol": s_n,
        "weight_hour": w, "k": float(k)}


def hour_cost_pts(surface: dict[str, Any] | None, markout: dict[str, Any] | None, symbol: str,
                  hour: int, q: str = "p50") -> tuple[float | None, dict[str, Any]]:
    """Spread + measured slip in points at broker `hour`. READ-ONLY helper: not wired into any
    charge (the slip measurement is under audit, 2026-10-14). None when the spread is UNMEASURED."""
    spread, s_info = hour_spread_pts(surface, symbol, hour, q)
    slip, p_info = hour_slip_pts(markout, symbol, hour)
    if spread is None:
        return None, {"spread": s_info, "slip": p_info}
    return spread + slip, {"spread": s_info, "slip": p_info, "spread_pts": spread,
                           "slip_pts": slip}
