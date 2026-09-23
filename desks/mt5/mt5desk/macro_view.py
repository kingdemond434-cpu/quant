"""A CURRENCY-LEVEL MACRO VIEW: which way each currency is leaning, how sure, and what that means
for the direction of every pair the desk trades.

WHY THIS EXISTS, in the principal's words on 2026-09-16: "forex is all macro, so why is it being
stupid with so many losing trades." Measured that night, every currency leg the book held was
losing at once -- CHF -5.03, EUR -2.69, CAD -2.65, AUD -2.62, USD -2.31, GBP -1.65 -- which is
the signature of a book with NO directional view at all: it took the same mechanical signal on
EURCHF, USDCHF and GBPCHF and called them three bets when they were one CHF bet, and it sized
the third the same as the first.

THE DESK ALREADY HAD THE INPUTS AND A FAMILY THAT COULD NOT USE THEM. `data/fred_macro.json`
carries the broad dollar index (DTWEXBGS), VIX (VIXCLS), the 10-year (DGS10) and the curve
(T10Y2Y), each with 800+ daily observations. `family_macro_conditional` took a macro series
and emitted 14,448 signals -- one per bar -- with the IDENTICAL {long: 6384, short: 8064} split
on EURUSD, USDJPY, AUDUSD and USDCHF alike. It had no idea which side of the dollar each pair
sits on: USDJPY long is LONG dollar, EURUSD long is SHORT dollar, and it treated them the same.
That is a coin with a bias, and the sweep correctly rejected it.

WHAT THIS DOES INSTEAD. It reads the same series, ranks each against its own trailing window,
turns the ranks into a lean per CURRENCY -- not per pair -- and derives each pair's direction as
the difference of its two legs. A strong dollar is +USD, which is short EURUSD and long USDJPY
at the same time, which is the whole point.

    dollar  DTWEXBGS rank   -> USD lean; EUR and GBP lean the other way
    rates   DGS10 rank      -> reinforces USD (a rising 10-year draws the dollar)
    risk    VIXCLS rank     -> risk-on currencies (AUD NZD CAD MXN ZAR NOK SEK) lean down
                               when VIX is high; havens (JPY CHF) lean up; gold leans up
    XAU                     -> up on risk-off and on a weak dollar

CONFIDENCE IS EARNED TWICE. Ranks near 0.5 say nothing, so confidence rises with distance from
the middle. And a series that stopped updating twelve days ago -- the FRED collector died with
the VPS on ~2026-09-11 -- is worth less than a fresh one, so confidence decays linearly to zero
over STALE_DAYS. A stale view still tilts, gently, and says in its own report that it is stale;
it never pretends to be current.

TWO-SIDED, LIKE `leg_balance`, AND FOR THE SAME REASON. An order ALIGNED with the view is sized
UP by the same bound an opposed order is sized DOWN, so the book's total heat is unchanged and
what moves is which direction it buys. That is a capital modifier under the growth-governance
rule (registered in `libs/portfolio/capital_modifiers.py`), not a veto: nothing here refuses a
trade, and a sleeve whose certificate disagrees with the macro lean still trades -- smaller,
with the disagreement written into the order's basis line so it can be judged later.

NONE IS A REAL ANSWER. No file, an unreadable file, a symbol with no currency decomposition, or
a lean the data cannot support all return a multiplier of exactly 1.0 with the reason, never a
guess and never a silent shrink.

    python desks/mt5/mt5desk/macro_view.py        # print the view and write the report

Artifact: desks/mt5/reports/MACRO_VIEW.json
"""
from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
FRED = ROOT / "data" / "fred_macro.json"
OUT = DESK / "reports" / "MACRO_VIEW.json"

#: Trailing window for the percentile rank, in daily observations. One trading year: long enough
#: that a rank means "high for this cycle", short enough to notice a regime that turned this
#: quarter. Matches `orthogonal_sweep.MACRO_RANK_MIN_OBS` so the two readers agree on what
#: "enough history" is.
RANK_WINDOW = int(os.environ.get("MACRO_RANK_WINDOW", "250"))

#: Days of staleness at which the view's confidence reaches ZERO. The lean still computes and
#: still reports; it just stops moving size. 30 days: a daily macro regime moves slowly, but a
#: month-old dollar rank has had a full FOMC cycle happen behind it.
STALE_DAYS = float(os.environ.get("MACRO_STALE_DAYS", "30"))

#: The multiplier's band. Symmetric about 1.0 on purpose -- see the module docstring.
MULT_MIN = float(os.environ.get("MACRO_MULT_MIN", "0.6"))
MULT_MAX = float(os.environ.get("MACRO_MULT_MAX", "1.4"))

RISK_ON = ("AUD", "NZD", "CAD", "MXN", "ZAR", "NOK", "SEK", "BRL", "TRY", "HUF", "PLN", "CZK")
HAVENS = ("JPY", "CHF")
DOLLAR_INVERSE = ("EUR", "GBP", "DKK", "SGD")     # currencies that move mostly against the USD


def _rank(values: list[float], window: int = RANK_WINDOW) -> float | None:
    """Where the latest value sits in its trailing window, 0..1. None with too little history."""
    if len(values) < window:
        return None
    tail = values[-window:]
    last = tail[-1]
    below = sum(1 for v in tail if v < last)
    return below / (len(tail) - 1) if len(tail) > 1 else None


def _load() -> tuple[dict[str, list[float]], str | None, float | None]:
    """(series -> values, newest print date, age in days). Empty on any failure."""
    try:
        doc = json.loads(FRED.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}, None, None
    out: dict[str, list[float]] = {}
    newest = None
    for k, pts in (doc.get("series") or {}).items():
        if not isinstance(pts, list):
            continue
        vals = []
        for p in pts:
            try:
                d, v = p[0], float(p[1])
            except (TypeError, ValueError, IndexError):
                continue
            vals.append(v)
            if newest is None or str(d) > newest:
                newest = str(d)
        if vals:
            out[k] = vals
    age = None
    if newest:
        try:
            age = (datetime.now(tz=UTC) - datetime.fromisoformat(newest).replace(tzinfo=UTC)).days
        except ValueError:
            age = None
    return out, newest, age


def view() -> dict[str, Any]:
    """The lean per currency, the confidence, and why."""
    series, newest, age = _load()
    ranks = {k: _rank(series[k]) for k in ("DTWEXBGS", "VIXCLS", "DGS10", "T10Y2Y") if k in series}
    ranks = {k: v for k, v in ranks.items() if v is not None}
    if "DTWEXBGS" not in ranks and "VIXCLS" not in ranks:
        return {"status": "UNMEASURED", "why": "neither a dollar nor a risk series with "
                f"{RANK_WINDOW}+ observations in {FRED.name}", "lean": {}, "confidence": 0.0,
                "ranks": ranks, "newest_print": newest, "age_days": age}

    # Centred drivers in [-1, 1]: +1 means "at the top of its year".
    dxy = 2.0 * (ranks.get("DTWEXBGS", 0.5) - 0.5)
    vix = 2.0 * (ranks.get("VIXCLS", 0.5) - 0.5)
    r10 = 2.0 * (ranks.get("DGS10", 0.5) - 0.5)

    lean: dict[str, float] = {}
    # USD: the dollar index is the direct read; the 10-year reinforces it at half weight.
    lean["USD"] = max(-1.0, min(1.0, 0.7 * dxy + 0.3 * r10))
    for c in DOLLAR_INVERSE:
        lean[c] = -0.6 * lean["USD"]
    for c in RISK_ON:
        lean[c] = -0.8 * vix
    for c in HAVENS:
        lean[c] = 0.8 * vix
    # Gold: risk-off AND a weak dollar both lift it.
    lean["XAU"] = max(-1.0, min(1.0, 0.6 * vix - 0.6 * dxy))
    lean["XAG"] = 0.7 * lean["XAU"]

    # Confidence: how far the drivers sit from the middle, then decayed by staleness.
    drivers = [abs(dxy)] + ([abs(vix)] if "VIXCLS" in ranks else [])
    strength = sum(drivers) / len(drivers)
    fresh = 1.0 if age is None else max(0.0, 1.0 - age / STALE_DAYS)
    conf = round(strength * fresh, 4)
    why = (f"dollar rank {ranks.get('DTWEXBGS', float('nan')):.2f}, VIX rank "
           f"{ranks.get('VIXCLS', float('nan')):.2f}, 10y rank {ranks.get('DGS10', float('nan')):.2f}"
           f"; newest print {newest} ({age}d old -> freshness {fresh:.2f}); confidence {conf:.2f}")
    return {"status": "MEASURED" if fresh > 0 else "STALE",
            "why": why, "lean": {k: round(v, 3) for k, v in lean.items()},
            "confidence": conf, "freshness": round(fresh, 3), "strength": round(strength, 3),
            "ranks": {k: round(v, 3) for k, v in ranks.items()},
            "newest_print": newest, "age_days": age}


def _legs(symbol: str) -> tuple[str, str] | None:
    s = str(symbol or "").upper()
    if len(s) == 6:
        return s[:3], s[3:]
    return None


def score(symbol: str, v: dict[str, Any] | None = None) -> tuple[float | None, str]:
    """This pair's macro direction in [-1, 1] (+ = long the base), or None with the reason."""
    v = v or view()
    if v.get("status") == "UNMEASURED":
        return None, v.get("why", "unmeasured")
    legs = _legs(symbol)
    if legs is None:
        return None, f"{symbol} has no currency decomposition"
    base, quote = legs
    lean = v["lean"]
    if base not in lean and quote not in lean:
        return None, f"no lean for either leg of {symbol}"
    s = lean.get(base, 0.0) - lean.get(quote, 0.0)
    return max(-1.0, min(1.0, s)), f"{base} {lean.get(base, 0.0):+.2f} vs {quote} {lean.get(quote, 0.0):+.2f}"


#: The families a macro REGIME can legitimately condition. These hold across sessions -- carry
#: earns the rollover overnight, overnight_gap_decay fades the gap into the next session,
#: macro_conditional IS the macro trade, and a session-range breakout runs with the day's trend.
#: A multi-week dollar lean is on the same clock as these and can size them.
MACRO_HORIZON_FAMILIES = frozenset({
    "carry", "overnight_gap_decay", "macro_conditional", "session_range_breakout",
    "vol_transition", "cross_asset_residual", "cot_positioning",
})


def horizon_ok(family: str | None, ttl_bars: object = None, bar_minutes: int = 60) -> bool:
    """Is this trade's horizon long enough for a macro regime to be the right tool?

    THE ERROR THIS PREVENTS, caught the night the macro layer shipped (2026-09-16). The desk's
    AUDUSD and AUDCAD SHORTS were its best trades -- short-horizon mean reversion selling the top
    of the Asian range. The macro view leaned AUD UP (risk-on, low VIX), read those shorts as
    fighting the trend, and DAMPED the winners 4.3%. A multi-week dollar regime and a nine-hour
    range scalp are different clocks: a currency leans up on the month while falling for the day,
    and conditioning the scalp on the month is simply the wrong instrument.

    So macro sizes a trade only when the trade lives long enough for the regime to act on it --
    by family (the directional, multi-session ones) OR by a genuinely long TTL. Everything else
    is macro-NEUTRAL, sized as the certificate says, because at the scalp horizon the macro lean
    carries no information in either direction and must not pretend to.
    """
    if str(family or "") in MACRO_HORIZON_FAMILIES:
        return True
    try:
        hold_h = float(ttl_bars) * float(bar_minutes) / 60.0
    except (TypeError, ValueError):
        return False
    return hold_h >= 24.0     # a full day held is long enough for a regime to matter


def multiplier(symbol: str, side: int, v: dict[str, Any] | None = None, *,
               family: str | None = None, ttl_bars: object = None,
               bar_minutes: int = 60) -> tuple[float, str]:
    """Size an order by its agreement with the macro lean. 1.0 whenever the view cannot speak,
    AND 1.0 whenever the trade's horizon is too short for a macro regime to apply."""
    v = v or view()
    if family is not None or ttl_bars is not None:
        if not horizon_ok(family, ttl_bars, bar_minutes):
            return 1.0, (f"macro 1.00: {family or 'this'} is a short-horizon trade; a macro "
                         f"regime is the wrong clock for it, so it sizes as certified")
    sc, why = score(symbol, v)
    if sc is None:
        return 1.0, f"macro 1.00: {why}"
    align = float(side) * sc                     # +1 fully aligned, -1 fully opposed
    conf = float(v.get("confidence") or 0.0)
    raw = 1.0 + (MULT_MAX - 1.0) * align * conf
    m = max(MULT_MIN, min(MULT_MAX, raw))
    stance = "aligned" if align > 0.15 else "opposed" if align < -0.15 else "neutral"
    return m, (f"macro {m:.2f} ({stance}): {'long' if side > 0 else 'short'} {symbol} vs lean "
               f"{sc:+.2f} [{why}] at confidence {conf:.2f}"
               + ("" if v.get("status") == "MEASURED" else f" ({v.get('status')})"))


def main() -> int:
    v = view()
    print(f"macro view: {v['status']} -- {v.get('why')}")
    for c, l in sorted((v.get("lean") or {}).items(), key=lambda kv: -abs(kv[1])):
        bar = "+" * int(round(max(0.0, l) * 10)) + "-" * int(round(max(0.0, -l) * 10))
        print(f"   {c:4} {l:+.2f}  {bar}")
    print()
    for sym, side in (("EURUSD", 1), ("USDJPY", 1), ("AUDUSD", 1), ("EURCHF", -1), ("USDCHF", -1),
                      ("XAUUSD", 1), ("GBPNOK", 1)):
        m, w = multiplier(sym, side, v)
        print(f"   {sym} {'long ' if side > 0 else 'short'} -> x{m:.2f}   {w[:90]}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({**v, "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
                               "band": [MULT_MIN, MULT_MAX], "stale_days": STALE_DAYS},
                              indent=1), encoding="utf-8")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
