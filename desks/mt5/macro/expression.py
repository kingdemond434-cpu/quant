"""EXPRESSION -- event, to the thing it concerns, to the instruments THIS desk can actually reach.

THE FAILURE THIS EXISTS TO PREVENT, in the principal's own example. A South American country
changes something about its bean exports. The impact estimate is about the Brazilian real. BRL is
not in the Fusion universe. A pipeline that stops there has silently thrown away every
commodity-driven signal it will ever produce, and its logs will say nothing was wrong -- the
forecast was correct, it simply had nowhere to go. So IMPACT and EXPRESSION are separate steps
here, and the expression step's job is to find whichever tradeable instruments carry MEASURED
exposure to the same driver.

The desk can express this. Measured on `desks/mt5/data/universe/universe.json`: 251 instruments,
including SOYBEAN, CORN, WHEAT, SUGAR, COTTON, the cocoas and the coffees as instruments in their
own right, XCUUSD and the rest of the metals, three energy contracts, and 86 FX pairs of which 57
are exotic crosses. An agricultural event has real expressions -- in the soft itself, and in the
currencies of the economies that export or import it.

THE PROPAGATION IS MEASURED, AND THIS IS THE PART THAT MATTERS MOST. There is no table in this
file saying soybeans move the real, or copper moves the Australian dollar, or any other pair of
things. What there is instead is `measure_exposures`: every tradeable instrument's regression
beta on every driver instrument the desk quotes, with a bootstrap standard error and the same
never-shrinking multiplicity charge `factors.py` uses. That set of betas IS the desk's
terms-of-trade map, it is re-measured as data accumulates, and it will contain links nobody wrote
down -- an exotic cross with a real but unobvious exposure -- because it was never restricted to
links somebody thought of. A hardcoded table can only ever encode what was known the day it was
written.

WHAT IS LEXICAL AND WHAT IS CAUSAL, kept strictly apart. That the token "soybean" refers to the
instrument SOYBEAN is a NAMING fact, and naming facts are allowed to be written down --
`_seed_aliases` does exactly that and nothing more. That SOYBEAN moves any particular currency is
a CAUSAL claim, and every causal claim in this file is a measured beta with an interval. The
aliases also grow: `learn_aliases` promotes a token to an instrument's alias when items containing
it have repeatedly shown a measured reaction concentrated in that instrument, so the vocabulary
extends itself past what was seeded.

THERE IS NO "BOOST THE OPPOSITE SIDE" RULE HERE, DELIBERATELY. This module outputs a forecast
delta per instrument and nothing else. Whether the book should take the other side of anything is
the allocator's joint solve to decide -- and it is frequently the wrong answer, because an event
that impairs one exposure often impairs its naive opposite too. Hardcoding a paired response would
fight the optimiser and would be wrong in exactly the cases where it mattered.

DEAD ENDS ARE NAMED, NOT SWALLOWED. When an economy or a factor has no admitted tradeable
expression, `express` returns a blind-spot record saying so. That is a research and purchasing
decision the principal can act on; a silent empty list is a loss nobody can see.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from statistics import NormalDist
from typing import Any

from .factors import ALPHA, BOOTSTRAP_B, FactorBasis, MultiplicityLedger
from .ledger import MACRO_DIR, write_json_atomic
from .prices import PriceReader, aligned_returns
from .schema import InstrumentForecast, Status, now_iso

DESK = Path(__file__).resolve().parents[1]
UNIVERSE_JSON = DESK / "data" / "universe" / "universe.json"
EXPOSURE_PATH = MACRO_DIR / "exposures.json"
ALIAS_PATH = MACRO_DIR / "instrument_aliases.json"

#: Aligned observations required before an exposure beta is estimable at all.
MIN_EXPOSURE_N = 250

#: Asset classes whose instruments act as DRIVERS -- the physical and rate things an event is
#: usually about. FX is excluded from the driver set not because currencies cannot drive but
#: because the currency side is the TARGET here; a currency-on-currency beta is a cross, which
#: the desk already trades directly.
DRIVER_CLASSES = ("Soft Commodity", "Commodities", "Energy", "Bonds", "Indices")

#: Classes an event may be expressed IN. Everything the gateway can send an order for.
TARGET_CLASSES = ("Forex", "Forex Exotics", "Soft Commodity", "Commodities", "Energy",
                  "Bonds", "Indices", "Equities", "Crypto")

__all__ = [
    "DRIVER_CLASSES",
    "MIN_EXPOSURE_N",
    "Exposure",
    "express",
    "expression_report",
    "learn_aliases",
    "lexical_drivers",
    "load_universe",
    "measure_exposures",
    "symbol_currencies",
    "symbols_in_classes",
    "tradeable_currencies",
]


def load_universe(path: Path | str | None = None) -> dict[str, dict[str, Any]]:
    p = Path(path) if path is not None else UNIVERSE_JSON
    if not p.exists():
        return {}
    try:
        raw = json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in raw.items() if isinstance(v, dict)}


def symbols_in_classes(universe: Mapping[str, Mapping[str, Any]],
                       classes: Sequence[str]) -> list[str]:
    return sorted(s for s, m in universe.items() if str(m.get("asset_class", "")) in classes)


_CCY_RE = re.compile(r"^([A-Z]{3})([A-Z]{3})$")


#: Only these classes have symbols whose NAME is two currency codes. Splitting on shape alone
#: was measured wrong on this universe: COFARA (robusta/arabica coffee) parsed as COF + ARA and
#: invented a currency, and CHINAH, COTTON, NVIDIA and UKGILT do the same. A false currency tag
#: sends the expression step hunting for exposures nobody implied, so the class decides, not the
#: length.
_PAIR_CLASSES = ("Forex", "Forex Exotics")


def symbol_currencies(symbol: str, meta: Mapping[str, Any] | None = None) -> tuple[str, ...]:
    """The currencies a symbol is quoted in. STRUCTURAL: reading metadata, not claiming a cause.

    `EURPLN` concerns EUR and PLN by definition. `XAUUSD` concerns USD because its profit
    currency says so. Nothing here asserts that a Polish event moves EURPLN in any direction --
    that is a measured beta elsewhere.
    """
    cls = str((meta or {}).get("asset_class", "") or "")
    if cls in _PAIR_CLASSES:
        m = _CCY_RE.match(symbol)
        if m:
            return (m.group(1), m.group(2))
    prof = str((meta or {}).get("currency_profit", "") or "")
    return (prof,) if len(prof) == 3 else ()


def tradeable_currencies(universe: Mapping[str, Mapping[str, Any]]) -> set[str]:
    """Every currency this desk can take direct exposure to through an FX pair.

    Measured on the current universe file: 27 of them. Notably BRL IS quoted (USDBRL) while ARS,
    CLP, COP, PEN, TWD, PHP and MYR are not -- so the untradeable-economy path is a real path and
    not a hypothetical, but it is narrower than one would guess.
    """
    out: set[str] = set()
    for sym, meta in universe.items():
        if str(meta.get("asset_class", "")) in _PAIR_CLASSES:
            out.update(symbol_currencies(sym, meta))
    return out


def _seed_aliases(universe: Mapping[str, Mapping[str, Any]]) -> dict[str, list[str]]:
    """Instrument -> the words a feed is likely to use for it. NAMING ONLY.

    Most entries are derived mechanically from the symbol itself, so the table stays small and
    stays a vocabulary. The handful of written-down entries are the ones where the ticker is not
    a word (XTIUSD is WTI crude, XCUUSD is copper). Extending this cannot create a causal claim;
    it can only let the desk understand that a headline is talking about an instrument it quotes.
    """
    hand: dict[str, list[str]] = {
        "XTIUSD": ["wti", "crude", "oil", "petroleum"],
        "XBRUSD": ["brent", "crude", "oil"],
        "XNGUSD": ["natgas", "gas", "lng"],
        "XAUUSD": ["gold", "bullion"],
        "XAGUSD": ["silver"],
        "XCUUSD": ["copper"],
        "XPTUSD": ["platinum"],
        "XPDUSD": ["palladium"],
        "XALUSD": ["aluminium", "aluminum"],
        "XNIUSD": ["nickel"],
        "XZNUSD": ["zinc"],
        "XPBUSD": ["lead"],
        "UKCOCOA": ["cocoa"],
        "USCOCOA": ["cocoa"],
        "COFARA": ["coffee", "arabica"],
        "COFROB": ["coffee", "robusta"],
        "SUGARRAW": ["sugar"],
        "OJ": ["orange", "juice", "citrus"],
        "UST10Y": ["treasury", "treasuries", "10-year", "yields"],
        "UST05Y": ["treasury", "treasuries", "5-year"],
        "UKGILT": ["gilt", "gilts"],
        "USDX": ["dollar", "dxy", "greenback"],
    }
    out: dict[str, list[str]] = {}
    for sym in universe:
        words = list(hand.get(sym, ()))
        low = sym.lower()
        if low.isalpha() and len(low) > 3 and not _CCY_RE.match(sym):
            words.append(low)
        if words:
            out[sym] = sorted(set(words))
    return out


def load_aliases(universe: Mapping[str, Mapping[str, Any]],
                 path: Path | str | None = None) -> dict[str, list[str]]:
    """Seeded vocabulary plus anything `learn_aliases` has promoted."""
    out = _seed_aliases(universe)
    p = Path(path) if path is not None else ALIAS_PATH
    if p.exists():
        try:
            raw = json.loads(p.read_text("utf-8"))
        except (OSError, ValueError):
            return out
        for sym, words in (raw.get("learned") or {}).items():
            if sym in universe and isinstance(words, list):
                out[sym] = sorted(set(out.get(sym, [])) | {str(w).lower() for w in words})
    return out


def lexical_drivers(text: str, aliases: Mapping[str, Sequence[str]]) -> list[str]:
    """Which quoted instruments this text is TALKING ABOUT. A reading step, not a forecast."""
    words = set(re.findall(r"[a-z][a-z0-9-]{2,}", text.lower()))
    return sorted(sym for sym, al in aliases.items() if words & {a.lower() for a in al})


def learn_aliases(observations: Sequence[tuple[str, Mapping[str, float]]], *,
                  min_instances: int = 20, concentration: float = 0.6,
                  existing: Mapping[str, Sequence[str]] | None = None) -> dict[str, list[str]]:
    """Promote a token to an instrument's alias when the EVIDENCE keeps pointing that way.

    `observations` is `(text, {symbol: |measured move in sigma|})`. A token earns an alias when it
    has appeared at least `min_instances` times and, across those appearances, at least
    `concentration` of the total measured reaction landed on one instrument. This is how the
    vocabulary grows past what was seeded -- a commodity, a company or a policy term nobody
    listed becomes readable once the market has repeatedly shown what it refers to.

    It is still only vocabulary. Learning that "arabica" means COFARA does not assert a direction
    for anything; it lets the measured betas do their work.
    """
    from .taxonomy import tokenise

    seen: Counter[str] = Counter()
    # Reaction MASS per (token, instrument), as floats -- a Counter is int-valued and would
    # silently truncate every share to zero.
    mass: dict[str, dict[str, float]] = {}
    for text, moves in observations:
        toks = set(tokenise(text))
        total = sum(abs(float(v)) for v in moves.values()) or 1.0
        for t in toks:
            seen[t] += 1
            bucket = mass.setdefault(t, {})
            for sym, v in moves.items():
                bucket[sym] = bucket.get(sym, 0.0) + abs(float(v)) / total
    learned: dict[str, set[str]] = {}
    for tok, n in seen.items():
        if n < min_instances:
            continue
        shares = mass.get(tok)
        if not shares:
            continue
        sym, share = max(shares.items(), key=lambda kv: kv[1])
        if share / n >= concentration:
            learned.setdefault(sym, set()).add(tok)
    for sym, words in (existing or {}).items():
        learned.setdefault(sym, set()).update(str(w).lower() for w in words)
    return {s: sorted(w) for s, w in sorted(learned.items())}


@dataclass(frozen=True)
class Exposure:
    """One measured target-on-driver beta. The desk's terms-of-trade map is a table of these."""

    symbol: str
    driver: str
    beta: float
    se: float
    ci_lo: float
    ci_hi: float
    n: int
    cells_charged: int
    admitted: bool
    status: str
    note: str = ""


def _ols_beta(y: Sequence[float], x: Sequence[float]) -> float | None:
    n = min(len(y), len(x))
    if n < 3:
        return None
    xm = sum(x[:n]) / n
    ym = sum(y[:n]) / n
    sxx = sum((xi - xm) ** 2 for xi in x[:n])
    if sxx <= 0:
        return None
    sxy = sum((x[i] - xm) * (y[i] - ym) for i in range(n))
    return sxy / sxx


def _beta_se(y: Sequence[float], x: Sequence[float], *, b: int = BOOTSTRAP_B,
             seed: int = 0) -> float | None:
    """Bootstrap the beta's standard error by resampling PAIRS.

    Pairs, not residuals: resampling residuals assumes the model, and the question here is
    whether there is a relationship at all. A pairs bootstrap is agnostic about that and is
    robust to the fat tails these returns actually have, which is why it is used rather than the
    textbook OLS standard error.
    """
    try:
        import numpy as np
    except ImportError:
        return None
    n = min(len(y), len(x))
    if n < 30:
        return None
    ya = np.asarray(y[:n], dtype=float)
    xa = np.asarray(x[:n], dtype=float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(b, n))
    xs = xa[idx]
    ys = ya[idx]
    xm = xs.mean(axis=1, keepdims=True)
    ym = ys.mean(axis=1, keepdims=True)
    sxx = ((xs - xm) ** 2).sum(axis=1)
    sxy = ((xs - xm) * (ys - ym)).sum(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        betas = np.where(sxx > 0, sxy / sxx, np.nan)
    betas = betas[np.isfinite(betas)]
    if betas.size < b // 4:
        return None
    se = float(betas.std(ddof=1))
    return se if se > 0 and math.isfinite(se) else None


def measure_exposures(reader: PriceReader, *, targets: Sequence[str], drivers: Sequence[str],
                      ledger: MultiplicityLedger, min_n: int = MIN_EXPOSURE_N,
                      seed: int = 0) -> list[Exposure]:
    """The learned terms-of-trade map: every target's beta on every driver, admitted or not.

    Every (target, driver) cell is charged to the SHARED multiplicity ledger before it is
    measured, so exploring the whole 251 x 30 grid is paid for in the width of every interval it
    produces. That is the correct price for a search this wide, and it is the reason a link
    discovered here can be believed.
    """
    # CHARGE THE WHOLE PASS BEFORE MEASURING ANY OF IT. Charging inside the loop would give the
    # first cell tested a discount -- it would face a narrower interval purely for being first,
    # which is a search-order artefact and exactly the kind of free pass a multiplicity ledger
    # exists to remove.
    for drv in drivers:
        for tgt in targets:
            if tgt != drv:
                ledger.charge(f"exposure:{tgt}", drv)
    cells = ledger.total

    out: list[Exposure] = []
    for drv in drivers:
        pool = [t for t in targets if t != drv]
        if not pool:
            continue
        panel, _ = aligned_returns(reader, [drv, *pool], min_obs=min_n)
        if drv not in panel:
            # SAY SO rather than skipping. A silent skip is how a driver the desk has no series
            # for becomes a driver the desk believes has no effect.
            out.extend(Exposure(t, drv, 0.0, 0.0, 0.0, 0.0, 0, cells, False, Status.UNMEASURED,
                                f"no aligned series for driver {drv} at min_n={min_n}")
                       for t in pool)
            continue
        x = panel[drv]
        for tgt in pool:
            y = panel.get(tgt)
            if y is None or len(y) < min_n:
                out.append(Exposure(tgt, drv, 0.0, 0.0, 0.0, 0.0, 0 if y is None else len(y),
                                    cells, False, Status.UNMEASURED,
                                    f"n={0 if y is None else len(y)} aligned obs < {min_n}"))
                continue
            beta = _ols_beta(y, x)
            se = _beta_se(y, x, seed=seed)
            if beta is None or se is None:
                out.append(Exposure(tgt, drv, 0.0, 0.0, 0.0, 0.0, len(y), cells, False,
                                    Status.UNMEASURED, "beta or bootstrap SE unavailable"))
                continue
            z = NormalDist().inv_cdf(1.0 - ALPHA / (2.0 * cells))
            lo, hi = beta - z * se, beta + z * se
            admitted = (lo > 0.0) or (hi < 0.0)
            out.append(Exposure(
                tgt, drv, round(beta, 6), round(se, 6), round(lo, 6), round(hi, 6), len(y),
                cells, admitted,
                Status.MEASURED if admitted else Status.RECORDED_ONLY,
                "" if admitted else (f"interval [{lo:.4f}, {hi:.4f}] includes zero at "
                                     f"alpha={ALPHA}/{cells} cells")))
    return out


def express(*, factor_deltas: Mapping[str, float], basis: FactorBasis,
            drivers_named: Sequence[str], driver_moves: Mapping[str, float] | None,
            exposures: Sequence[Exposure], universe: Mapping[str, Mapping[str, Any]],
            economies: Sequence[str] = (),
            max_instruments: int = 12) -> tuple[list[InstrumentForecast], list[dict[str, Any]]]:
    """Resolve an impact estimate into instruments the gateway can actually send an order for.

    Two routes, both measured, and the second is the one that saves commodity signals:

        factor route   the event's measured factor deltas times the basis loadings -- every
                       instrument in the basis carries an implied move.
        driver route   for an event NAMED against a driver instrument, the driver's own implied
                       move times each target's ADMITTED beta on that driver. This is the route
                       that takes a Brazilian soybean story to the tradeable currencies and
                       crosses that move with SOYBEAN, without anyone ever writing down that
                       Brazil exports beans.

    Returns (forecasts, blind_spots). A blind spot is a named dead end -- an economy or factor
    with no admitted tradeable expression -- and it is an acquisition decision, not an error.
    """
    scores: dict[str, float] = {}
    paths: dict[str, tuple[str, ...]] = {}
    ns: dict[str, int] = {}

    for fid, delta in factor_deltas.items():
        load = basis.loadings.get(fid)
        if not load or not math.isfinite(float(delta)):
            continue
        for sym, w in load.items():
            if sym not in universe:
                continue
            contrib = float(delta) * float(w)
            if abs(contrib) < 1e-9:
                continue
            if abs(contrib) > abs(scores.get(sym, 0.0)):
                paths[sym] = ("factor", fid, sym)
                ns[sym] = basis.n_obs
            scores[sym] = scores.get(sym, 0.0) + contrib

    by_driver: dict[str, list[Exposure]] = {}
    for e in exposures:
        if e.admitted:
            by_driver.setdefault(e.driver, []).append(e)

    for drv in drivers_named:
        move = None if driver_moves is None else driver_moves.get(drv)
        if move is None or not math.isfinite(float(move)):
            continue
        # The driver itself is the most direct expression there is.
        if drv in universe:
            scores[drv] = scores.get(drv, 0.0) + float(move)
            paths.setdefault(drv, ("named_driver", drv))
            ns.setdefault(drv, 0)
        for e in by_driver.get(drv, ()):
            contrib = float(move) * e.beta
            if abs(contrib) < 1e-9:
                continue
            if abs(contrib) > abs(scores.get(e.symbol, 0.0)):
                paths[e.symbol] = ("driver", drv, f"beta={e.beta:+.3f}", e.symbol)
                ns[e.symbol] = e.n
            scores[e.symbol] = scores.get(e.symbol, 0.0) + contrib

    forecasts = [
        InstrumentForecast(
            symbol=sym, expected_move_sigma=round(v, 6),
            confidence=round(min(1.0, abs(v)), 4), path=paths.get(sym, ("unknown",)),
            n=ns.get(sym, 0),
            status=Status.MEASURED if ns.get(sym, 0) > 0 else Status.RECORDED_ONLY)
        for sym, v in sorted(scores.items(), key=lambda kv: -abs(kv[1]))[:max_instruments]
        if abs(v) > 0.0
    ]

    blind: list[dict[str, Any]] = []
    tradeable_ccy = tradeable_currencies(universe)
    for eco in economies:
        code = eco.upper()
        if len(code) == 3 and code not in tradeable_ccy:
            reachable = bool(forecasts)
            blind.append({
                "economy": code,
                "direct_instrument": None,
                "resolved_via": ("measured driver/factor exposure" if reachable
                                 else "NOTHING -- dead end"),
                "note": (f"{code} is not quoted by this broker. "
                         + ("The impact was carried to tradeable instruments through measured "
                            "exposures, which is the intended path."
                            if reachable else
                            "No admitted exposure carried it anywhere: this event class is "
                            "currently INEXPRESSIBLE for this desk. Named as an acquisition / "
                            "research target rather than dropped.")),
            })
    if not forecasts:
        blind.append({
            "economy": None, "resolved_via": "NOTHING -- dead end",
            "note": ("no admitted factor loading and no admitted driver exposure produced a "
                     "tradeable expression; the event is RECORDED with no capital authority"),
        })
    return forecasts, blind


def expression_report(exposures: Sequence[Exposure],
                      universe: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """What the terms-of-trade map currently knows, and which instruments it cannot reach."""
    admitted = [e for e in exposures if e.admitted]
    reached = {e.symbol for e in admitted}
    tradeable = set(symbols_in_classes(universe, TARGET_CLASSES))
    return {
        "at": now_iso(),
        "cells_measured": len(exposures),
        "cells_admitted": len(admitted),
        "drivers": sorted({e.driver for e in exposures}),
        "top_exposures": [
            {"symbol": e.symbol, "driver": e.driver, "beta": e.beta,
             "ci": [e.ci_lo, e.ci_hi], "n": e.n}
            for e in sorted(admitted, key=lambda e: -abs(e.beta))[:25]],
        "instruments_with_no_admitted_driver_exposure": sorted(tradeable - reached)[:60],
        "n_instruments_unreached": len(tradeable - reached),
        "note": ("Every beta here is measured with a Bonferroni charge over every (target, "
                 "driver) cell ever tested. No commodity-to-currency link is written down "
                 "anywhere in this package; the map is what the data supports and it grows as "
                 "data accumulates."),
    }


def save_exposures(exposures: Sequence[Exposure], universe: Mapping[str, Mapping[str, Any]],
                   path: Path | str | None = None) -> None:
    payload = expression_report(exposures, universe)
    payload["exposures"] = [
        {"symbol": e.symbol, "driver": e.driver, "beta": e.beta, "se": e.se,
         "ci_lo": e.ci_lo, "ci_hi": e.ci_hi, "n": e.n, "cells": e.cells_charged,
         "admitted": e.admitted, "status": e.status}
        for e in exposures if e.admitted]
    write_json_atomic(Path(path) if path is not None else EXPOSURE_PATH, payload)
