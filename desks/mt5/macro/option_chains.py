#!/usr/bin/env python3
"""OPTION-CHAIN POSITIONING -- free delayed ETF chains as STATE for the CFDs they proxy.

CARDS. QG-OT-005 (free option chains -> put/call ratios, ATM IV, skew, dealer-gamma inputs for the
ETF proxies of CFD underlyings) and QG-ADH-001 (dealer-gamma sign as a continuation state). Both
were EXISTS_INCOMPLETE: `macro/market_state.py` names per-strike chains as an acquisition target
(CHAINS_BLOCKED) and `families_edge_queue.family_hedging_demand_close` says outright that the desk
has no options data. This organ is that data. OPTIONS NEVER TRADE HERE: every number below is a
risk-neutral (measure "Q") STATE feature of the mapped MT5 CFD and nothing else.

THE SOURCE, REGISTERED HONESTLY (`SOURCE`). CBOE's public delayed-quotes JSON,
`https://cdn.cboe.com/api/global/delayed_quotes/options/<SYM>.json`: public, no credential, ~15
minutes delayed; read and tested, never redistributed (the derived summaries stay on the box and
the raw body is not kept). Labelled the way `data/event_consensus_sources.json` labels its rows.

THE ASSUMED FORMAT (the cloud container that wrote this has no network; the parser was written
against `tests/fixtures/cboe_delayed_options_SPY.json`, built in this shape):

    {"timestamp": "2026-10-05 15:45:12",          # ET wall clock when naive (assumption)
     "data": {"symbol": "SPY", "current_price": 571.2, "close": ..., "iv30": ...,
              "options": [{"option": "SPY261016C00570000",   # OCC: root YYMMDD C|P strike*1000
                           "bid": 4.1, "ask": 4.2, "iv": 0.142, "open_interest": 1200,
                           "volume": 310, "delta": 0.52, "gamma": 0.031, ...}, ...]}}

TOLERANT, NEVER GUESSING. A body that is not that shape is PARSE_FAILED with the reason; a
contract whose symbol does not decode is skipped and counted; a missing greek is COMPUTED (see
below) and counted, never assumed; an IV quoted in percent (median > 3, i.e. >300% vol as a
decimal, impossible for these ETFs) is rescaled and the rescale is recorded on the snapshot.

PIT. knowable_at is the snapshot's own printed `timestamp` (knowable_basis printed_stamp); a
naive stamp is read as America/New_York. A stamp later than our receipt (a wrong timezone
assumption) or no stamp at all falls back to receipt (bounded_by_receipt). Open interest in a
delayed chain is the PRIOR session's end-of-day figure (OCC publishes it overnight) -- it is
knowable at the snapshot, and its as-of date is recorded so nobody reads it as intraday OI. Time
to expiry runs from the QUOTE stamp, never from a wall clock (card QG-ADH-003).

FEATURES per ETF per snapshot (all measure "Q"):
  pc_oi_ratio, pc_volume_ratio    put / call over every listed expiry
  atm_iv_front, atm_iv_30d        ATM IV of the front expiry (first with >= MIN_FRONT_DTE days)
                                  and 30-day ATM IV interpolated in total variance (never
                                  extrapolated: outside the listed tenors it is UNMEASURED)
  skew_90_110                     IV(0.9 S) - IV(1.1 S) on the front expiry's OTM smile
  rr25                            IV(25-delta call) - IV(25-delta put), front expiry
  term_slope                      ATM IV(90d) - ATM IV(30d) (second - front when 90d is absent)
  gex                             sum OI x gamma x S^2 x 0.01 x 100 x (+1 call, -1 put): dealer
                                  dollar gamma per 1% move UNDER THE STANDARD CONVENTION that
                                  dealers are long the calls and short the puts customers trade
                                  (`DEALER_CONVENTION`, stated on every output; card QG-ADH-001
                                  lists it as a selection risk)
  gex_sign, gamma_flip            sign, and the spot at which the convention's dealer gamma
                                  changes sign (nearest crossing within +-20% of spot)

GREEKS. CBOE carries per-contract iv/delta/gamma; where one is absent it is computed by the
TEMPORARY private Black-Scholes `_bs` below (libs/quant_models is being built in parallel; this
helper is marked for replacement and tested for put-call parity and gamma = pdf, the two defects
the Q-Fin donor shipped).

BUDGET. One snapshot per symbol per REFETCH_S (6h, state file), TIMEOUT_S per fetch, and only
derived per-expiry summaries plus the front two expiries' strikes within +-10% of spot are kept,
gzip JSON under data/option_chains/<ETF>/ (gitignored box-local state).

CONTRACTS (libs.research.sensor_engines). Both read UNMEASURED until the box accrues history, which
is correct: the archive is forward-only (card QG-OT-005 weakness).
  QG-ADH-001  gated_gain of a 1-day momentum base cell on the mapped CFD gated on gex < 0, with the
              continuation-rate difference GEX<0 vs GEX>0 and its two-sided p beside it (n>=250).
  QG-OT-005   forecast_gain of next-21d realised vol: expanding out-of-sample OLS on (IV index,
              chain features) against the same OLS on the IV index alone (VIX/GVZ/OVX/VXN/EVZ).

    python desks/mt5/macro/option_chains.py [--no-fetch] [--dry-run] [--symbols SPY,GLD]
"""
from __future__ import annotations

import argparse
import bisect
import gzip
import itertools
import json
import math
import os
import re
import sys
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import sensor_contract as sc  # noqa: E402
from libs.research import sensor_engines as se  # noqa: E402

ENGINE = "option_chains"
REPORT = DESK / "reports" / "OPTION_CHAINS.json"
DATA = DESK / "data" / "option_chains"
UNIVERSE = DESK / "data" / "universe" / "universe.json"
VOL_REFERENCE = DESK / "data" / "vol_archive" / "reference"
ET = ZoneInfo("America/New_York")
UNMEASURED = "UNMEASURED"
MEASURE = "Q"
URL = "https://cdn.cboe.com/api/global/delayed_quotes/options/{sym}.json"
UA = "Mozilla/5.0 (MT5 research desk; point-in-time option-chain state)"
#: One snapshot per symbol at most this often (attempts count, so a failing source is not hammered).
REFETCH_S = 6 * 3600
TIMEOUT_S = 20
MAX_BODY = 40 * 1024 * 1024
#: The front expiry is the first with at least this many days: 0-6 DTE smiles are pin noise.
MIN_FRONT_DTE = 7
#: Strikes kept per snapshot: the front two expiries within this distance of spot.
KEEP_MONEYNESS = 0.10
#: Gamma-flip search band and step, as fractions of spot.
FLIP_BAND = 0.20
FLIP_STEP = 0.0025
#: Realised-vol horizon of the QG-OT-005 forecast contract, trading days.
RV_HORIZON = 21
MIN_TRAIN = 60
#: The CFD trade from close(d) is gated by the latest state available by d at this UTC hour --
#: before the broker's daily close (21:00-22:00 UTC) in both DST seasons.
CUT_HOUR_UTC = 20

DEALER_CONVENTION = ("dealer gamma sign convention: customers buy puts and sell calls, so dealers "
                     "are LONG calls (+1) and SHORT puts (-1); GEX is that book's dollar gamma "
                     "per 1% move. It is a convention, not an observation (card QG-ADH-001 "
                     "selection risk)")

SOURCE: dict[str, Any] = {
    "id": "cboe_delayed_quotes_options",
    "name": "CBOE delayed quotes, per-ETF option chain JSON",
    "url": URL,
    "access": "public",
    "machine_use_allowed": True,
    "redistribute_allowed": False,
    "licence": ("public delayed (~15 min) quotes published by Cboe on its CDN; numbers are read "
                "and tested on this desk, the chain itself is not redistributed and the raw body "
                "is not kept"),
    "refetch_s": REFETCH_S,
    "timeout_s": TIMEOUT_S,
    "format": ("ASSUMED (written offline against a constructed fixture): top-level `timestamp` "
               "and `data` {current_price, options:[{option (OCC symbol), bid, ask, iv, "
               "open_interest, volume, delta, gamma}]}; anything else is PARSE_FAILED"),
}

CARD_ADH001_FALSIFIER = ("no difference in continuation rate between GEX<0 and GEX>0 days "
                         "(two-sided, n>=250 days)")
CARD_OT005_FALSIFIER = ("no incremental predictive power over VIX/GVZ/OVX levels after 250 "
                        "forward observations")


@dataclass(frozen=True)
class Proxy:
    """One ETF and the MT5 instrument its chain is a state of."""

    etf: str
    candidates: tuple[str, ...]
    vol_index: str = ""
    #: -1 when the ETF moves against the CFD's quote (FXY is yen in dollars; USDJPY is the inverse).
    orientation: int = 1
    note: str = ""


PROXIES: tuple[Proxy, ...] = (
    Proxy("SPY", ("US500", "SPX500", "USA500", "US500.cash"), "^VIX"),
    Proxy("QQQ", ("NAS100", "USTEC", "NDX", "USTEC.cash"), "^VXN"),
    Proxy("IWM", ("US2000", "RUSSELL2000", "RUS2000", "US2000.cash")),
    Proxy("GLD", ("XAUUSD", "GOLD"), "^GVZ"),
    Proxy("SLV", ("XAGUSD", "SILVER")),
    Proxy("USO", ("USOIL", "XTIUSD", "WTI"), "^OVX"),
    Proxy("UNG", ("XNGUSD", "NATGAS", "NGAS")),
    Proxy("TLT", ("UST30Y", "USTBOND", "UST10Y"),
          note="TLT is 20y+ Treasuries; a 10y CFD is a duration-mismatched proxy"),
    Proxy("UUP", ("USDX", "DXY", "USDINDEX")),
    Proxy("FXE", ("EURUSD",), "^EVZ"),
    Proxy("FXY", ("USDJPY",), orientation=-1,
          note="FXY rises when the yen strengthens, i.e. when USDJPY falls"),
)
BY_ETF: dict[str, Proxy] = {p.etf: p for p in PROXIES}
#: The card's dealer-gamma candidates (QG-ADH-001).
GEX_CARD_ETFS: tuple[str, ...] = ("SPY", "QQQ", "IWM", "GLD")


def series_id(etf: str) -> str:
    return f"ws_optchain_{etf.lower()}"


# ============================================================================== helpers
def _f(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _iso(when: datetime) -> str:
    return when.astimezone(UTC).isoformat(timespec="seconds")


def _atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def load_registry(path: Path = UNIVERSE) -> dict[str, dict[str, Any]]:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(doc, dict):
        return {}
    return {str(k).upper(): v for k, v in doc.items() if isinstance(v, dict)}


def resolve(proxy: Proxy, registry: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """The first candidate this account lists wins; none listed is NOT_TRADEABLE_HERE."""
    for cand in proxy.candidates:
        row = registry.get(cand.upper())
        if row is not None:
            return {"etf": proxy.etf, "mt5_symbol": str(row.get("symbol") or cand),
                    "status": "TRADEABLE", "orientation": proxy.orientation,
                    "vol_index": proxy.vol_index, "note": proxy.note}
    return {"etf": proxy.etf, "mt5_symbol": None, "status": "NOT_TRADEABLE_HERE",
            "tried": list(proxy.candidates), "vol_index": proxy.vol_index,
            "why": f"none of {', '.join(proxy.candidates)} is listed in universe.json"}


# ============================================================================== Black-Scholes
# TEMPORARY -- replace with libs.quant_models (being built in parallel) when it lands in this
# tree. Private on purpose so nothing outside this module grows a dependency on it. Tested for
# put-call parity and gamma = pdf(d1)/(S sigma sqrt T) (the Q-Fin donor used the cdf).
def _ncdf(x: float) -> float:
    return 0.5 * math.erfc(-x / math.sqrt(2.0))


def _npdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _bs(S: float, K: float, T: float, sigma: float, cp: str, r: float = 0.0,
        q: float = 0.0) -> dict[str, float] | None:
    """TEMPORARY Black-Scholes-Merton price, delta and gamma. None outside the model's domain."""
    if not (S > 0 and K > 0 and T > 0 and sigma > 0):
        return None
    sq = sigma * math.sqrt(T)
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / sq
    d2 = d1 - sq
    dq, dr = math.exp(-q * T), math.exp(-r * T)
    gamma = dq * _npdf(d1) / (S * sq)
    if cp == "C":
        price = S * dq * _ncdf(d1) - K * dr * _ncdf(d2)
        delta = dq * _ncdf(d1)
    else:
        price = K * dr * _ncdf(-d2) - S * dq * _ncdf(-d1)
        delta = dq * (_ncdf(d1) - 1.0)
    return {"price": price, "delta": delta, "gamma": gamma}


def _implied_vol(price: float, S: float, K: float, T: float, cp: str, r: float = 0.0,
                 q: float = 0.0) -> float | None:
    """TEMPORARY bisection IV; None when the price is outside the no-arbitrage band."""
    lo, hi = 1e-4, 5.0
    plo, phi = _bs(S, K, T, lo, cp, r, q), _bs(S, K, T, hi, cp, r, q)
    if plo is None or phi is None or not (plo["price"] <= price <= phi["price"]):
        return None
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        pm = _bs(S, K, T, mid, cp, r, q)
        if pm is None:
            return None
        if pm["price"] < price:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-7:
            break
    return 0.5 * (lo + hi)


# ============================================================================== parsing
_OCC = re.compile(r"^(?P<root>[A-Z][A-Z0-9.]{0,5}?)\s*(?P<ymd>\d{6})(?P<cp>[CP])(?P<k>\d{8})$")


def parse_contract(symbol: str) -> tuple[date, str, float] | None:
    """(expiry, 'C'|'P', strike) from an OCC option symbol, or None."""
    m = _OCC.match(str(symbol or "").strip().upper())
    if m is None:
        return None
    ymd = m.group("ymd")
    try:
        exp = date(2000 + int(ymd[:2]), int(ymd[2:4]), int(ymd[4:]))
    except ValueError:
        return None
    strike = int(m.group("k")) / 1000.0
    return (exp, m.group("cp"), strike) if strike > 0 else None


def _stamp(value: Any) -> datetime | None:
    """A printed stamp as UTC. Naive stamps are CBOE's ET wall clock (the declared assumption)."""
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        v = float(value) / (1000.0 if float(value) > 1e11 else 1.0)
        return datetime.fromtimestamp(v, tz=UTC)
    text = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=ET)).astimezone(UTC)


def _expiry_instant(exp: date) -> datetime:
    return datetime.combine(exp, time(16, 0), tzinfo=ET).astimezone(UTC)


def parse_chain(doc: Any, *, etf: str, received_at: datetime, r: float = 0.0) -> dict[str, Any]:
    """The chain as typed contracts with the PIT stamp, or PARSE_FAILED with the reason."""
    def fail(why: str) -> dict[str, Any]:
        return {"status": "PARSE_FAILED", "etf": etf, "why": why,
                "received_at": _iso(received_at)}

    if not isinstance(doc, Mapping):
        return fail(f"body is {type(doc).__name__}, not an object")
    data = doc.get("data")
    if not isinstance(data, Mapping):
        return fail("no `data` object")
    options = data.get("options")
    if not isinstance(options, list) or not options:
        return fail("`data.options` is not a non-empty list")
    spot = next((v for v in (_f(data.get(k)) for k in ("current_price", "close",
                                                      "last_trade_price", "prev_day_close"))
                 if v is not None and v > 0), None)
    if spot is None:
        return fail("no positive spot in current_price/close/last_trade_price")
    # ---- the PIT stamp
    printed = _stamp(doc.get("timestamp")) or _stamp(data.get("last_trade_time"))
    rx = received_at.astimezone(UTC).replace(microsecond=0)
    if printed is not None and printed <= rx + timedelta(seconds=60):
        knowable, basis, pit_note = printed.replace(microsecond=0), "printed_stamp", ""
        knowable = min(knowable, rx)
    else:
        knowable, basis = rx, "bounded_by_receipt"
        pit_note = ("no printed stamp" if printed is None else
                    "printed stamp is later than receipt (timezone assumption wrong?): bounded "
                    "by receipt instead")
    quote_time = knowable if basis == "printed_stamp" else rx
    # ---- contracts
    raw: list[dict[str, Any]] = []
    skipped = 0
    for opt in options:
        if not isinstance(opt, Mapping):
            skipped += 1
            continue
        got = parse_contract(str(opt.get("option") or opt.get("symbol") or ""))
        if got is None:
            skipped += 1
            continue
        exp, cp, k = got
        raw.append({"expiry": exp, "cp": cp, "strike": k, "iv": _f(opt.get("iv")),
                    "delta": _f(opt.get("delta")), "gamma": _f(opt.get("gamma")),
                    "oi": _f(opt.get("open_interest")) or 0.0,
                    "volume": _f(opt.get("volume")) or 0.0,
                    "bid": _f(opt.get("bid")), "ask": _f(opt.get("ask"))})
    if not raw:
        return fail(f"none of {len(options)} contract symbols decoded as OCC")
    ivs = [c["iv"] for c in raw if c["iv"] is not None and c["iv"] > 0]
    iv_unit = "decimal"
    if ivs and float(np.median(ivs)) > 3.0:
        iv_unit = "percent_rescaled"
        for c in raw:
            if c["iv"] is not None:
                c["iv"] = c["iv"] / 100.0
    # ---- greeks: CBOE's where present, the TEMPORARY _bs where absent (counted)
    filled = {"iv_from_mid": 0, "delta_bs": 0, "gamma_bs": 0}
    contracts: list[dict[str, Any]] = []
    for c in raw:
        T = (_expiry_instant(c["expiry"]) - quote_time).total_seconds() / (365.0 * 86400.0)
        if T <= 0:
            skipped += 1
            continue
        c["T"] = T
        if (c["iv"] is None or c["iv"] <= 0) and c["bid"] is not None and c["ask"] is not None \
                and 0 < c["bid"] <= c["ask"]:
            c["iv"] = _implied_vol(0.5 * (c["bid"] + c["ask"]), spot, c["strike"], T, c["cp"], r)
            filled["iv_from_mid"] += int(c["iv"] is not None)
        if c["iv"] is not None and c["iv"] > 0:
            g = _bs(spot, c["strike"], T, c["iv"], c["cp"], r)
            if g is not None:
                if c["gamma"] is None:
                    c["gamma"] = g["gamma"]
                    filled["gamma_bs"] += 1
                if c["delta"] is None:
                    c["delta"] = g["delta"]
                    filled["delta_bs"] += 1
        else:
            c["iv"] = None
        contracts.append(c)
    if not contracts:
        return fail("every decoded contract had expired at the quote stamp")
    return {"status": "PARSED", "etf": etf, "spot": spot, "quote_time": _iso(quote_time),
            "knowable_at": _iso(knowable), "knowable_basis": basis, "pit_note": pit_note,
            "received_at": _iso(rx),
            "oi_as_of": "prior session end-of-day (OCC overnight publication)",
            "iv_unit": iv_unit, "greeks_filled": filled, "n_raw": len(options),
            "n_parsed": len(contracts), "n_skipped": skipped, "contracts": contracts}


# ============================================================================== features
def _smile(cs: Sequence[Mapping[str, Any]], spot: float) -> tuple[np.ndarray, np.ndarray]:
    """The OTM smile of one expiry: puts at or below spot, calls at or above, averaged at a tie."""
    pts: dict[float, list[float]] = {}
    for c in cs:
        iv = c.get("iv")
        if iv is None or iv <= 0:
            continue
        k = float(c["strike"])
        if (c["cp"] == "P" and k <= spot) or (c["cp"] == "C" and k >= spot):
            pts.setdefault(k, []).append(float(iv))
    ks = np.asarray(sorted(pts), dtype=float)
    return ks, np.asarray([sum(pts[k]) / len(pts[k]) for k in ks], dtype=float)


def _smile_at(ks: np.ndarray, ivs: np.ndarray, x: float) -> float | None:
    """Linear in strike inside the quoted range; never extrapolated."""
    if ks.size == 0 or x < ks[0] or x > ks[-1]:
        return None
    return float(np.interp(x, ks, ivs))


def _atm(cs: Sequence[Mapping[str, Any]], spot: float) -> float | None:
    ks, ivs = _smile(cs, spot)
    got = _smile_at(ks, ivs, spot)
    if got is not None:
        return got
    # spot outside the OTM range: the nearest-strike call/put average, if quoted on both sides
    near = [c for c in cs if c.get("iv")]
    if not near:
        return None
    k0 = min(near, key=lambda c: abs(float(c["strike"]) - spot))["strike"]
    at = [float(c["iv"]) for c in near if c["strike"] == k0]
    return sum(at) / len(at) if abs(k0 / spot - 1.0) <= 0.02 else None


def _tenor_iv(points: Sequence[tuple[float, float]], days: float) -> float | None:
    """ATM IV at `days`, linear in total variance between the bracketing expiries."""
    t = days / 365.0
    pts = sorted(points)
    for (t1, v1), (t2, v2) in itertools.pairwise(pts):
        if t1 <= t <= t2 and t2 > t1:
            w = v1 * v1 * t1 + (v2 * v2 * t2 - v1 * v1 * t1) * (t - t1) / (t2 - t1)
            return math.sqrt(w / t) if w > 0 else None
    return next((v for tt, v in pts if abs(tt - t) < 1e-9), None)


def _rr25(cs: Sequence[Mapping[str, Any]]) -> float | None:
    calls = [c for c in cs if c["cp"] == "C" and c.get("delta") is not None and c.get("iv")]
    puts = [c for c in cs if c["cp"] == "P" and c.get("delta") is not None and c.get("iv")]
    if not calls or not puts:
        return None
    c25 = min(calls, key=lambda c: abs(float(c["delta"]) - 0.25))
    p25 = min(puts, key=lambda c: abs(float(c["delta"]) + 0.25))
    if abs(float(c25["delta"]) - 0.25) > 0.10 or abs(float(p25["delta"]) + 0.25) > 0.10:
        return None
    return float(c25["iv"]) - float(p25["iv"])


def _gex(cs: Sequence[Mapping[str, Any]], spot: float, *, recompute: bool = False,
         r: float = 0.0) -> float:
    """Dollar gamma per 1% move under DEALER_CONVENTION. 100 = equity option multiplier."""
    total = 0.0
    for c in cs:
        oi = float(c.get("oi") or 0.0)
        if oi <= 0:
            continue
        if recompute:
            if not c.get("iv"):
                continue
            g = _bs(spot, float(c["strike"]), float(c["T"]), float(c["iv"]), c["cp"], r)
            gamma = g["gamma"] if g else 0.0
        else:
            gamma = float(c.get("gamma") or 0.0)
        total += oi * gamma * spot * spot * 0.01 * 100.0 * (1.0 if c["cp"] == "C" else -1.0)
    return total


def gamma_flip(cs: Sequence[Mapping[str, Any]], spot: float, r: float = 0.0) -> float | None:
    """The spot nearest the current one at which convention GEX (recomputed by `_bs` at each
    hypothetical spot, each contract at its own IV) changes sign; None inside no crossing."""
    grid = spot * (1.0 + np.arange(-FLIP_BAND, FLIP_BAND + 1e-12, FLIP_STEP))
    vals = np.asarray([_gex(cs, float(s), recompute=True, r=r) for s in grid], dtype=float)
    best: float | None = None
    for i in range(grid.size - 1):
        a, b = vals[i], vals[i + 1]
        if a == 0.0 or a * b < 0:
            x = float(grid[i]) if a == 0.0 else float(
                grid[i] + (grid[i + 1] - grid[i]) * (-a) / (b - a))
            if best is None or abs(x - spot) < abs(best - spot):
                best = x
    return best


def features(chain: Mapping[str, Any], r: float = 0.0) -> dict[str, Any]:
    """Every feature of one parsed snapshot, plus the per-expiry summaries kept on disk."""
    spot = float(chain["spot"])
    cs = list(chain["contracts"])
    by_exp: dict[date, list[dict[str, Any]]] = {}
    for c in cs:
        by_exp.setdefault(c["expiry"], []).append(c)
    summaries: list[dict[str, Any]] = []
    tenor_pts: list[tuple[float, float]] = []
    for exp in sorted(by_exp):
        group = by_exp[exp]
        ks, ivs = _smile(group, spot)
        atm = _atm(group, spot)
        T = float(group[0]["T"])
        if atm is not None:
            tenor_pts.append((T, atm))
        summaries.append({
            "expiry": exp.isoformat(), "dte": round(T * 365.0, 3), "n": len(group),
            "call_oi": sum(c["oi"] for c in group if c["cp"] == "C"),
            "put_oi": sum(c["oi"] for c in group if c["cp"] == "P"),
            "call_volume": sum(c["volume"] for c in group if c["cp"] == "C"),
            "put_volume": sum(c["volume"] for c in group if c["cp"] == "P"),
            "atm_iv": atm, "iv_90": _smile_at(ks, ivs, 0.9 * spot),
            "iv_110": _smile_at(ks, ivs, 1.1 * spot), "rr25": _rr25(group),
            "gex": _gex(group, spot)})
    fronts = [s for s in summaries if s["dte"] >= MIN_FRONT_DTE]
    front = fronts[0] if fronts else None
    second = fronts[1] if len(fronts) > 1 else None
    call_oi = sum(s["call_oi"] for s in summaries)
    put_oi = sum(s["put_oi"] for s in summaries)
    call_v = sum(s["call_volume"] for s in summaries)
    put_v = sum(s["put_volume"] for s in summaries)
    iv30, iv90 = _tenor_iv(tenor_pts, 30.0), _tenor_iv(tenor_pts, 90.0)
    term = (iv90 - iv30 if iv30 is not None and iv90 is not None else
            (second["atm_iv"] - front["atm_iv"]) if front and second and front["atm_iv"]
            is not None and second["atm_iv"] is not None else None)
    skew = (front["iv_90"] - front["iv_110"] if front and front["iv_90"] is not None
            and front["iv_110"] is not None else None)
    gex = _gex(cs, spot)
    flip = gamma_flip(cs, spot, r)
    feats: dict[str, Any] = {
        "spot": spot,
        "pc_oi_ratio": put_oi / call_oi if call_oi > 0 else None,
        "pc_volume_ratio": put_v / call_v if call_v > 0 else None,
        "atm_iv_front": front["atm_iv"] if front else None,
        "atm_iv_30d": iv30,
        "skew_90_110": skew,
        "rr25": front["rr25"] if front else None,
        "term_slope": term,
        "gex": gex,
        "gex_bn": gex / 1e9,
        "gex_sign": float(np.sign(gex)) if gex != 0 else 0.0,
        "gamma_flip": flip,
        "flip_distance": (flip / spot - 1.0) if flip is not None else None,
    }
    front_two = {s["expiry"] for s in fronts[:2]}
    kept = [{k: (v.isoformat() if isinstance(v, date) else v) for k, v in c.items()}
            for c in cs if c["expiry"].isoformat() in front_two
            and abs(float(c["strike"]) / spot - 1.0) <= KEEP_MONEYNESS]
    return {"features": feats, "expiries": summaries, "front_strikes": kept,
            "front_expiry": front["expiry"] if front else None,
            "measure": MEASURE, "dealer_convention": DEALER_CONVENTION}


#: The numeric columns of the lake series, in order.
FEATURE_COLS: tuple[str, ...] = ("spot", "pc_oi_ratio", "pc_volume_ratio", "atm_iv_front",
                                 "atm_iv_30d", "skew_90_110", "rr25", "term_slope", "gex",
                                 "gex_bn", "gex_sign", "gamma_flip", "flip_distance")


# ============================================================================== fetch + archive
def fetch_chain(etf: str, timeout: float = TIMEOUT_S) -> tuple[Any, str]:
    """(parsed JSON body or None, status). Public CDN, no credential, bounded body."""
    try:
        req = urllib.request.Request(URL.format(sym=etf), headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(MAX_BODY + 1)
        if len(body) > MAX_BODY:
            return None, "FETCH_FAILED: body over MAX_BODY"
        return json.loads(body), "OK"
    except Exception as exc:
        return None, f"FETCH_FAILED: {type(exc).__name__}: {str(exc)[:120]}"


def load_state(data_dir: Path) -> dict[str, Any]:
    try:
        doc = json.loads((data_dir / "state.json").read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def due(state: Mapping[str, Any], etf: str, now: datetime) -> bool:
    last = sc.parse_time((state.get(etf) or {}).get("last_attempt"))
    return last is None or (now - last).total_seconds() >= REFETCH_S


def save_snapshot(data_dir: Path, chain: Mapping[str, Any], feats: Mapping[str, Any]) -> Path:
    stamp = str(chain["quote_time"]).replace("-", "").replace(":", "").replace("+0000", "Z")
    path = data_dir / str(chain["etf"]) / f"{stamp[:15]}Z.json.gz"
    doc = {k: v for k, v in chain.items() if k != "contracts"}
    doc.update({"source": SOURCE["id"], **feats})
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as fh:
        json.dump(doc, fh, default=str)
    os.replace(tmp, path)
    return path


def history(data_dir: Path, etf: str) -> list[dict[str, Any]]:
    path = data_dir / f"features_{etf.lower()}.jsonl"
    if not path.exists():
        return []
    out = []
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict):
                out.append(row)
    return out


def append_history(data_dir: Path, etf: str, row: Mapping[str, Any]) -> None:
    path = data_dir / f"features_{etf.lower()}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(dict(row), sort_keys=True, default=str) + "\n")


def feature_row(chain: Mapping[str, Any], feats: Mapping[str, Any], mt5: str | None
                ) -> dict[str, Any]:
    return {"available_time": chain["knowable_at"], "event_time": chain["quote_time"],
            "received_at": chain["received_at"], "knowable_basis": chain["knowable_basis"],
            "source_id": SOURCE["id"], "etf": chain["etf"], "mt5_symbol": mt5 or "",
            "measure": MEASURE, **{k: feats["features"].get(k) for k in FEATURE_COLS}}


# ============================================================================== contracts
def _cut(day: str) -> datetime:
    d = date.fromisoformat(day[:10])
    return datetime(d.year, d.month, d.day, CUT_HOUR_UTC, tzinfo=UTC)


def state_asof(rows: Sequence[Mapping[str, Any]], col: str
               ) -> tuple[list[datetime], list[float]]:
    pts = []
    for r in rows:
        t, v = sc.parse_time(r.get("available_time")), _f(r.get(col))
        if t is not None and v is not None:
            pts.append((t, v))
    pts.sort()
    return [p[0] for p in pts], [p[1] for p in pts]


def _latest(times: Sequence[datetime], vals: Sequence[float], at: datetime) -> float | None:
    i = bisect.bisect_right(times, at) - 1
    return vals[i] if i >= 0 else None


def _two_prop_p(k1: int, n1: int, k2: int, n2: int) -> float | None:
    if min(n1, n2) < 2:
        return None
    p = (k1 + k2) / (n1 + n2)
    sd = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    if sd <= 0:
        return None
    z = (k1 / n1 - k2 / n2) / sd
    return round(math.erfc(abs(z) / math.sqrt(2.0)), 6)


def gex_continuation_contract(rows: Sequence[Mapping[str, Any]],
                              closes: Sequence[tuple[str, float]], *, etf: str, symbol: str,
                              min_n: int = se.MIN_N) -> dict[str, Any]:
    """QG-ADH-001: the 1-day momentum base cell on `symbol` gated on GEX < 0.

    Day d's payoff is sign(r_{d-1}) x r_d (close-to-close), entered at close(d-1); the gate is the
    latest GEX AVAILABLE by d-1's cut, so the state precedes the entry. Days with no state yet are
    not days of the test. Beside the Kelly gain: the continuation rates in the two regimes and
    the card's two-sided difference p."""
    times, vals = state_asof(rows, "gex")
    pay, gate, strata = [], [], []
    k_neg = n_neg = k_pos = n_pos = 0
    rets = [(closes[i][0], math.log(closes[i][1] / closes[i - 1][1]))
            for i in range(1, len(closes))]
    rv: list[float | None] = []
    for i in range(len(rets)):
        win = [x[1] for x in rets[max(0, i - 21):i]]
        rv.append(float(np.std(win, ddof=1)) if len(win) >= 10 else None)
    finite_rv = [v for v in rv if v is not None]
    qs = ([float(x) for x in np.quantile(finite_rv, [1 / 3, 2 / 3])]
          if len(finite_rv) >= 30 else [])
    for i in range(1, len(rets)):
        g = _latest(times, vals, _cut(rets[i - 1][0]))
        if g is None:
            continue
        prev, cur = rets[i - 1][1], rets[i][1]
        if prev == 0:
            continue
        pay.append(math.copysign(1.0, prev) * cur)
        gate.append(g < 0)
        cont = int(math.copysign(1.0, prev) == math.copysign(1.0, cur) and cur != 0)
        if g < 0:
            n_neg += 1
            k_neg += cont
        elif g > 0:
            n_pos += 1
            k_pos += cont
        v = rv[i - 1]
        strata.append(None if v is None or not qs else
                      (0 if v <= qs[0] else 1 if v <= qs[1] else 2))
    row = se.gated_gain(pay, gate, engine=ENGINE, cards=["QG-ADH-001"],
                        falsifier=CARD_ADH001_FALSIFIER,
                        baseline=(f"1-day momentum base cell on {symbol}, ungated (card H arm: "
                                  "hedging_demand_close require_elevated_vol)"),
                        strata=strata if qs else None, min_n=min_n)
    row.update({"label": f"{etf}->{symbol} gex<0 continuation", "etf": etf, "symbol": symbol,
                "measure": MEASURE, "dealer_convention": DEALER_CONVENTION,
                "continuation_rate_gex_neg": round(k_neg / n_neg, 4) if n_neg else None,
                "continuation_rate_gex_pos": round(k_pos / n_pos, 4) if n_pos else None,
                "n_gex_neg": n_neg, "n_gex_pos": n_pos,
                "continuation_diff_p_two_sided": _two_prop_p(k_neg, n_neg, k_pos, n_pos)})
    return row


def _ols_forecast(X: np.ndarray, y: np.ndarray, gap: int, min_train: int) -> np.ndarray:
    """Expanding out-of-sample OLS: row i is forecast from rows j <= i - gap - 1 only (their
    targets were fully realised before row i's decision)."""
    out = np.full(y.size, np.nan)
    for i in range(y.size):
        m = i - gap
        if m < min_train:
            continue
        beta, *_ = np.linalg.lstsq(X[:m], y[:m], rcond=None)
        out[i] = float(X[i] @ beta)
    return out


def vol_forecast_contract(rows: Sequence[Mapping[str, Any]],
                          closes: Sequence[tuple[str, float]],
                          iv_index: Mapping[str, float], *, etf: str, symbol: str,
                          vol_index: str, min_n: int = se.MIN_N,
                          chain_cols: Sequence[str] = ("atm_iv_30d", "skew_90_110",
                                                       "pc_oi_ratio")) -> dict[str, Any]:
    """QG-OT-005: does the chain add to the IV index in forecasting next-21d realised vol?"""
    states = {c: state_asof(rows, c) for c in chain_cols}
    idx_dates = sorted(iv_index)
    rets = [math.log(closes[i][1] / closes[i - 1][1]) for i in range(1, len(closes))]
    days = [closes[i][0] for i in range(1, len(closes))]
    xb, xm, ys = [], [], []
    for i, day in enumerate(days):
        if i + RV_HORIZON >= len(rets):
            break
        cut = _cut(day)
        # the index close of date x is knowable x+1 01:00 UTC (PIT law)
        j = bisect.bisect_right(idx_dates, (cut - timedelta(hours=25)).date().isoformat()) - 1
        if j < 0:
            continue
        lvl = _f(iv_index[idx_dates[j]])
        feats = [_latest(*states[c], cut) for c in chain_cols]
        if lvl is None or any(v is None for v in feats):
            continue
        fut = rets[i + 1:i + 1 + RV_HORIZON]
        ys.append(float(np.std(fut, ddof=1)) * math.sqrt(252.0) * 100.0)
        xb.append([1.0, lvl])
        xm.append([1.0, lvl, *[float(v) for v in feats if v is not None]])
    y = np.asarray(ys, dtype=float)
    base = _ols_forecast(np.asarray(xb, dtype=float).reshape(-1, 2), y, RV_HORIZON, MIN_TRAIN)
    model = _ols_forecast(np.asarray(xm, dtype=float).reshape(-1, 2 + len(chain_cols)), y,
                          RV_HORIZON, MIN_TRAIN)
    row = se.forecast_gain(y, model, base, engine=ENGINE, cards=["QG-OT-005"],
                           falsifier=CARD_OT005_FALSIFIER,
                           baseline=f"expanding OLS on {vol_index} level alone (vol_archive)",
                           min_n=min_n)
    row.update({"label": f"{etf}->{symbol} next-{RV_HORIZON}d realised vol", "etf": etf,
                "symbol": symbol, "vol_index": vol_index, "chain_features": list(chain_cols),
                "measure": MEASURE, "n_rows_joined": int(y.size)})
    return row


# ============================================================================== box readers
def bars_daily(symbol: str, now: datetime) -> list[tuple[str, float]]:
    """Daily closes of `symbol` from the desk's bar store, through market_state's one reader."""
    try:
        from macro import market_state as ms
        return ms.daily_closes(ms._chart(symbol), now)
    except Exception:
        return []


def vol_index_series(ticker: str, root: Path = VOL_REFERENCE) -> dict[str, float]:
    """{date: level} from vol_archive's reference history and its own observations."""
    out: dict[str, float] = {}
    try:
        doc = json.loads((root / f"{ticker}.json").read_text("utf-8"))
        for k, v in ((doc or {}).get("series") or {}).items():
            fv = _f(v)
            if fv is not None:
                out[str(k)[:10]] = fv
    except (OSError, ValueError, AttributeError):
        pass
    try:
        from macro import market_state as ms
        for r in ms.read_vol_archive():
            if r.get("vol_ticker") == ticker and _f(r.get("implied_vol")) is not None:
                out[str(r.get("value_date"))[:10]] = float(r["implied_vol"])
    except Exception:
        pass
    return out


# ============================================================================== the organ
def _ledger_rows(row: Mapping[str, Any], hist: Sequence[Mapping[str, Any]], symbol: str
                 ) -> list[Any]:
    from macro import market_state as ms
    out = []
    for metric in ("gex", "pc_oi_ratio", "skew_90_110", "atm_iv_30d", "rr25", "gamma_flip"):
        v = _f(row.get(metric))
        if v is None:
            continue
        past = [x for x in (_f(h.get(metric)) for h in hist[:-1]) if x is not None]
        out.append(sc.make(
            sensor_id=f"{ENGINE}:{row['etf']}", source_id=SOURCE["id"], metric=metric,
            entity=symbol, kind="state", sensor_class="options_positioning",
            asset_domain="options_implied", value=v, event_time=row["event_time"],
            knowable_at=row["available_time"], knowable_basis=row["knowable_basis"],
            received_at=row["received_at"], percentile=ms.percentile(past, v),
            surprise_z=ms.zscore(past, v), licence=SOURCE["licence"],
            commercial_rights="read and tested, not redistributed",
            attributes={"measure": MEASURE, "etf": row["etf"],
                        "dealer_convention": DEALER_CONVENTION if "gex" in metric
                        or metric == "gamma_flip" else ""}))
    return out


def run(*, now: datetime, fetch: bool = True, fetcher: Callable[[str], tuple[Any, str]] | None
        = None, etfs: Sequence[str] | None = None, data_dir: Path = DATA,
        registry: Mapping[str, Mapping[str, Any]] | None = None,
        closes_fn: Callable[[str, datetime], list[tuple[str, float]]] | None = None,
        vol_index_fn: Callable[[str], Mapping[str, float]] | None = None,
        lake_root: Path | None = None, contracts_root: Path | None = None,
        ledger: Any = None, report: Path | None = REPORT, dry_run: bool = False,
        emit_cells: bool = True, min_n: int = se.MIN_N) -> dict[str, Any]:
    reg = registry if registry is not None else load_registry()
    get = fetcher or fetch_chain
    closes_of = closes_fn or bars_daily
    vol_of = vol_index_fn or vol_index_series
    state = load_state(data_dir)
    chosen = [BY_ETF[e] for e in (etfs or BY_ETF) if e in BY_ETF]
    per: dict[str, Any] = {}
    contracts: list[dict[str, Any]] = []
    obs: list[Any] = []
    cells: list[dict[str, Any]] = []
    for proxy in chosen:
        res = resolve(proxy, reg)
        sym = res.get("mt5_symbol")
        entry: dict[str, Any] = {"mapping": res}
        # ---- snapshot (budgeted)
        if fetch and due(state, proxy.etf, now):
            doc, status = get(proxy.etf)
            entry["fetch"] = status
            if not dry_run:
                state[proxy.etf] = {"last_attempt": _iso(now), "status": status[:120]}
            if doc is not None:
                chain = parse_chain(doc, etf=proxy.etf, received_at=now)
                entry["parse"] = {k: chain.get(k) for k in (
                    "status", "why", "knowable_basis", "pit_note", "n_parsed", "n_skipped",
                    "iv_unit", "greeks_filled")}
                if chain["status"] == "PARSED":
                    feats = features(chain)
                    row = feature_row(chain, feats, sym)
                    entry["latest"] = row
                    if not dry_run:
                        save_snapshot(data_dir, chain, feats)
                        append_history(data_dir, proxy.etf, row)
                        state[proxy.etf]["status"] = "PARSED"
        else:
            entry["fetch"] = "NOT_DUE" if fetch else "NO_FETCH"
        hist = history(data_dir, proxy.etf)
        if dry_run and entry.get("latest"):
            hist = [*hist, entry["latest"]]
        entry["history_rows"] = len(hist)
        # ---- lake series
        sid = series_id(proxy.etf)
        lake_rows = [{"available_time": h["available_time"], "event_time": h["event_time"],
                      "source_id": SOURCE["id"],
                      **{c: h.get(c) for c in FEATURE_COLS}} for h in hist]
        if not dry_run and lake_rows:
            entry["lake"] = se.write_lake_series(sid, lake_rows, root=lake_root)
        else:
            entry["lake"] = {"series_id": sid, "rows": len(lake_rows),
                             "status": "DRY_RUN" if dry_run else UNMEASURED}
        if sym is None:
            entry["contracts"] = UNMEASURED
            per[proxy.etf] = entry
            continue
        # ---- cells (gex and skew, both sides: the mechanism does not fix a sign the
        #      conditioner can express -- continuation under GEX<0 is a momentum reading)
        if emit_cells and lake_rows:
            cells.append(se.emit_conditioner_cells(
                sid, ["gex", "skew_90_110"], [sym],
                mechanism=(f"{proxy.etf} option-chain dealer gamma (measure Q, {DEALER_CONVENTION})"
                           f" and 90/110 skew as state for {sym}: negative dealer gamma "
                           "amplifies moves, positive dampens; skew prices tail demand"),
                falsifier=CARD_ADH001_FALSIFIER, generator=ENGINE, sides=(1, -1),
                dry_run=dry_run))
        # ---- contracts
        closes = closes_of(sym, now)
        if proxy.etf in GEX_CARD_ETFS:
            contracts.append(gex_continuation_contract(hist, closes, etf=proxy.etf, symbol=sym,
                                                       min_n=min_n))
        if proxy.vol_index:
            contracts.append(vol_forecast_contract(hist, closes, vol_of(proxy.vol_index),
                                                   etf=proxy.etf, symbol=sym,
                                                   vol_index=proxy.vol_index, min_n=min_n))
        # ---- ledger
        if hist:
            obs.extend(_ledger_rows(hist[-1], hist, sym))
        per[proxy.etf] = entry
    ledger_out: Any = {"status": "DRY_RUN"} if dry_run else {"appended": 0}
    if not dry_run:
        _atomic(data_dir / "state.json", json.dumps(state, indent=1, sort_keys=True))
        if obs:
            led = ledger if ledger is not None else sc.SensorLedger()
            ledger_out = led.append(obs, now=now)
        se.publish(ENGINE, contracts, root=contracts_root,
                   extra={"measure": MEASURE, "dealer_convention": DEALER_CONVENTION})
    doc = {"engine": ENGINE, "at": _iso(now), "dry_run": dry_run, "source": SOURCE,
           "measure": MEASURE, "dealer_convention": DEALER_CONVENTION,
           "symbols": per, "contracts": contracts,
           "verdicts": {v: sum(1 for c in contracts if c.get("verdict") == v)
                        for v in (se.GAIN, se.NO_GAIN, se.UNMEASURED)},
           "cells": cells, "ledger": ledger_out, "authority": "NONE",
           "rule": "options never trade; every number is a Q-measure state of the mapped CFD"}
    if not dry_run and report is not None:
        _atomic(report, json.dumps(doc, indent=1, sort_keys=True, default=str) + "\n")
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="ETF option-chain positioning state (QG-OT-005)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-fetch", action="store_true", help="measure the archive only")
    ap.add_argument("--symbols", default="", help="comma-separated ETFs (default: all)")
    a = ap.parse_args(argv)
    etfs = [s.strip().upper() for s in a.symbols.split(",") if s.strip()] or None
    doc = run(now=datetime.now(UTC), fetch=not a.no_fetch, etfs=etfs, dry_run=a.dry_run)
    print(json.dumps({"at": doc["at"], "verdicts": doc["verdicts"],
                      "fetch": {k: v.get("fetch") for k, v in doc["symbols"].items()},
                      "mapping": {k: v["mapping"].get("mt5_symbol") or v["mapping"]["status"]
                                  for k, v in doc["symbols"].items()}}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
