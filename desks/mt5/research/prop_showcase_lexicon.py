"""Prop-firm showcase lexicon: prose -> claim -> (family, params) cells.

The deterministic half of prop_showcase_miner (see its header for the whole pipeline): which
words name an instrument, a session and a style, and which registered family each claim stands
for on the desk's broker stamp hours (NY+7). No fetch, no file I/O, no LLM seat.
"""
from __future__ import annotations

import html
import json
import re
from typing import Any

# ------------------------------------------------------------------------------- lexicon
#: Underlying -> desk symbols in preference order (the first with bars on this box is used).
INSTRUMENTS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "gold": (r"\b(gold|xau(usd)?|gc\b|mgc\b)", ("XAUUSD",)),
    "silver": (r"\b(silver|xag(usd)?)\b", ("XAGUSD",)),
    "nasdaq": (r"\b(nasdaq|nas ?100|us ?100|ustec|nq\b|mnq\b)", ("NAS100", "USTEC", "US100")),
    "sp500": (r"\b(s&p|s&amp;p|sp ?500|spx|us ?500|es\b|mes\b)", ("US500", "SPX500")),
    "dow": (r"\b(dow|us ?30|dj30|ym\b|mym\b)", ("US30", "DJ30")),
    "dax": (r"\b(dax|ger ?40|de ?40|ger30)", ("GER40", "DE40")),
    "ftse": (r"\b(ftse|uk ?100)", ("UK100",)),
    "nikkei": (r"\b(nikkei|jp ?225|jpn225)", ("JP225",)),
    "oil": (r"\b(crude|oil|wti|usoil|xtiusd|cl\b)", ("USOIL", "XTIUSD", "WTI")),
    "bitcoin": (r"\b(bitcoin|btc(usd)?)", ("BTCUSD",)),
    "ethereum": (r"\b(ethereum|eth(usd)?)\b", ("ETHUSD",)),
    "eurusd": (r"\beur ?/? ?usd\b|\beuro dollar\b|\bfiber\b", ("EURUSD",)),
    "gbpusd": (r"\bgbp ?/? ?usd\b|\bcable\b", ("GBPUSD",)),
    "usdjpy": (r"\busd ?/? ?jpy\b", ("USDJPY",)),
    "gbpjpy": (r"\bgbp ?/? ?jpy\b|\bthe beast\b|\bgeppy\b", ("GBPJPY",)),
    "eurjpy": (r"\beur ?/? ?jpy\b", ("EURJPY",)),
    "audusd": (r"\baud ?/? ?usd\b|\baussie\b", ("AUDUSD",)),
    "usdcad": (r"\busd ?/? ?cad\b|\bloonie\b", ("USDCAD",)),
}
#: Session -> open stamp hours on NY+7 (asia: the (start, end) window asia_momentum reads; the
#: two rows cover the US-DST shift of the Tokyo open).
SESSIONS: dict[str, tuple[str, tuple[tuple[int, int], ...]]] = {
    "asia": (r"\b(asia(n)?|tokyo|sydney)\b", ((0, 7), (0, 8))),
    "london": (r"\b(london|frankfurt|european)( session| open)?\b", ((10, 0),)),
    "new_york": (r"\b(new york|ny|us|wall street)( session| open|-open)\b|\bny open\b",
                 ((16, 0),)),
    "london_close": (r"\blondon (close|fix(ing)?)\b", ()),
}
STYLES: dict[str, str] = {
    "scalp": r"\bscalp(s|ing|er)?\b",
    "breakout": r"\bbreak ?outs?\b|\bopening range\b|\brange break",
    "pullback": r"\bpull ?backs?\b|\bretrace(ment)?s?\b|\bbuy(ing)? the dip",
    "trend": r"\btrend(s|ing| following)?\b|\bmoving averages?\b|\bema\b",
    "reversal": r"\brevers(al|als|ion)\b|\bfad(e|ing)\b|\bcounter.?trend\b|\bmean reversion\b",
    "smc": r"\b(ict|fair value gaps?|fvg|smart money|order blocks?|liquidity (grab|sweep)s?)\b",
    "levels": r"\b(support and resistance|supply and demand|key levels?|previous day('s)? "
              r"high|pdh|pdl)\b",
    "rsi": r"\brsi\b|\brelative strength index\b",
    "bollinger": r"\bbollinger\b",
    "news": r"\b(news trading|trade the news|nfp|cpi release|fomc|high.impact news)\b",
    "price_action": r"\bprice action\b|\bcandlestick\b|\bpin ?bars?\b|\bengulfing\b",
    "swing": r"\bswing trad(e|es|er|ing)\b",
}
RR_RE = re.compile(r"\b1\s*[:/]\s*([1-5](?:\.\d)?)\b|\b([1-5](?:\.\d)?)\s*r\b|"
                   r"risk[- ]to[- ]reward(?: ratio)?(?: of)?\s*(?:1\s*[:/]\s*)?([1-5](?:\.\d)?)",
                   re.I)
PAYOUT_RE = re.compile(r"\$\s?([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{4,7})")


def extract(text: str) -> dict[str, Any]:
    """Prose -> structured claim. Deterministic; empty lists mean 'not stated', never 'no'."""
    t = html.unescape(text or "").lower()
    out: dict[str, Any] = {
        "instruments": sorted(k for k, (rx, _) in INSTRUMENTS.items() if re.search(rx, t)),
        "sessions": sorted(k for k, (rx, _) in SESSIONS.items() if re.search(rx, t)),
        "styles": sorted(k for k, rx in STYLES.items() if re.search(rx, t)),
    }
    rr = []
    for m in RR_RE.finditer(t):
        v = next((g for g in m.groups() if g), None)
        if v is not None and 1.0 <= float(v) <= 5.0:
            rr.append(float(v))
    out["rr"] = sorted(set(rr))
    pays = [int(m.group(1).replace(",", "")) for m in PAYOUT_RE.finditer(t)]
    out["payout_usd_max"] = max(pays) if pays else None
    out["horizon"] = ("intraday" if re.search(r"\b(minutes?|intraday|scalp)", t)
                      else "swing" if re.search(r"\b(days|weeks|swing)\b", t) else None)
    return out


# ------------------------------------------------------------------------------- cells
def _grid(style: str, session: str | None, rr: list[float], horizon: str | None
          ) -> list[tuple[str, dict[str, Any]]]:
    """(family, params) variants one claim stands for. Small and fixed: every one is a look."""
    rrs = [min(4.0, max(1.0, r)) for r in rr][:2] or [None]
    ttl = 4 if horizon == "intraday" else 24 if horizon == "swing" else 12
    out: list[tuple[str, dict[str, Any]]] = []
    windows = SESSIONS[session][1] if session in SESSIONS else ()
    for r in rrs:
        extra = {"rr": r} if r is not None else {}
        if style in ("breakout", "scalp") and (windows or session == "london_close"):
            if session == "asia":
                for a, b in windows:
                    out.append(("asia_momentum", {"asia_start": a, "asia_end": b, **extra}))
            elif session == "london_close":
                out.append(("london_close_momentum", {**extra}))
            else:
                o = windows[0][0]
                # pre-open range broken at the open, and the opening hour's range broken after
                out.append(("session_range_breakout", {"range_start": o - 3, "range_end": o,
                                                       "signal_at": o, "ttl_bars": ttl,
                                                       **extra}))
                out.append(("session_range_breakout", {"range_start": o, "range_end": o + 1,
                                                       "signal_at": o + 1, "ttl_bars": ttl,
                                                       **extra}))
        elif style == "breakout":
            out.append(("level_breakout", {"level": "pdh", "ttl_bars": ttl, **extra}))
        elif style == "levels":
            out.append(("level_breakout", {"level": "pdh", "ttl_bars": ttl, **extra}))
            out.append(("failed_breakout", {**extra}))
        elif style == "pullback":
            out.append(("pullback_entry", {**extra}))
        elif style in ("trend", "swing"):
            out.append(("trend_ma_cross", {"ttl_bars": max(ttl, 24), **extra}))
        elif style == "reversal":
            out.append(("mean_reversion_bollinger", {**extra}))
            out.append(("range_reversion", {**extra}))
        elif style == "smc":
            out.append(("ict_fvg", {"ttl_bars": ttl, **extra}))
        elif style == "rsi":
            out.append(("mean_reversion_rsi", {**extra}))
        elif style == "bollinger":
            out.append(("mean_reversion_bollinger", {**extra}))
        # "news" maps to no family here: usd_session_shock needs the dollar-index frame
        # (positional fx) this producer does not load, and a cell that always raises is dead.
        elif style == "price_action":
            out.append(("pin_bar_reversal", {**extra}))
            out.append(("engulfing_reversal", {**extra}))
        elif style == "scalp":
            out.append(("mean_reversion_bollinger", {"ttl_bars": 4, **extra}))
    return out


def cells(claims: list[dict[str, Any]], have: set[str]) -> list[dict[str, Any]]:
    """Claims -> unique (symbol, family, params) cells with the stories that back each."""
    book: dict[str, dict[str, Any]] = {}
    for c in claims:
        syms = []
        for inst in c.get("instruments") or []:
            prefs = INSTRUMENTS.get(inst, ("", ()))[1]
            s = next((p for p in prefs if p in have), None)
            if s:
                syms.append(s)
        sessions = c.get("sessions") or [None]
        for style in c.get("styles") or []:
            for sess in sessions:
                for fam, params in _grid(style, sess, c.get("rr") or [], c.get("horizon")):
                    for sym in syms:
                        key = json.dumps([sym, fam, params], sort_keys=True)
                        row = book.setdefault(key, {"symbol": sym, "family": fam,
                                                    "params": params, "styles": set(),
                                                    "sessions": set(), "stories": set(),
                                                    "firms": set()})
                        row["styles"].add(style)
                        if sess:
                            row["sessions"].add(sess)
                        row["stories"].add(c["url"])
                        row["firms"].add(c["firm"])
    out = []
    for row in book.values():
        row = {**row, "styles": sorted(row["styles"]), "sessions": sorted(row["sessions"]),
               "firms": sorted(row["firms"]), "support": len(row["stories"]),
               "stories": sorted(row["stories"])[:8]}
        out.append(row)
    out.sort(key=lambda r: (-r["support"], -len(r["firms"]), r["symbol"], r["family"]))
    return out
