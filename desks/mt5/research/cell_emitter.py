"""The open-source cell emitter: published strategy CODE read as testable cells.

    grounds (data/cell_emitter_sources.json) -> list files (API tree / seed paths / code search)
      -> fetch raw source -> STATIC parse (mt5desk.compiler front end + the readers below)
      -> map to a registered family + exact params, or a STRUCTURED_HYPOTHESIS
      -> map instruments to Fusion analogues (universe_policy decides the lane)
      -> donate to data/intelligence/cell_emitter/ -> miner_candidate_compiler -> docket
      -> gauntlet, with every cell priced in this pass's trial census

WHY A NEW ORGAN AND NOT `repo_miner`. `repo_miner` reads READMEs for PROSE mechanism claims and
queues them for an LLM seat to turn into a recipe; `mt5desk/compiler.py` parses MQL/Pine/Python
into an indicator IR and ablation families, but nothing on a clock ever handed it public code or
turned its IR into a family the gauntlet can build. The code already STATES the rule -- `fast_window
= 10`, `ta.ema(close, 20)`, `iRSI(_Symbol, PERIOD_H1, 14, PRICE_CLOSE)` -- so an LLM call to
re-derive it is waste, and a README sentence is a weaker witness than the code it describes. This
organ reuses the compiler's front end (language detection, its coverage honesty rule), the prose
miners' instrument grammar (`libs.research.mechanism_claims`), the lane law
(`research.universe_policy`) and the compiler's donation door; what it adds is the READER from an
indicator call to a family's keyword arguments.

WHAT COUNTS AS EXACT. A cell is an EXACT recipe (`family` + `params`, compiled as EXACT_RECIPE)
only when the family's primary lookbacks were READ from the code -- a literal, or an identifier the
file assigns a number to -- and the orientation the family encodes matches the code's (an RSI that
BUYS strength is momentum, not `mean_reversion_rsi`). Everything else that still names a
mechanism lands as a `kind: hypothesis` row: with the nearest registered family when there is one
(compiled as STRUCTURED_HYPOTHESIS on the family's defaults), without one when there is not (the
compiler routes it to deepening as NEEDS_EXACT_RULE_EXTRACTION, with the reading attached). An SMA
cross judged on the family's EMA construction is marked `fidelity: analogue`, never `exact`.

NOTHING READ IS EXECUTED. Static text only: regex and the compiler's `parse_source`. No `exec`,
`eval`, `compile`, `import` of fetched code, no subprocess; a test walks this module's AST for it.

CRYPTO-EXCHANGE GROUND (standing order 2026-08-18). A ground marked `venue: crypto_exchange`
(freqtrade, jesse) maps ONLY onto Fusion's crypto CFDs; a strategy whose code reads funding,
perpetuals, liquidations or an exchange order book is dropped and COUNTED, because that mechanism
does not exist on a CFD. No other ground may resolve to a crypto-exchange venue.

THE YIELD IS MEASURED, NEVER CLAIMED. The report (`reports/CELL_EMITTER.json`) carries, per
ground: files listed, fetched, parsed, mapped, donated, cells, and every drop by reason; a ground
the host could not reach says UNREACHED with the HTTP status, and its yield is UNMEASURED, never 0.
A fixture run says `mode: FIXTURE` on the report and writes no donation.

    python desks/mt5/research/cell_emitter.py --once --budget-s 300
    python desks/mt5/research/cell_emitter.py --once --dry-run
    python desks/mt5/research/cell_emitter.py --fixtures desks/mt5/tests/fixtures/cell_emitter
"""
from __future__ import annotations

import argparse
import contextlib
import fnmatch
import hashlib
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SOURCE = "cell_emitter"
LEG = "cell_emitter"
SOURCES = _DESK / "data" / "cell_emitter_sources.json"
STATE = _DESK / "data" / "cell_emitter_state.json"
DONATE_DIR = _DESK / "data" / "intelligence" / SOURCE
REPORT = _DESK / "reports" / "CELL_EMITTER.json"
UNIVERSE = _DESK / "data" / "universe" / "universe.json"
GITHUB_API = "https://api.github.com"
GITHUB_RAW = "https://raw.githubusercontent.com"
GITEE_API = "https://gitee.com/api/v5"
UNMEASURED = "UNMEASURED"
#: Seconds held back from the budget to write the report, state and donations.
WRITE_RESERVE_S = 20.0
#: Seen-content memory: a file whose bytes did not change since it was last emitted is not
#: re-donated (the compiler dedups exact rows too; this saves the fetch-parse round and keeps
#: `donated` meaning NEW cells).
SEEN_CAP = 20_000

# ============================================================================ the static reader

#: Indicator call -> kind. Matched against the callee's LAST dotted component, lower-cased, so
#: `ta.EMA`, `bt.ind.EMA`, `am.ema` and `ta.ema` are one reading. MQL's `iMA` is resolved by
#: its method argument (MODE_EMA / MODE_SMA) in `_read_calls`.
CALLEE_KIND: dict[str, str] = {
    "ema": "ema", "exponentialmovingaverage": "ema", "movingaverageexponential": "ema",
    "sma": "sma", "simplemovingaverage": "sma", "movingaveragesimple": "sma", "ma": "sma",
    "rsi": "rsi", "irsi": "rsi", "relativestrengthindex": "rsi",
    "boll": "bb", "bb": "bb", "bbands": "bb", "bollingerbands": "bb", "ibands": "bb",
    "bollinger_bands": "bb",
    "keltner": "keltner", "kc": "keltner", "keltnerchannel": "keltner",
    "donchian": "donchian", "highest": "donchian", "lowest": "donchian", "ihighest": "donchian",
    "ilowest": "donchian", "donchianchannel": "donchian", "max_n": "donchian",
    "adx": "adx", "iadx": "adx", "dmi": "adx", "averagedirectionalmovementindex": "adx",
    "atr": "atr", "iatr": "atr", "averagetruerange": "atr",
    "macd": "macd", "imacd": "macd",
    "mom": "mom", "momentum": "mom", "imomentum": "mom", "roc": "mom", "rateofchange": "mom",
    "cci": "cci", "icci": "cci", "commoditychannelindex": "cci",
    "stoch": "stoch", "stochastic": "stoch", "istochastic": "stoch",
}
#: Keyword names a lookback is passed under, in every framework seen.
_PERIOD_KW = ("period", "timeperiod", "length", "window", "n", "lookback", "len", "ma_period",
              "bands_period", "rsi_period", "timeperiod1")
_DEV_KW = ("devfactor", "nbdevup", "nbdev", "dev", "mult", "deviation", "std", "stddev", "k")
_CALL = re.compile(r"(?<![\w.])([A-Za-z_][\w.]*)\s*\(")
_NUM = re.compile(r"^[+-]?\d+(?:\.\d+)?$")

#: Code-level evidence of a crypto-exchange-native mechanism. Read on the code with comments
#: stripped, so a docstring that mentions an exchange by name does not drop an EMA cross.
VENUE_NATIVE = re.compile(
    r"funding|perpetual|\bperp\b|liquidation|open_interest|openinterest|order_?book|"
    r"fetch_order_book|mark_price|basis_rate", re.I)
_PAIR = re.compile(r"\b([A-Z]{2,6})\s*[/_-]\s*(USDT|USDC|BUSD|USD|TUSD|FDUSD)\b")

_LONG_INTENT = re.compile(
    r"enter_long|\bbuy\s*\(|\.buy\s*\(|op_buy|order_type_buy|strategy\.long|go_long|"
    r"\bbuy_signal|'buy'|\"buy\"|should_long|signal\s*=\s*1\b", re.I)
_SHORT_INTENT = re.compile(
    r"enter_short|\bshort\s*\(|\.short\s*\(|op_sell|order_type_sell|strategy\.short|go_short|"
    r"should_short|signal\s*=\s*-1\b", re.I)


def detect_language(src: str, path: str = "") -> str:
    ext = Path(path).suffix.lower()
    if ext == ".pine":
        return "pinescript"
    if ext in {".mq4", ".mq5", ".mqh"}:
        return "mql"
    if ext == ".py":
        return "python"
    try:
        from mt5desk.compiler import detect_language as _det
        return _det(src)
    except Exception:
        return "unknown"


def strip_comments(src: str, language: str) -> str:
    """The code without comments and (for Python) docstrings -- the text the fences read."""
    if language == "python":
        out = re.sub(r'("""|\'\'\')[\s\S]*?\1', "", src)
        return "\n".join(re.sub(r"\s#.*$|^#.*$", "", ln) for ln in out.splitlines())
    out = re.sub(r"/\*[\s\S]*?\*/", "", src)
    return "\n".join(re.sub(r"//.*$", "", ln) for ln in out.splitlines())


def _norm_name(name: str) -> str:
    n = name.strip().lower()
    for pre in ("self.params.", "self.p.", "self.", "params.", "p.", "inp_", "inp", "input_"):
        if n.startswith(pre) and len(n) > len(pre):
            n = n[len(pre):]
    return n


def symbol_table(code: str) -> dict[str, float]:
    """Names the file binds to a number: assignments, MQL inputs, Pine inputs, backtrader params,
    freqtrade Int/DecimalParameter defaults. The identifier is normalised (`self.p.fast` ->
    `fast`), so a lookback passed by name resolves to the number the author wrote."""
    tab: dict[str, float] = {}

    def put(name: str, val: str) -> None:
        # First non-zero binding wins: `rsi_buy: float = 0` is a placeholder the strategy fills
        # in later (`self.rsi_buy = 50 + self.rsi_entry`), never the value it trades on.
        with contextlib.suppress(ValueError):
            key, v = _norm_name(name), float(val)
            if not tab.get(key):
                tab[key] = v

    # One binding per LINE: `[ \t]` never `\s`, so a match cannot run into the next line, and the
    # type keyword needs its own whitespace, so `intra_trade_high` is not `int ra_trade_high`.
    for m in re.finditer(r"(?m)^[ \t]*(?:(?i:input|extern|sinput|static|const)[ \t]+)*"
                         r"(?:(?:int|double|float|uint|long|ENUM_\w+)[ \t]+)?"
                         r"([A-Za-z_][\w.]*)[ \t]*(?::[ \t]*[\w\[\], ]+?)?[ \t]*=[ \t]*"
                         r"([+-]?\d+(?:\.\d+)?)[ \t]*(?:[;,)#]|$)", code):
        put(m.group(1), m.group(2))
    for m in re.finditer(r"([A-Za-z_]\w*)\s*=\s*input(?:\.int|\.float)?\s*\(\s*(?:defval\s*=\s*)?"
                         r"([+-]?\d+(?:\.\d+)?)", code):
        put(m.group(1), m.group(2))
    for m in re.finditer(r"\(\s*['\"]([A-Za-z_]\w*)['\"]\s*,\s*([+-]?\d+(?:\.\d+)?)\s*\)", code):
        put(m.group(1), m.group(2))                       # backtrader params = (('fast', 10),)
    for m in re.finditer(r"(?:dict|params)\s*\(([^)]*)\)", code):
        for k, v in re.findall(r"([A-Za-z_]\w*)\s*=\s*([+-]?\d+(?:\.\d+)?)", m.group(1)):
            put(k, v)
    for sig in re.findall(r"def\s+\w+\s*\(([^)]*)\)", code):  # def f(price, Lfast=32, ...)
        for k, v in re.findall(r"([A-Za-z_]\w*)\s*(?::\s*\w+)?\s*=\s*([+-]?\d+(?:\.\d+)?)",
                               sig):
            put(k, v)
    for m in re.finditer(r"([A-Za-z_]\w*)\s*=\s*(?:Int|Decimal|Real)Parameter\s*\([^)]*?"
                         r"default\s*=\s*([+-]?\d+(?:\.\d+)?)", code):
        put(m.group(1), m.group(2))
    # a binding by simple arithmetic of two bound names or numbers: `rsi_buy = 50 + rsi_entry`
    for m in re.finditer(r"(?m)^\s*([A-Za-z_][\w.]*)\s*=\s*([\w.]+)\s*([+\-*])\s*([\w.]+)\s*$",
                         code):
        a, b = _resolve(m.group(2), tab), _resolve(m.group(4), tab)
        if a is not None and b is not None and not tab.get(_norm_name(m.group(1))):
            tab[_norm_name(m.group(1))] = (a + b if m.group(3) == "+" else
                                           a - b if m.group(3) == "-" else a * b)
    return tab


def _resolve(token: str, tab: dict[str, float]) -> float | None:
    t = (token or "").strip()
    if _NUM.match(t):
        return float(t)
    return tab.get(_norm_name(t))


def _args(code: str, start: int) -> tuple[list[str], int]:
    """Top-level comma-split arguments of the call whose '(' is at `start`, and its end."""
    depth, cur, out, i = 0, [], [], start
    while i < len(code):
        ch = code[i]
        if ch in "([{":
            depth += 1
            if depth > 1:
                cur.append(ch)
        elif ch in ")]}":
            depth -= 1
            if depth == 0:
                out.append("".join(cur).strip())
                return [a for a in out if a != ""], i
            cur.append(ch)
        elif ch == "," and depth == 1:
            out.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
        i += 1
        if i - start > 600:
            break
    return [a for a in out if a != ""], i


def _split_kw(args: list[str]) -> tuple[list[str], dict[str, str]]:
    pos: list[str] = []
    kw: dict[str, str] = {}
    for a in args:
        m = re.match(r"^([A-Za-z_]\w*)\s*=\s*(?!=)(.+)$", a)
        if m:
            kw[m.group(1).lower()] = m.group(2).strip()
        else:
            pos.append(a)
    return pos, kw


def _read_calls(code: str, language: str, tab: dict[str, float]) -> list[dict[str, Any]]:
    """Every indicator call: kind, the lookback(s) and deviation it was given, and its line."""
    out: list[dict[str, Any]] = []
    for m in _CALL.finditer(code):
        callee = m.group(1)
        last = callee.rsplit(".", 1)[-1].lower()
        if last.startswith("indi_"):                     # EA31337's Indi_RSI / Indi_MA classes
            last = last[len("indi_"):]
        kind = CALLEE_KIND.get(last)
        if kind is None and last == "ima":
            kind = "ma"
        if kind is None:
            continue
        args, _end = _args(code, m.end() - 1)
        pos, kw = _split_kw(args)
        line = code.count("\n", 0, m.start()) + 1
        numeric = [(_resolve(a, tab), a) for a in pos]
        period: float | None = None
        dev: float | None = None
        extra: list[float] = []
        for k in _PERIOD_KW:
            if k in kw:
                period = _resolve(kw[k], tab)
                break
        for k in _DEV_KW:
            if k in kw:
                dev = _resolve(kw[k], tab)
                break
        if language == "mql" and last.startswith("i") and len(pos) >= 3:
            # iXXX(symbol, timeframe, period, ...): the lookback is the THIRD positional argument.
            period = period if period is not None else numeric[2][0]
            if last == "ima" and len(pos) >= 5:
                meth = pos[4].upper()
                kind = "ema" if "EMA" in meth else "sma"
            if kind == "bb":
                dev = dev if dev is not None else next(
                    (v for v, _ in numeric[3:6] if v is not None and 0.5 <= v <= 5.0), None)
            if kind == "macd":
                extra = [v for v, _ in numeric[2:5] if v is not None]
        elif kind == "ma":
            kind = "sma"
        if period is None:
            # Positional: the first numeric-resolvable argument that is not the data series.
            cands = [v for v, _raw in numeric if v is not None]
            if cands:
                period = cands[0]
            if kind == "bb" and dev is None and len(cands) >= 2:
                dev = cands[1]
            if kind == "keltner" and dev is None and len(cands) >= 2:
                dev = cands[1]
            if kind == "macd" and not extra:
                extra = cands[:3]
        if kind == "macd" and extra:
            period = period if period is not None else extra[0]
        if period is None:
            period = _bound_period(kind, tab)
        out.append({"kind": kind, "callee": callee, "period": period, "dev": dev,
                    "extra": extra, "line": line, "raw": code[m.start():_end + 1][:160]})
    # pandas: x.ewm(span=N) is an EMA, x.rolling(N).mean() an SMA; zipline's
    # data.history(asset, "price", N, "1d").mean() is an N-bar SMA.
    for m in re.finditer(r"\.ewm\s*\(\s*span\s*=\s*([\w.]+)", code):
        out.append({"kind": "ema", "callee": "ewm", "period": _resolve(m.group(1), tab),
                    "dev": None, "extra": [], "line": code.count("\n", 0, m.start()) + 1,
                    "raw": m.group(0)[:160]})
    for m in re.finditer(r"(?:rolling\s*\(\s*([\w.]+)[^)]*\)|history\s*\([^()]*?,\s*([\w.]+)\s*,"
                         r"\s*[\"'][^\"']+[\"']\s*\))\s*\.\s*mean\s*\(", code):
        out.append({"kind": "sma", "callee": "rolling.mean",
                    "period": _resolve(m.group(1) or m.group(2), tab), "dev": None, "extra": [],
                    "line": code.count("\n", 0, m.start()) + 1, "raw": m.group(0)[:160]})
    # pandas rolling extremes: x.rolling(20).max() is a Donchian channel
    for m in re.finditer(r"rolling\s*\(\s*([\w.]+)[^)]*\)\s*\.\s*(max|min)\s*\(", code):
        out.append({"kind": "donchian", "callee": "rolling." + m.group(2),
                    "period": _resolve(m.group(1), tab), "dev": None, "extra": [],
                    "line": code.count("\n", 0, m.start()) + 1, "raw": m.group(0)[:160]})
    return out


def _bound_period(kind: str, tab: dict[str, float]) -> float | None:
    """A lookback the file binds under the indicator's own name when the call passes a struct
    (EA31337: `INPUT int RSI_Indi_RSI_Period = 16;`). Only an unambiguous single binding counts."""
    names = {"ema": ("ema", "ma"), "sma": ("sma", "ma"), "bb": ("bands", "boll", "bb")}.get(
        kind, (kind,))
    hits = {v for k, v in tab.items()
            if "period" in k and any(re.search(rf"(^|_){n}(_|$)", k) for n in names)
            and 1 <= v <= 1000}
    return hits.pop() if len(hits) == 1 else None


def _intent_after(lines: list[str], i: int, span: int = 6) -> str:
    """'long' / 'short' / '' -- the first entry intent on line i or the `span` lines after it."""
    for ln in lines[i:i + span + 1]:
        lo, sh = bool(_LONG_INTENT.search(ln)), bool(_SHORT_INTENT.search(ln))
        if lo and not sh:
            return "long"
        if sh and not lo:
            return "short"
    return ""


def rsi_orientation(code: str, tab: dict[str, float]) -> tuple[str, dict[str, float]]:
    """('reversion' | 'momentum' | '', thresholds) from how the code's RSI comparisons trade.

    Buying when RSI is BELOW a level (or selling above one) is mean reversion; buying ABOVE a
    level of 50 or more (vn.py's ATR-RSI: `rsi_value > 50 + rsi_entry` -> buy) is momentum, and
    mapping that to `mean_reversion_rsi` would hand the gauntlet the opposite of the rule."""
    lines = code.splitlines()
    rx = re.compile(r"(\w*rsi\w*['\"]?\]?(?:\[[^\]]*\])?(?:\([^)]*\))?)\s*([<>]=?)\s*([\w.]+)",
                    re.I)
    rx_rev = re.compile(r"([\w.]+)\s*([<>]=?)\s*(\w*rsi\w*)", re.I)
    votes: Counter[str] = Counter()
    th: dict[str, float] = {}
    for i, ln in enumerate(lines):
        hits: list[tuple[str, float]] = []
        for m in rx.finditer(ln):
            v = _resolve(m.group(3), tab)
            if v is not None and 0 < v < 100:
                hits.append((m.group(2)[0], v))
        for m in rx_rev.finditer(ln):
            v = _resolve(m.group(1), tab)
            if v is not None and 0 < v < 100 and "rsi" not in m.group(1).lower():
                hits.append((">" if m.group(2)[0] == "<" else "<", v))
        if not hits:
            continue
        side = _intent_after(lines, i)
        for op, v in hits:
            if v < 50:
                th.setdefault("oversold", v)
            elif v > 50:
                th.setdefault("overbought", v)
            if not side:
                continue
            below = op == "<"
            if side == "long":
                votes["reversion" if below and v <= 50 else
                      "momentum" if not below and v >= 50 else "reversion"] += 1
            else:
                votes["reversion" if not below and v >= 50 else
                      "momentum" if below and v <= 50 else "reversion"] += 1
    if not votes:
        return "", th
    return votes.most_common(1)[0][0], th


def band_orientation(code: str) -> str:
    """'breakout' when the long entry is placed at/above the UPPER band, 'reversion' when at/below
    the LOWER band, '' when the code does not say."""
    lines = code.splitlines()
    for i, ln in enumerate(lines):
        if not _LONG_INTENT.search(ln):
            continue
        window = " ".join(lines[max(0, i - 4):i + 1]).lower()
        up = re.search(r"(boll|bb|band|kc|keltner)\w*_?(up|upper|top|high)", window)
        dn = re.search(r"(boll|bb|band|kc|keltner)\w*_?(down|lower|low|bot|dn)", window)
        cmp_dn = re.search(r"close\w*\s*<\s*\w*(lower|low|down|bot|dn)", window)
        cmp_up = re.search(r"close\w*\s*>\s*\w*(upper|up|top|high)", window)
        if (up or cmp_up) and not (dn or cmp_dn):
            return "breakout"
        if (dn or cmp_dn) and not (up or cmp_up):
            return "reversion"
    return ""


def _ints(vals: list[float | None]) -> list[int]:
    return sorted({round(v) for v in vals if v is not None and 1 <= v <= 1000})


def map_to_family(reading: dict[str, Any], code: str, tab: dict[str, float],
                  text: str = "") -> dict[str, Any]:
    """{family|None, params|None, fidelity, why}. `params` is None unless the family's primary
    lookback was READ; a None family means no registered family is the mechanism."""
    kinds: dict[str, list[dict[str, Any]]] = {}
    for c in reading["calls"]:
        kinds.setdefault(c["kind"], []).append(c)
    low = (text or code).lower()

    def first(kind: str, key: str = "period") -> float | None:
        return next((c[key] for c in kinds.get(kind, []) if c.get(key) is not None), None)

    if re.search(r"fair.?value.?gap|\bfvg\b|order.?block|liquidity.?sweep", low):
        return {"family": "ict_fvg", "params": None, "fidelity": "nearest_family",
                "why": "ICT vocabulary in the code; the family's own construction is judged"}
    if re.search(r"session|asian.?range|london.?open|opening.?range|range_start", low) and \
            not kinds.get("rsi") and not kinds.get("bb"):
        return {"family": "session_range_breakout", "params": None,
                "fidelity": "nearest_family", "why": "session-range logic in the code"}
    if "bb" in kinds and ("keltner" in kinds or "squeeze" in low):
        n, k = first("bb"), first("bb", "dev")
        return {"family": "volatility_squeeze",
                "params": ({"bb_n": int(n), **({"bb_k": float(k)} if k else {})} if n else None),
                "fidelity": "exact" if n else "nearest_family",
                "why": "Bollinger inside Keltner (squeeze) read from the code"}
    if "donchian" in kinds and "adx" in kinds:
        ch, ax = first("donchian"), first("adx")
        return {"family": "adx_channel_hybrid",
                "params": ({"channel": int(ch), "adx_n": int(ax)} if ch and ax else None),
                "fidelity": "exact" if ch and ax else "nearest_family",
                "why": "channel extreme conditioned on ADX read from the code"}
    if "rsi" in kinds:
        orient, th = rsi_orientation(code, tab)
        n = first("rsi")
        mas = _ints([c["period"] for c in kinds.get("ema", []) + kinds.get("sma", [])])
        if orient == "momentum":
            return {"family": "momentum_volgate", "params": None, "fidelity": "nearest_family",
                    "why": (f"RSI({n and int(n)}) traded as MOMENTUM (buys strength)"
                            + (", ATR-gated" if "atr" in kinds else ""))}
        if orient == "reversion" and n and len(mas) == 1 and mas[0] >= 50:
            return {"family": "pullback_entry",
                    "params": {"rsi_n": int(n), "trend_ema": mas[0],
                               **({"rsi_pullback": int(th["oversold"])}
                                  if th.get("oversold") else {})},
                    "fidelity": "exact" if kinds.get("ema") else "analogue",
                    "why": "RSI pullback inside a moving-average trend read from the code"}
        if orient == "reversion":
            params = ({"rsi_n": int(n),
                       **({"oversold": int(th["oversold"])} if th.get("oversold") else {}),
                       **({"overbought": int(th["overbought"])} if th.get("overbought") else {})}
                      if n else None)
            return {"family": "mean_reversion_rsi", "params": params,
                    "fidelity": "exact" if n else "nearest_family",
                    "why": "RSI read as mean reversion (buys weakness / sells strength)"}
        # orientation unread: the mechanism is RSI but which way it trades is not stated
        return {"family": "mean_reversion_rsi", "params": None, "fidelity": "nearest_family",
                "why": "RSI used, orientation not read from the code"}
    ma_e = _ints([c["period"] for c in kinds.get("ema", [])])
    ma_s = _ints([c["period"] for c in kinds.get("sma", [])])
    if len(ma_e) >= 2 or len(ma_s) >= 2 or (ma_e and ma_s):
        both = sorted(set(ma_e) | set(ma_s))
        return {"family": "trend_ma_cross",
                "params": {"fast_ema": both[0], "slow_ema": both[1]},
                "fidelity": "exact" if len(ma_e) >= 2 and not ma_s else "analogue",
                "why": (f"moving-average cross {both[0]}/{both[1]} read from the code"
                        + ("" if len(ma_e) >= 2 and not ma_s
                           else "; SMA read, judged on the family's EMA construction"))}
    if "macd" in kinds:
        ex = [int(v) for v in (kinds["macd"][0].get("extra") or []) if v]
        if len(ex) >= 2:
            return {"family": "trend_ma_cross",
                    "params": {"fast_ema": min(ex[:2]), "slow_ema": max(ex[:2])},
                    "fidelity": "analogue",
                    "why": "MACD read as its fast/slow EMA cross; the signal line is not judged"}
        return {"family": "trend_ma_cross", "params": None, "fidelity": "nearest_family",
                "why": "MACD used, lengths not read (family defaults)"}
    if "bb" in kinds:
        n, k = first("bb"), first("bb", "dev")
        orient = band_orientation(code)
        if orient == "breakout":
            return {"family": None, "params": None, "fidelity": "unmapped",
                    "why": (f"band BREAKOUT (continuation) on BB({n and int(n)}, {k}): no "
                            "registered family trades a band break as continuation")}
        return {"family": "mean_reversion_bollinger",
                "params": ({"bb_n": int(n), **({"bb_k": float(k)} if k else {})}
                           if n and orient == "reversion" else None),
                "fidelity": "exact" if n and orient == "reversion" else "nearest_family",
                "why": "Bollinger band fade read from the code" if orient == "reversion"
                       else "Bollinger bands used, entry side not read"}
    if "donchian" in kinds:
        return {"family": "level_breakout", "params": None, "fidelity": "nearest_family",
                "why": (f"channel/Donchian breakout (lookback {first('donchian')}); nearest "
                        "registered family is the level breakout, judged on its defaults")}
    if re.search(r"day_?(high|low|range)|prev(ious)?_?day_?(high|low)|\bpd[hl]\b", low):
        return {"family": "level_breakout", "params": None, "fidelity": "nearest_family",
                "why": ("prior-day high/low/range breakout read from the code (dual-thrust "
                        "shape); nearest registered family is the level breakout")}
    if "mom" in kinds:
        n = first("mom")
        return {"family": "momentum_volgate",
                "params": {"mom_n": int(n)} if n else None,
                "fidelity": "analogue" if n else "nearest_family",
                "why": "momentum / rate-of-change read; judged with the family's volatility gate"}
    if re.search(r"\bvolume\b", low) and re.search(r"volume\w*\s*>\s*[\w.]*\s*\*", low):
        return {"family": "volume_spike", "params": None, "fidelity": "nearest_family",
                "why": "volume multiple of its average read from the code"}
    if "keltner" in kinds:
        n, k = first("keltner"), first("keltner", "dev")
        orient = band_orientation(code)
        return {"family": None, "params": None, "fidelity": "unmapped",
                "why": (f"Keltner channel ({n and int(n)}, {k}) "
                        + ("BREAKOUT (continuation)" if orient == "breakout" else
                           "FADE" if orient == "reversion" else "entry side unread")
                        + ": no registered family is a Keltner channel rule")}
    named = sorted(kinds)
    return {"family": None, "params": None, "fidelity": "unmapped",
            "why": ("indicators " + ", ".join(named) + " map to no registered family"
                    if named else "no indicator call recognised")}


def parse_code(src: str, path: str = "") -> dict[str, Any]:
    """The whole static reading of one file. Never executes, imports or compiles `src`."""
    language = detect_language(src, path)
    code = strip_comments(src, language)
    tab = symbol_table(code)
    calls = _read_calls(code, language, tab)
    coverage: float | None = None
    partial = None
    terms: list[str] = []
    try:
        from mt5desk.compiler import parse_source
        ir = parse_source(code, name=path or "unnamed", language=language)
        coverage, partial = round(float(ir.coverage), 3), bool(ir.partial)
        terms = [t.render() for t in ir.terms]
    except Exception:
        pass
    reading: dict[str, Any] = {"language": language, "calls": calls, "coverage": coverage,
                               "partial": partial, "terms": terms, "bindings": len(tab)}
    reading["map"] = map_to_family(reading, code, tab)
    reading["venue_native"] = bool(VENUE_NATIVE.search(code))
    return reading


# ============================================================================ instruments

def _universe() -> dict[str, dict[str, Any]]:
    try:
        d = json.loads(UNIVERSE.read_text("utf-8"))
        return {str(k).upper(): (v if isinstance(v, dict) else {}) for k, v in d.items()} \
            if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _is_crypto(sym: str) -> bool:
    from research import universe_policy as up
    return up.asset_class_of(sym) in {"crypto", "cryptocurrency"}


def map_instruments(src: str, ground: dict[str, Any], family: str | None,
                    universe: set[str]) -> tuple[list[str], str, Counter[str]]:
    """(Fusion symbols this cell may be minted on, basis, dropped-by-reason)."""
    from research import universe_policy as up
    drops: Counter[str] = Counter()
    crypto_ground = str(ground.get("venue") or "") == "crypto_exchange"
    named: list[str] = []
    if crypto_ground:
        for base, _q in _PAIR.findall(src):
            s = f"{base}USD"
            if s in universe and s not in named:
                named.append(s)
    try:
        from libs.research.mechanism_claims import resolve_instruments
        for s in resolve_instruments(src, universe).get("analogues") or []:
            if s.upper() in universe and s.upper() not in named:
                named.append(s.upper())
    except Exception:
        pass
    basis = "named_in_code"
    if not named:
        named = [s for s in (ground.get("default_instruments") or []) if s.upper() in universe]
        basis = "ground_default (declared mechanism transfer: the code names no instrument)"
    out: list[str] = []
    for s in named:
        if crypto_ground and not _is_crypto(s):
            drops["crypto_ground_non_crypto_cfd"] += 1
            continue
        if not up.may_hypothesise(s, family):
            drops[f"lane_{up.lane(s)}"] += 1
            continue
        out.append(s)
    return out, basis, drops


# ============================================================================ network routes

def _get(url: str, *, accept: str = "", timeout: float = 20.0) -> tuple[int | None, str, str]:
    """(status, text, error) through the desk's polite fetcher; never raises."""
    hdr = {"User-Agent": "quant-cell-emitter"}
    if accept:
        hdr["Accept"] = accept
    tok = os.environ.get("GITHUB_TOKEN")
    if tok and "api.github.com" in url:
        hdr["Authorization"] = f"Bearer {tok}"
    try:
        from libs.data import polite_fetch as pf
        r = pf.get(url, headers=hdr, timeout=timeout, retries=1, leg=LEG, max_bytes=2_000_000)
        return r.status, (r.text if r.ok else ""), (r.error or "")
    except Exception as exc:                                  # transport, import
        return None, "", f"{type(exc).__name__}: {str(exc)[:120]}"


def _match_globs(path: str, globs: list[str], exts: tuple[str, ...]) -> bool:
    if not path.lower().endswith(exts):
        return False
    return any(fnmatch.fnmatch(path, g) for g in globs) if globs else True


def list_files(ground: dict[str, Any], exts: tuple[str, ...]) -> tuple[list[dict[str, str]],
                                                                        str, str]:
    """(files [{path, url, sha}], listing basis, error). Seed paths are the fallback listing."""
    route = str(ground.get("route") or "")
    repo = str(ground.get("repo") or "")
    branch = str(ground.get("branch") or "master")
    globs = [str(g) for g in ground.get("globs") or []]
    err = ""
    if route in {"github_repo", "gitee_repo"}:
        api = (f"{GITHUB_API}/repos/{repo}/git/trees/{branch}?recursive=1" if route ==
               "github_repo" else f"{GITEE_API}/repos/{repo}/git/trees/{branch}?recursive=1")
        raw = (f"{GITHUB_RAW}/{repo}/{branch}/{{path}}" if route == "github_repo"
               else f"https://gitee.com/{repo}/raw/{branch}/{{path}}")
        status, text, e = _get(api, accept="application/vnd.github+json")
        if status and 200 <= status < 300 and text:
            try:
                tree = json.loads(text).get("tree") or []
                files = [{"path": t["path"], "url": raw.format(path=t["path"]),
                          "sha": str(t.get("sha") or "")}
                         for t in tree if t.get("type") == "blob"
                         and _match_globs(str(t.get("path")), globs, exts)]
                return sorted(files, key=lambda f: f["path"]), "api_tree", ""
            except (ValueError, AttributeError, KeyError) as exc:
                err = f"tree unreadable: {type(exc).__name__}"
        else:
            err = f"tree HTTP {status}: {e[:80]}" if status else f"tree unreachable: {e[:80]}"
        seeds = [str(p) for p in ground.get("paths") or []]
        return ([{"path": p, "url": raw.format(path=p), "sha": ""} for p in seeds],
                "seed_paths" if seeds else "none", err)
    if route == "github_code_search":
        if not os.environ.get("GITHUB_TOKEN"):
            return [], "none", "NEEDS_TOKEN: GitHub code search is authenticated-only"
        from urllib.parse import quote
        status, text, e = _get(f"{GITHUB_API}/search/code?per_page=50&q="
                               f"{quote(str(ground.get('query') or ''))}",
                               accept="application/vnd.github+json")
        if not (status and 200 <= status < 300 and text):
            return [], "none", f"search HTTP {status}: {e[:80]}"
        items = (json.loads(text).get("items") or []) if text else []
        return ([{"path": f"{it['repository']['full_name']}/{it['path']}",
                  "url": f"{GITHUB_RAW}/{it['repository']['full_name']}/HEAD/{it['path']}",
                  "sha": str(it.get("sha") or "")} for it in items
                 if isinstance(it, dict) and it.get("repository")], "code_search", "")
    if route == "page_code":
        status, text, e = _get(str(ground.get("url") or ""))
        if not (status and 200 <= status < 300 and text):
            return [], "none", f"listing HTTP {status}: {e[:80]}"
        from urllib.parse import urljoin
        pat = re.compile(str(ground.get("link_pattern") or r"$^"))
        links = sorted({urljoin(str(ground["url"]), m.group(0)) for m in pat.finditer(text)})
        return [{"path": u, "url": u, "sha": ""} for u in links], "page_links", ""
    return [], "none", f"unknown route {route!r}"


def code_from_page(page: str) -> str:
    """Source held in a page's <pre>/<code> blocks (an open-source script page), or ''."""
    import html as _html
    blocks = re.findall(r"(?is)<(?:pre|code)[^>]*>(.*?)</(?:pre|code)>", page)
    text = "\n".join(_html.unescape(re.sub(r"(?s)<[^>]+>", "", b)) for b in blocks)
    return text if re.search(r"strategy\.|ta\.|//@version|OnTick|iMA\(", text) else ""


# ============================================================================ the pass

def _load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _atomic_write(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False, default=str), "utf-8")
    os.replace(tmp, path)


def rows_for_file(src: str, path: str, url: str, ground: dict[str, Any],
                  universe: set[str], *, fixture: bool = False
                  ) -> tuple[list[dict[str, Any]], dict[str, Any], Counter[str]]:
    """(donation rows, the reading, drops) for one fetched file."""
    drops: Counter[str] = Counter()
    reading = parse_code(src, path)
    if not reading["calls"] and not reading["terms"] and not reading["map"].get("family"):
        drops["no_rule_recognised"] += 1
        return [], reading, drops
    if reading["venue_native"]:
        # Funding, perpetuals, liquidations and exchange books do not exist on a CFD. On any
        # ground this is exchange-native mechanics; the cell is dropped and counted.
        drops["crypto_venue_native_mechanism"] += 1
        return [], reading, drops
    mp = reading["map"]
    fam, params = mp.get("family"), mp.get("params")
    if params is not None and reading.get("partial"):
        # A LOW-COVERAGE FILE IS A COMPONENT TEST, AND SAYS SO. `mt5desk/compiler.py` refuses to
        # ABLATE a partial parse because a decomposition of a rule set the parser mostly invented
        # produces numbers. This is not a decomposition: the family and the lookbacks were READ,
        # literally, and the cell tests exactly that component. Demoting it to the family's
        # defaults would throw away the author's numbers and test something nobody wrote. So the
        # recipe stands, the fidelity says `component` and the note names the coverage, so no
        # reader mistakes the cell for the whole published system.
        mp = {**mp, "fidelity": "component",
              "why": (mp["why"] + f"; the file also holds rules this reader did not account for "
                      f"(coverage {reading['coverage']}): the cell tests this component only")}
    symbols, basis, idrops = map_instruments(src, ground, fam, universe)
    drops.update(idrops)
    if not symbols:
        drops["no_admissible_instrument"] += 1
        return [], reading, drops
    digest = hashlib.sha256(src.encode("utf-8", "replace")).hexdigest()
    readout = "; ".join(f"{c['kind']}({'' if c['period'] is None else int(c['period'])}"
                        f"{'' if c.get('dev') is None else ', ' + str(c['dev'])})"
                        for c in reading["calls"][:12])
    base = {
        "source": SOURCE, "ground": ground.get("name"), "region": ground.get("region"),
        "url": url, "file": path, "license": ground.get("license"),
        "language": reading["language"], "content_sha256": digest,
        "coverage": reading["coverage"], "fidelity": mp["fidelity"],
        "instrument_basis": basis, "symbols": symbols,
        "code_copied": False, "venue": ground.get("venue") or "open",
        "title": f"{ground.get('name')}: {Path(path).name} -> {fam or 'unmapped'}",
        "mechanism": mp["why"],
        "readout": readout,
        **({"fixture": True} if fixture else {}),
    }
    if fam and params is not None:
        return [{**base, "kind": "code_rule", "family": fam, "params": params}], reading, drops
    # STRUCTURED_HYPOTHESIS: the family (when there is one) without params -> the family's
    # defaults; no family -> the compiler's prose path and then deepening, reading attached.
    row = {**base, "kind": "hypothesis",
           "testable_claim": (f"{mp['why']}. Published code {path} reads: {readout}. "
                              + ("Judge the registered family on its defaults." if fam else
                                 "No registered family carries this; extract the exact rule.")),
           "text": f"{mp['why']}. Code reading: {readout}. Terms: {', '.join(reading['terms'])}"}
    if fam:
        row["family"] = fam
    return [row], reading, drops


def _trial_census(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """This pass's cells priced by the desk's effective-trial ledger (participation ratio)."""
    cells = [(r, s) for r in rows for s in r.get("symbols") or []]
    if not cells:
        return {"n_raw": 0, "n_effective": 0.0, "basis": "no cell emitted this pass"}
    try:
        from libs.research import trial_ledger as tl
        trials = [tl.Trial(hashlib.sha256(f"{r['content_sha256']}|{s}".encode()).hexdigest()[:16],
                           str(r.get("family") or "unmapped"),
                           {"symbol": s, "mechanism": str(r.get("family") or "unmapped"),
                            "data": "ohlc", "source": SOURCE,
                            "geography": str(r.get("region") or "")},
                           dict(r.get("params") or {}))
                  for r, s in cells]
        c = tl.census(trials)
        return {"n_raw": int(c.n_raw), "n_effective": round(float(c.n_effective), 3),
                "inflation": round(float(c.inflation), 4), "n_families": len(c.families),
                "basis": ("libs.research.trial_ledger.census over this pass's cells; the docket "
                          "charges them again when miner_candidate_compiler admits them")}
    except Exception as exc:
        return {"n_raw": len(cells), "n_effective": None,
                "basis": f"{UNMEASURED}: trial_ledger ({type(exc).__name__}: {exc})"}


def _fixture_files(fixtures: Path) -> dict[str, list[dict[str, str]]]:
    """Ground name -> files, from the fixture MANIFEST (recorded or synthetic, marked each)."""
    man = _load_json(fixtures / "MANIFEST.json", {})
    out: dict[str, list[dict[str, str]]] = {}
    for f in man.get("files") or []:
        out.setdefault(str(f["ground"]), []).append(
            {"path": str(f.get("path") or f["file"]), "url": str(f.get("url") or ""),
             "sha": "", "local": str(fixtures / f["file"]), "provenance": str(f.get("kind"))})
    return out


def run(*, budget_s: float = 300.0, write: bool = True, fixtures: Path | None = None,
        sources: Path = SOURCES, state_path: Path = STATE, donate_dir: Path = DONATE_DIR,
        report_path: Path = REPORT) -> dict[str, Any]:
    t0 = time.monotonic()
    cap = None
    with contextlib.suppress(ValueError):
        cap = float(os.environ.get("QUANT_LEG_BUDGET_S") or 0) or None
    budget = min(budget_s, cap - WRITE_RESERVE_S) if cap else budget_s
    reg = _load_json(sources, {})
    grounds: list[dict[str, Any]] = [g for g in reg.get("grounds") or [] if isinstance(g, dict)]
    policy = reg.get("policy") or {}
    per_ground = int(policy.get("files_per_ground") or 12)
    max_bytes = int(policy.get("max_file_bytes") or 400_000)
    exts = tuple(str(e).lower() for e in policy.get("extensions") or [".py", ".pine", ".mq5"])
    uni_rows = _universe()
    universe = set(uni_rows)
    fixture_map = _fixture_files(fixtures) if fixtures else None
    state = {} if fixture_map is not None else _load_json(state_path, {})
    cursors: dict[str, int] = dict(state.get("file_cursor") or {})
    seen: dict[str, str] = dict(state.get("seen") or {})
    start = int(state.get("ground_cursor") or 0) % max(1, len(grounds))
    order = grounds[start:] + grounds[:start]
    per: dict[str, dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    worked = 0
    for g in order:
        name = str(g.get("name"))
        st: dict[str, Any] = {"route": g.get("route"), "region": g.get("region"),
                              "listed": 0, "fetched": 0, "parsed": 0, "mapped_exact": 0,
                              "mapped_hypothesis": 0, "unmapped": 0, "donated": 0, "cells": 0,
                              "unchanged_skipped": 0, "dropped": Counter(), "families": Counter(),
                              "status": "", "listing": ""}
        per[name] = st
        if time.monotonic() - t0 > budget:
            st["status"] = "NOT_REACHED_THIS_PASS (budget)"
            for k in ("listed", "fetched", "parsed", "donated", "cells"):
                st[k] = None                                    # UNMEASURED, never 0
            continue
        worked += 1
        if fixture_map is not None:
            files = fixture_map.get(name, [])
            st["listing"], err = "FIXTURE", ""
            if not files:
                st["status"] = "NO_FIXTURE"
                for k in ("listed", "fetched", "parsed", "donated", "cells"):
                    st[k] = None
                continue
        else:
            files, st["listing"], err = list_files(g, exts)
        st["listed"] = len(files)
        if not files:
            st["status"] = f"UNREACHED: {err}" if err else "EMPTY_LISTING"
            for k in ("fetched", "parsed", "donated", "cells"):
                st[k] = None                                    # UNMEASURED, never 0
            continue
        off = int(cursors.get(name) or 0) % len(files)
        batch = (files[off:] + files[:off])[:per_ground]
        cursors[name] = (off + len(batch)) % len(files)
        http_errors: Counter[str] = Counter()
        for f in batch:
            if time.monotonic() - t0 > budget:
                st["dropped"]["budget_stop"] += 1
                break
            if "local" in f:
                try:
                    src = Path(f["local"]).read_text("utf-8", errors="replace")
                except OSError:
                    st["dropped"]["fixture_missing"] += 1
                    continue
            else:
                status, text, _e = _get(f["url"])
                if not (status and 200 <= status < 300 and text):
                    http_errors[str(status or "transport")] += 1
                    st["dropped"][f"fetch_{status or 'transport'}"] += 1
                    continue
                src = code_from_page(text) if g.get("route") == "page_code" else text
                if not src:
                    st["dropped"]["no_code_block"] += 1
                    continue
            st["fetched"] += 1
            if len(src.encode("utf-8", "replace")) > max_bytes:
                st["dropped"]["file_too_large"] += 1
                continue
            digest = hashlib.sha256(src.encode("utf-8", "replace")).hexdigest()
            if fixture_map is None and digest in seen:
                st["unchanged_skipped"] += 1
                continue
            got, reading, drops = rows_for_file(src, f["path"], f["url"] or f["path"], g,
                                                universe, fixture=fixture_map is not None)
            st["dropped"].update(drops)
            if reading["calls"] or reading["terms"] or reading["map"].get("family"):
                st["parsed"] += 1
            for r in got:
                if r["kind"] == "code_rule":
                    st["mapped_exact"] += 1
                elif r.get("family"):
                    st["mapped_hypothesis"] += 1
                else:
                    st["unmapped"] += 1
                st["families"][str(r.get("family") or "unmapped")] += 1
                st["donated"] += 1
                st["cells"] += len(r["symbols"])
            rows.extend(got)
            if fixture_map is None:
                seen[digest] = datetime.now(tz=UTC).isoformat(timespec="seconds")
        if http_errors and not st["fetched"]:
            st["status"] = "UNREACHED: raw fetch " + ", ".join(f"{k}x{v}"
                                                             for k, v in http_errors.items())
        else:
            st["status"] = "OK" + (f" (listing fell back to seeds: {err})" if err else "")
    for st in per.values():
        st["dropped"] = dict(st["dropped"])
        st["families"] = dict(st["families"])
    census = _trial_census(rows)
    now = datetime.now(tz=UTC)
    donated_to: str | None = None
    if write and rows and fixture_map is None:
        out = donate_dir / f"discoveries_cellemitter_{now:%Y%m%d_%H%M%S}.json"
        _atomic_write(out, rows)
        donated_to = str(out)
        with contextlib.suppress(Exception):
            from libs.data.datahub import record_mined_source
            for r in rows:
                record_mined_source(repo=str(r.get("ground")), url=str(r.get("url")),
                                    commit=str(r.get("content_sha256"))[:16],
                                    license_=str(r.get("license")), file=str(r.get("file")),
                                    mechanism=str(r.get("mechanism"))[:200], code_copied=False)
    if write and fixture_map is None:
        if len(seen) > SEEN_CAP:
            seen = dict(sorted(seen.items(), key=lambda kv: kv[1])[-SEEN_CAP:])
        _atomic_write(state_path, {"ground_cursor": (start + max(1, worked)) % max(1, len(grounds)),
                                   "file_cursor": cursors, "seen": seen,
                                   "updated_utc": now.isoformat(timespec="seconds")})
    totals = {k: sum(int(st[k] or 0) for st in per.values())
              for k in ("listed", "fetched", "parsed", "mapped_exact", "mapped_hypothesis",
                        "unmapped", "donated", "cells", "unchanged_skipped")}
    reached = [n for n, st in per.items() if str(st["status"]).startswith("OK")]
    doc = {
        "generated_utc": now.isoformat(timespec="seconds"),
        "organ": SOURCE,
        "mode": "FIXTURE" if fixture_map is not None else "LIVE",
        "fixture_note": ("FIXTURE RUN: files read from the recorded/synthetic fixture set named "
                         "in its MANIFEST; nothing donated; this is NOT a live yield")
                        if fixture_map is not None else None,
        "grounds": len(grounds), "grounds_worked": worked, "grounds_reached": len(reached),
        "yield": (totals if reached else {**dict.fromkeys(totals),
                                          "why": f"{UNMEASURED}: no ground reachable this pass"}),
        "per_source": per,
        "trial_census": census,
        "donated_to": donated_to,
        "cursor": {"ground_cursor_start": start, "file_cursor": cursors},
        "consumers": [
            "desks/mt5/research/miner_candidate_compiler.py reads data/intelligence/** -> "
            "EXACT_RECIPE for kind=code_rule rows, STRUCTURED_HYPOTHESIS for kind=hypothesis rows "
            "naming a registered family, deepening for the rest -> docket -> gauntlet",
            "desks/mt5/reports/CELL_EMITTER.json -> per-ground yield and drop reasons",
        ],
        "boundary": ("MINTS ONLY, through the compiler's door. Static parse; nothing fetched is "
                     "executed or copied. Crypto-exchange ground maps onto Fusion crypto CFDs "
                     "only; share CFDs only through universe_policy.may_hypothesise."),
        "seconds": round(time.monotonic() - t0, 2),
    }
    if write:
        _atomic_write(report_path, doc)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=300.0)
    ap.add_argument("--dry-run", action="store_true", help="write nothing")
    ap.add_argument("--fixtures", type=Path, default=None,
                    help="read files from a fixture MANIFEST instead of the network")
    ap.add_argument("--report", type=Path, default=REPORT)
    a = ap.parse_args(argv)
    doc = run(budget_s=a.budget_s, write=not a.dry_run, fixtures=a.fixtures,
              report_path=a.report)
    y = doc["yield"]
    print(f"CELL EMITTER [{doc['mode']}]  grounds {doc['grounds_worked']}/{doc['grounds']} worked, "
          f"{doc['grounds_reached']} reached")
    print(f"  fetched {y.get('fetched')} parsed {y.get('parsed')} exact {y.get('mapped_exact')} "
          f"hypothesis {y.get('mapped_hypothesis')} unmapped {y.get('unmapped')} "
          f"donated {y.get('donated')} cells {y.get('cells')}")
    for n, st in doc["per_source"].items():
        print(f"   {n[:34]:<34} {str(st['status'])[:60]:<60} fetched={st['fetched']} "
              f"donated={st['donated']} drops={st['dropped']}")
    tc = doc["trial_census"]
    print(f"  trials: n_raw {tc.get('n_raw')} n_effective {tc.get('n_effective')}")
    if doc["donated_to"]:
        print(f"donated: {doc['donated_to']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
