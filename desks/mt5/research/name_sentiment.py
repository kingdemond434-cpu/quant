#!/usr/bin/env python3
"""PER-SHARE NEWS SENTIMENT -- a daily, PIT, cross-sectionally ranked score per share CFD (QG25-25).

WHAT EXISTED. `nlp_event_factors` scores text per COUNTRY (macro and policy tone); `libs/data/
free_stack.py` carries a bull/bear word count for forum posts. Nothing scored NEWS per SHARE,
nothing handled negation, and nothing mapped a mention to a share CFD (card diff_first:
EXISTS_INCOMPLETE).

THE TEXT. Only news the desk already holds: `document` rows in the sensor ledger (news_event_stream
writes them) and `data/news_captures.jsonl`. NEVER Reddit, StockTwits, X/Twitter or Discord: a row
whose source or URL names one is dropped and counted (`SOCIAL_REFUSED`).

THE LEXICON IS THIS DESK'S OWN (no Loughran-McDonald, no VADER): a compact finance vocabulary where
buy/sell/beat/miss/upgrade/downgrade carry their market meaning, with n-grams that outrank their
words ("cuts guidance" is not "cuts" plus "guidance"), negation inside a three-token window ("did
not beat" is a miss; "failed to beat" too), and a small emoji polarity table.

NER-LITE. Mentions map to share CFDs through aliases DERIVED from universe.json symbols (CamelCase
split and the concatenated form, corporate suffixes stripped) plus a small ticker table. A company
name that is a common word (Apple, Target, Visa, Oracle, Meta, ...) counts only when it is
Capitalised AND either a ticker of that company appears in the document or a finance context word
sits within six tokens of it ("APPLE was delicious" maps to nothing). The alias table's hash is
recorded on every output: the mapping is frozen per vintage (card PIT requirement).

PIT. A document is usable on decision day d only if the desk HELD it by d's cut (13:00 UTC, before
the US cash open): its instant is max(knowable_at, received_at); a document without a world stamp
is bounded by receipt. The day's score is available at the cut; the contract's return runs from
close(d) to close(d+1), strictly after it.

AGGREGATION. Per name per day the mean document score (names without news that day are ABSENT,
never zero), then a cross-sectional z within the equity class (needs MIN_NAMES names that day).

WHERE IT GOES. Share CFDs may only be hypothesised in the cross-sectional class books or the news
lane (`universe_policy.may_hypothesise`). No existing class-book family consumes an external
per-name score -- every `cross_sectional_class_*` ranks a PRICE transform of the class panel it
loads itself -- so this organ emits NO exogenous_conditioner cells on shares (that family is refused
for them) and writes the per-name lake series plus a wide panel. `CLASS_BOOK_NEEDS` states exactly
what a consuming family must do.

CONTRACT (card QG25-25). Daily top-minus-bottom tercile next-day return spread of the sentiment
rank, net of cost, against the same-day cross_sectional_class_reversal spread on the same names;
the null permutes the scores across names within each day. GAIN also needs the spread's alpha over
the reversal spread to be positive at t >= 2 (falsifier: "explained by reversal").

    python desks/mt5/research/name_sentiment.py [--days 400] [--dry-run]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import sensor_contract as sc  # noqa: E402
from libs.research import sensor_engines as se  # noqa: E402

ENGINE = "name_sentiment"
REPORT = DESK / "reports" / "NAME_SENTIMENT.json"
NEWS_CAPTURES = DESK / "data" / "news_captures.jsonl"
UNMEASURED = "UNMEASURED"
CUT_HOUR_UTC = 13
MIN_NAMES = 5
#: Cost charged on the spread per day: two legs, each entered and exited (share CFD spread).
COST_BP_PER_DAY = 10.0
N_PERM = 200
CARDS = ["QG25-25"]
FALSIFIER = "No net-of-cost spread or explained by reversal/momentum."
BASELINE = "cross_sectional_class_reversal (1-day lookback, 1-day hold) on the same names"
SOCIAL_REFUSED = ("reddit", "stocktwits", "twitter.com", "x.com/", "discord", "nitter")
CLASS_BOOK_NEEDS = (
    "No existing family consumes this score. A consuming family `cross_sectional_class_score` "
    "(registered in families_cross_sectional.CROSS_SECTIONAL_FAMILIES and "
    "universe_policy.CROSS_SECTIONAL_FAMILIES) needs: params {source: 'ws_name_sentiment', "
    "column: 'sent_z', quantile, hold_d, max_age_h}; at each decision bar it reads every class "
    "member's lake series desks/mt5/data/lake/series/ws_name_sentiment_<member>.csv (or the wide "
    "ws_name_sentiment_panel.csv, column z_<member>) AS OF the bar's UTC stamp (available_time <= "
    "stamp, newest row no older than max_age_h; older = absent, never carried), ranks members "
    "with a value, and returns the same leg Signals as _rank_sides/_signals (long top quantile, "
    "short bottom). MIN_MEMBERS applies to members WITH a score that day.")

# ============================================================================== the lexicon
#: Single words. Weights are this desk's own judgement of finance-news polarity, -3..+3.
WORDS: dict[str, float] = {
    # positive
    "beat": 2.0, "beats": 2.0, "upgrade": 2.0, "upgrades": 2.0, "upgraded": 2.0,
    "outperform": 1.5, "outperforms": 1.5, "overweight": 1.0, "buy": 0.5, "bullish": 1.5,
    "surge": 1.5, "surges": 1.5, "surged": 1.5, "soar": 1.5, "soars": 1.5, "soared": 1.5,
    "rally": 1.0, "rallies": 1.0, "rallied": 1.0, "jump": 1.0, "jumps": 1.0, "jumped": 1.0,
    "gain": 0.5, "gains": 0.5, "rebound": 1.0, "rebounds": 1.0, "record": 1.0, "strong": 1.0,
    "stronger": 1.0, "exceed": 1.5, "exceeds": 1.5, "exceeded": 1.5, "approval": 1.5,
    "approved": 1.5, "wins": 1.0, "won": 1.0, "accelerates": 1.0, "accelerating": 1.0,
    "buyback": 1.0, "profit": 0.5, "profitable": 1.0, "growth": 0.5, "upbeat": 1.5,
    "optimistic": 1.0, "boost": 1.0, "boosts": 1.0, "raises": 0.5, "raised": 0.5,
    # negative
    "miss": -2.0, "misses": -2.0, "missed": -2.0, "downgrade": -2.0, "downgrades": -2.0,
    "downgraded": -2.0, "underperform": -1.5, "underweight": -1.0, "sell": -0.5,
    "bearish": -1.5, "plunge": -2.0, "plunges": -2.0, "plunged": -2.0, "slump": -1.5,
    "slumps": -1.5, "tumble": -1.5, "tumbles": -1.5, "tumbled": -1.5, "fall": -1.0, "falls": -1.0,
    "fell": -1.0, "drop": -1.0, "drops": -1.0, "dropped": -1.0, "slide": -1.0, "slides": -1.0,
    "weak": -1.0, "weaker": -1.0, "warning": -1.5, "warns": -1.5, "warned": -1.5,
    "lawsuit": -1.5, "sued": -1.5, "probe": -1.5, "investigation": -1.5, "subpoena": -1.5,
    "recall": -1.5, "recalls": -1.5, "layoffs": -1.0, "loss": -1.0, "losses": -1.0,
    "delay": -1.0, "delays": -1.0, "delayed": -1.0, "halt": -1.5, "halts": -1.5,
    "fraud": -2.5, "bankruptcy": -3.0, "default": -2.0, "slash": -1.5, "slashes": -1.5,
    "cuts": -0.5, "cut": -0.5, "fined": -1.5, "resigns": -1.0, "downbeat": -1.5,
    "pessimistic": -1.0, "disappointing": -1.5, "disappoint": -1.5, "disappoints": -1.5,
    "shortfall": -1.5,
}
#: N-grams outrank their words (longest match wins, and its tokens are consumed).
PHRASES: dict[tuple[str, ...], float] = {
    ("raises", "guidance"): 2.5, ("raised", "guidance"): 2.5, ("raises", "outlook"): 2.0,
    ("guidance", "raise"): 2.5, ("lifts", "guidance"): 2.5,
    ("cuts", "guidance"): -2.5, ("cut", "guidance"): -2.5, ("guidance", "cut"): -2.5,
    ("lowers", "guidance"): -2.5, ("lowered", "guidance"): -2.5, ("cuts", "outlook"): -2.0,
    ("beat", "estimates"): 2.5, ("beats", "estimates"): 2.5, ("tops", "estimates"): 2.5,
    ("missed", "estimates"): -2.5, ("misses", "estimates"): -2.5,
    ("better", "than", "expected"): 2.0, ("worse", "than", "expected"): -2.0,
    ("price", "target", "raised"): 1.5, ("raises", "price", "target"): 1.5,
    ("price", "target", "cut"): -1.5, ("cuts", "price", "target"): -1.5,
    ("buy", "rating"): 1.5, ("strong", "buy"): 2.0, ("sell", "rating"): -1.5,
    ("sell", "off"): -1.5, ("selloff",): -1.5, ("profit", "warning"): -2.5,
    ("dividend", "cut"): -2.0, ("cuts", "dividend"): -2.0, ("dividend", "increase"): 1.5,
    ("raises", "dividend"): 1.5, ("share", "buyback"): 1.5, ("record", "revenue"): 2.0,
    ("all", "time", "high"): 1.0, ("short", "seller"): -1.5, ("job", "cuts"): -1.0,
}
#: Tokens that flip a sentiment term starting within NEG_WINDOW tokens after them.
NEGATORS = frozenset({"not", "no", "never", "without", "nor", "neither", "hardly", "fail",
                      "fails", "failed", "lack", "lacks"})
NEG_WINDOW = 3
EMOJI: dict[str, float] = {"\U0001F680": 1.5, "\U0001F4C8": 1.0, "\U0001F402": 1.0,
                           "\U0001F44D": 0.5, "\U0001F4B0": 0.5, "\U0001F525": 0.5,
                           "\U0001F4C9": -1.0, "\U0001F43B": -1.0, "\U0001F480": -1.0,
                           "\U0001F631": -1.0, "\U0001F44E": -0.5, "\U0001F921": -1.0}
_MAXN = max(len(k) for k in PHRASES)


def lexicon_version() -> str:
    blob = json.dumps([sorted(WORDS.items()), sorted((" ".join(k), v) for k, v in PHRASES.items()),
                       sorted(NEGATORS), NEG_WINDOW, sorted(EMOJI.items())], ensure_ascii=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:12]


_TOKEN = re.compile(r"\$?[A-Za-z0-9][A-Za-z0-9&']*")


def tokens(text: str) -> list[str]:
    """Original-case tokens; "n't" becomes a separate "not"; a possessive "'s" is dropped."""
    out: list[str] = []
    for raw in _TOKEN.findall(text):
        t = raw
        if t.lower().endswith("n't"):
            stem = t[:-3]
            if stem.lower() in ("ca", "wo"):
                stem = stem + "n"
            if stem:
                out.append(stem)
            out.append("not")
            continue
        if t.lower().endswith("'s"):
            t = t[:-2]
        t = t.strip("'")
        if t:
            out.append(t)
    return out


def score_tokens(toks: Sequence[str]) -> tuple[float, list[tuple[str, float]]]:
    """Sum of term weights with n-gram precedence and 3-token negation. Returns (sum, hits)."""
    low = [t.lower().lstrip("$") for t in toks]
    i, total, hits = 0, 0.0, []
    while i < len(low):
        w: float | None = None
        span = 1
        for n in range(min(_MAXN, len(low) - i), 0, -1):
            key = tuple(low[i:i + n])
            if n > 1 and key in PHRASES:
                w, span = PHRASES[key], n
                break
            if n == 1 and key in PHRASES:
                w = PHRASES[key]
                break
        if w is None:
            w = WORDS.get(low[i])
        if w is not None:
            negated = any(low[j] in NEGATORS for j in range(max(0, i - NEG_WINDOW), i))
            w = -w if negated else w
            total += w
            hits.append((" ".join(low[i:i + span]) + (" [neg]" if negated else ""), w))
        i += span
    return total, hits


def emoji_score(text: str) -> float:
    return sum(EMOJI.get(ch, 0.0) for ch in text)


# ============================================================================== NER-lite
#: Tickers per universe symbol, and extra names. Only symbols the registry lists are used.
TICKERS: dict[str, tuple[str, ...]] = {
    "Apple": ("AAPL",), "NVIDIA": ("NVDA",), "Microsoft": ("MSFT",), "Amazon": ("AMZN",),
    "Meta": ("META", "FB"), "Tesla": ("TSLA",), "Alphabet-A": ("GOOGL",), "Alphabet-C": ("GOOG",),
    "MicronTechnology": ("MU",), "AMD": ("AMD",), "Intel": ("INTC",), "Netflix": ("NFLX",),
    "BankofAmericaCorp": ("BAC",), "JPMorganChase": ("JPM",), "GoldmanSachs": ("GS",),
    "MorganStanley": ("MS",), "WellsFargo": ("WFC",), "Citigroup": ("C",), "Visa": ("V",),
    "Mastercard": ("MA",), "Target": ("TGT",), "Oracle": ("ORCL",), "Dow": ("DOW",),
    "Ford": ("F",), "GeneralMotors": ("GM",), "GeneralElectric": ("GE",), "Boeing": ("BA",),
    "Coca-Cola": ("KO",), "Pepsi": ("PEP",), "Walmart": ("WMT",), "HomeDepot": ("HD",),
    "Snowflake": ("SNOW",), "Booking": ("BKNG",), "Travelers": ("TRV",), "Charter": ("CHTR",),
    "Berkshire": ("BRK",), "3M": ("MMM",), "IBM": ("IBM",), "Broadcom": ("AVGO",),
    "TSMC": ("TSM",), "Salesforce": ("CRM",), "Adobe": ("ADBE",), "Qualcomm": ("QCOM",),
    "BlockInc": ("XYZ", "SQ"), "Uber": ("UBER",), "PayPal": ("PYPL",), "Shopify": ("SHOP",),
}
EXTRA_ALIASES: dict[str, tuple[str, ...]] = {
    "Alphabet-A": ("alphabet", "google"), "Meta": ("facebook",), "BankofAmericaCorp":
    ("bank of america",), "JPMorganChase": ("jpmorgan", "jp morgan"), "Coca-Cola": ("coca cola",),
    "WaltDisney": ("disney",), "Berkshire": ("berkshire hathaway",), "BlockInc": ("block",),
    "MicronTechnology": ("micron",), "PhilipMorrisInternational": ("philip morris",),
    "TSMC": ("taiwan semiconductor",), "UnitedHealth": ("unitedhealth",),
}
#: Aliases that are ordinary words: they need a Capital, and a ticker or context nearby.
AMBIGUOUS = frozenset({"apple", "amazon", "meta", "target", "visa", "oracle", "dow", "ford",
                       "snowflake", "booking", "intel", "travelers", "charter", "block", "coke",
                       "uber", "nike", "shell", "square", "micron"})
CONTEXT = frozenset({"shares", "share", "stock", "stocks", "inc", "corp", "corporation", "company",
                     "earnings", "revenue", "sales", "profit", "ceo", "cfo", "quarter",
                     "quarterly", "guidance", "analyst", "analysts", "nasdaq", "nyse", "investors",
                     "upgrade", "downgrade", "rating", "dividend", "buyback", "results", "fiscal",
                     "valuation", "market", "outlook", "estimates", "rally", "sell", "buy"})
TICKER_STOP = frozenset({"ON", "IT", "ALL", "A", "ARE", "CEO", "GDP", "USA", "EU", "UK", "AI",
                         "US", "OK", "MS", "GS", "C", "V", "F", "MA", "BA", "HD", "GM", "GE"})
_SUFFIX = ("international", "group", "corp", "corporation", "inc", "holdings", "co")


def _split_camel(sym: str) -> str:
    s = re.sub(r"-[A-Z]$", "", sym)
    s = s.replace("-", " ")
    s = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", s)
    return " ".join(s.lower().split())


def _strip_suffix(name: str) -> str:
    parts = name.split()
    while len(parts) > 1 and parts[-1] in _SUFFIX:
        parts.pop()
    return " ".join(parts)


@dataclass(frozen=True)
class AliasTable:
    names: dict[tuple[str, ...], tuple[str, ...]]     # lowercase token tuple -> symbols
    tickers: dict[str, str]                            # TICKER -> symbol
    version: str


def build_aliases(symbols: Iterable[str]) -> AliasTable:
    names: dict[tuple[str, ...], set[str]] = {}
    tick: dict[str, str] = {}
    for sym in sorted(set(symbols)):
        forms = {_split_camel(sym), _strip_suffix(_split_camel(sym)),
                 re.sub(r"[^a-z0-9]", "", _split_camel(sym))}
        forms |= set(EXTRA_ALIASES.get(sym, ()))
        for f in [*forms]:
            if f.endswith("s") and " " not in f and len(f) > 4:
                forms.add(f[:-1])
        for f in forms:
            key = tuple(f.split())
            if key and key != ("",):
                names.setdefault(key, set()).add(sym)
        for t in TICKERS.get(sym, ()):
            tick[t] = sym
    # ONE COMPANY, SEVERAL SHARE CLASSES (Alphabet-A / Alphabet-C): a NAME goes to the first class
    # only, the others are reached by their own ticker, so one story is not counted twice in the
    # cross-section.
    clean: dict[tuple[str, ...], tuple[str, ...]] = {}
    for k, v in names.items():
        bases = {re.sub(r"-[A-Z]$", "", s) for s in v}
        clean[k] = (min(v),) if len(v) > 1 and len(bases) == 1 else tuple(sorted(v))
    blob = json.dumps([sorted((" ".join(k), v) for k, v in clean.items()), sorted(tick.items())])
    return AliasTable(clean, tick, hashlib.sha256(blob.encode()).hexdigest()[:12])


def tickers_in(toks: Sequence[str], table: AliasTable) -> set[str]:
    """Symbols whose ticker appears as $TICKER, or bare upper-case and not in TICKER_STOP."""
    out = set()
    for t in toks:
        bare = t.lstrip("$")
        if bare in table.tickers and (t.startswith("$") or (bare.isupper() and len(bare) > 1
                                                            and bare not in TICKER_STOP)):
            out.add(table.tickers[bare])
    return out


def mentions(toks: Sequence[str], table: AliasTable,
             doc_tickers: set[str] | None = None) -> dict[str, list[int]]:
    """{symbol: [token positions]} with the ambiguity guard applied. `doc_tickers` are the
    tickers anywhere in the document (the guard reads the whole story, not one sentence)."""
    low = [t.lower().lstrip("$") for t in toks]
    ticks = doc_tickers if doc_tickers is not None else tickers_in(toks, table)
    found: dict[str, list[int]] = {}
    for i, t in enumerate(toks):
        bare = t.lstrip("$")
        if bare in table.tickers and (t.startswith("$") or (bare.isupper() and len(bare) > 1
                                                            and bare not in TICKER_STOP)):
            found.setdefault(table.tickers[bare], []).append(i)
    maxn = max((len(k) for k in table.names), default=1)
    i = 0
    while i < len(low):
        hit = None
        for n in range(min(maxn, len(low) - i), 0, -1):
            key = tuple(low[i:i + n])
            if key in table.names:
                hit = (key, n)
                break
        if hit is None:
            i += 1
            continue
        key, n = hit
        syms = table.names[key]
        if " ".join(key) in AMBIGUOUS:
            window = low[max(0, i - 6):i] + low[i + n:i + n + 6]
            ok = toks[i][:1].isupper() and (any(s in ticks for s in syms)
                                            or any(w in CONTEXT for w in window))
            if not ok:
                i += n
                continue
        for s in syms:
            found.setdefault(s, []).append(i)
        i += n
    return found


_SENT = re.compile(r"(?<=[.!?;])\s+|\n+")


def score_document(title: str, text: str, table: AliasTable) -> dict[str, float]:
    """{symbol: score in (-1, 1)}: each sentence's sentiment goes to the names it mentions."""
    sentences = [s for s in [title, *_SENT.split(text or "")] if s and s.strip()]
    ticks = tickers_in(tokens(f"{title} {text}"), table)
    agg: dict[str, float] = {}
    for s in sentences:
        toks = tokens(s)
        named = mentions(toks, table, ticks)
        if not named:
            continue
        val = score_tokens(toks)[0] + emoji_score(s)
        for sym in named:
            agg[sym] = agg.get(sym, 0.0) + val
    return {k: math.tanh(v / 3.0) for k, v in agg.items()}


# ============================================================================== documents
def _social(row: Mapping[str, Any]) -> bool:
    hay = " ".join(str(row.get(k) or "") for k in ("source_id", "source", "url", "raw_pointer",
                                                     "sensor_id", "dataset_id")).lower()
    return any(s in hay for s in SOCIAL_REFUSED)


def held_at(row: Mapping[str, Any]) -> datetime | None:
    """When the DESK held the document: max(knowable, received); receipt alone bounds it."""
    k = sc.parse_time(row.get("knowable_at") or row.get("published_utc")
                      or row.get("published_at"))
    r = sc.parse_time(row.get("received_at") or row.get("found_at") or row.get("fetched_utc"))
    if k is None:
        return r
    return max(k, r) if r is not None else None


def _rows(path: Path, limit: int = 200_000) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict):
                out.append(row)
    return out[-limit:]


def load_documents(now: datetime, days: int, ledger: Any = None,
                   captures: Path = NEWS_CAPTURES) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Every held news document of the last `days`, de-duplicated, social sources refused."""
    led = ledger if ledger is not None else sc.SensorLedger()
    raw: list[dict[str, Any]] = []
    for back in range(days + 1):
        day = (now - timedelta(days=back)).date().isoformat()
        raw.extend(r for r in led.rows(day) if r.get("kind") == "document")
    raw.extend(_rows(captures))
    seen: dict[str, dict[str, Any]] = {}
    acc = {"rows": len(raw), "social_refused": 0, "no_stamp": 0, "after_now": 0, "kept": 0}
    for r in raw:
        if _social(r):
            acc["social_refused"] += 1
            continue
        at = held_at(r)
        if at is None:
            acc["no_stamp"] += 1
            continue
        if at > now:
            acc["after_now"] += 1
            continue
        title = str(r.get("title") or r.get("headline") or r.get("text") or "")[:400]
        body = str(r.get("summary") or r.get("body") or (r.get("text") if r.get("title") else "")
                   or "")[:4000]
        key = hashlib.sha1(" ".join(tokens(title.lower())).encode()).hexdigest()
        doc = {"held_at": at, "title": title, "text": body}
        if key not in seen or at < seen[key]["held_at"]:
            seen[key] = doc
    acc["kept"] = len(seen)
    return sorted(seen.values(), key=lambda d: d["held_at"]), acc


# ============================================================================== aggregation
def cut_of(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, CUT_HOUR_UTC, tzinfo=UTC)


def decision_day(at: datetime) -> date:
    """The first weekday whose cut is at or after `at`."""
    d = at.astimezone(UTC).date()
    if at > cut_of(d):
        d += timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def daily_scores(docs: Sequence[Mapping[str, Any]], table: AliasTable
                 ) -> dict[date, dict[str, tuple[float, int]]]:
    """{day: {symbol: (mean score, n_docs)}} -- only documents held by that day's cut."""
    acc: dict[date, dict[str, list[float]]] = {}
    for d in docs:
        scores = score_document(str(d["title"]), str(d.get("text") or ""), table)
        if not scores:
            continue
        day = decision_day(d["held_at"])
        for sym, v in scores.items():
            acc.setdefault(day, {}).setdefault(sym, []).append(v)
    return {day: {s: (float(np.mean(v)), len(v)) for s, v in names.items()}
            for day, names in acc.items()}


def cross_z(day_scores: Mapping[str, tuple[float, int]], min_names: int = MIN_NAMES
            ) -> dict[str, float]:
    if len(day_scores) < min_names:
        return {}
    vals = np.asarray([v[0] for v in day_scores.values()], dtype=float)
    sd = float(vals.std(ddof=1))
    if sd <= 0:
        return {}
    mu = float(vals.mean())
    return {s: (v[0] - mu) / sd for s, v in day_scores.items()}


# ============================================================================== the contract
def _next_returns(closes: Mapping[str, Sequence[tuple[str, float]]]
                  ) -> tuple[dict[str, dict[str, float]], dict[str, dict[str, float]]]:
    """Per symbol {day: log close(next)/close(day)} and {day: log close(day)/close(prev)}."""
    fwd: dict[str, dict[str, float]] = {}
    back: dict[str, dict[str, float]] = {}
    for s, rows in closes.items():
        rows = sorted(rows)
        f, b = {}, {}
        for i in range(len(rows)):
            if i + 1 < len(rows):
                f[rows[i][0]] = math.log(rows[i + 1][1] / rows[i][1])
            if i > 0:
                b[rows[i][0]] = math.log(rows[i][1] / rows[i - 1][1])
        fwd[s], back[s] = f, b
    return fwd, back


def _tercile_spread(z: Mapping[str, float], ret: Mapping[str, float]) -> float | None:
    names = sorted((s for s in z if s in ret), key=lambda s: z[s])
    k = len(names) // 3
    if len(names) < MIN_NAMES or k < 1:
        return None
    lo, hi = names[:k], names[-k:]
    return float(np.mean([ret[s] for s in hi]) - np.mean([ret[s] for s in lo]))


def spread_contract(zs: Mapping[date, Mapping[str, float]],
                    closes: Mapping[str, Sequence[tuple[str, float]]], *,
                    cost_bp: float = COST_BP_PER_DAY, n_perm: int = N_PERM, seed: int = 17,
                    min_n: int = se.MIN_N) -> dict[str, Any]:
    fwd, back = _next_returns(closes)
    days, spread, rev, perm_inputs = [], [], [], []
    for day in sorted(zs):
        k = day.isoformat()
        z = zs[day]
        ret = {s: fwd[s][k] for s in z if s in fwd and k in fwd[s]}
        past = {s: back[s][k] for s in ret if k in back.get(s, {})}
        sp = _tercile_spread(z, ret)
        rv = _tercile_spread({s: -v for s, v in past.items()}, ret)
        if sp is None or rv is None:
            continue
        days.append(k)
        spread.append(sp - cost_bp / 1e4)
        rev.append(rv - cost_bp / 1e4)
        perm_inputs.append(([z[s] for s in ret], [ret[s] for s in ret]))
    sp_a, rv_a = np.asarray(spread), np.asarray(rev)
    value, base = se.kelly_growth(sp_a), se.kelly_growth(rv_a)
    null_p = None
    if value is not None and len(days) >= 2:
        rng = np.random.default_rng(seed)
        hits = 0
        for _ in range(n_perm):
            ps = []
            for zv, rv_ in perm_inputs:
                zz = dict(zip(range(len(zv)), rng.permutation(zv), strict=True))
                ps.append((_tercile_spread(zz, dict(enumerate(rv_))) or 0.0) - cost_bp / 1e4)
            v = se.kelly_growth(np.asarray(ps))
            hits += int(v is not None and v >= value)
        null_p = round((hits + 1) / (n_perm + 1), 4)
    extra: dict[str, Any] = {"label": "sentiment top-minus-bottom tercile, next day, net",
                             "cost_bp_per_day": cost_bp, "n_days": len(days),
                             "mean_spread_bp": round(float(sp_a.mean()) * 1e4, 3) if days else None,
                             "null": "scores permuted across names within each day"}
    alpha_t = None
    if len(days) >= 30 and float(rv_a.std()) > 0:
        X = np.column_stack([np.ones(len(days)), rv_a])
        beta, *_ = np.linalg.lstsq(X, sp_a, rcond=None)
        resid = sp_a - X @ beta
        s2 = float(resid @ resid) / (len(days) - 2)
        cov = s2 * np.linalg.inv(X.T @ X)
        alpha_t = float(beta[0] / math.sqrt(cov[0, 0])) if cov[0, 0] > 0 else None
        extra.update({"alpha_over_reversal_bp": round(float(beta[0]) * 1e4, 3),
                      "alpha_t": round(alpha_t, 3) if alpha_t is not None else None,
                      "beta_on_reversal": round(float(beta[1]), 4)})
    row = se.contract(engine=ENGINE, cards=CARDS, metric="kelly_growth_annual",
                      baseline=BASELINE, falsifier=FALSIFIER, value=value, baseline_value=base,
                      n=len(days), min_n=min_n, null_p=null_p, extra=extra)
    if row["verdict"] == se.GAIN and not (alpha_t is not None and alpha_t >= 2.0):
        row["verdict"] = se.NO_GAIN
        row["why"] = "the spread is explained by the reversal spread (alpha t < 2)"
    return row


# ============================================================================== the organ
def equity_symbols() -> list[str]:
    try:
        from research import universe_policy as up
        return list(up.class_members("equity"))
    except Exception:
        return []


def bars_daily(symbol: str, now: datetime) -> list[tuple[str, float]]:
    try:
        from macro import market_state as ms
        return ms.daily_closes(ms._chart(symbol), now)
    except Exception:
        return []


def _sid(sym: str) -> str:
    return "ws_name_sentiment_" + re.sub(r"[^a-z0-9]+", "_", sym.lower()).strip("_")


def run(*, now: datetime, days: int = 400, docs: Sequence[Mapping[str, Any]] | None = None,
        symbols: Sequence[str] | None = None, ledger: Any = None,
        closes_fn: Callable[[str, datetime], Sequence[tuple[str, float]]] | None = None,
        lake_root: Path | None = None, contracts_root: Path | None = None,
        report: Path | None = REPORT, dry_run: bool = False, min_n: int = se.MIN_N,
        n_perm: int = N_PERM) -> dict[str, Any]:
    syms = list(symbols) if symbols is not None else equity_symbols()
    table = build_aliases(syms)
    led = ledger if ledger is not None else sc.SensorLedger()
    if docs is None:
        docs, acc = load_documents(now, days, led)
    else:
        acc = {"rows": len(docs), "kept": len(docs), "supplied": 1}
    per_day = {d: v for d, v in daily_scores(docs, table).items() if cut_of(d) <= now}
    zs = {d: z for d, v in per_day.items() if (z := cross_z(v))}
    # ---- lake: per name, plus the wide panel
    lake: dict[str, Any] = {}
    by_sym: dict[str, list[dict[str, Any]]] = {}
    panel: list[dict[str, Any]] = []
    for d in sorted(per_day):
        at = cut_of(d).isoformat()
        prow: dict[str, Any] = {"available_time": at, "event_time": d.isoformat(),
                                "source_id": ENGINE}
        for s, (v, n) in per_day[d].items():
            z = zs.get(d, {}).get(s)
            by_sym.setdefault(s, []).append({"available_time": at, "event_time": d.isoformat(),
                                             "source_id": ENGINE, "sent_score": round(v, 6),
                                             "sent_z": None if z is None else round(z, 6),
                                             "n_docs": n})
            if z is not None:
                prow[f"z_{s}"] = round(z, 6)
        if len(prow) > 3:
            panel.append(prow)
    if not dry_run:
        for s, rows in by_sym.items():
            lake[s] = se.write_lake_series(_sid(s), rows, root=lake_root).get("rows")
        lake["_panel"] = se.write_lake_series("ws_name_sentiment_panel", panel,
                                              root=lake_root).get("rows")
    # ---- contract
    closes_of = closes_fn or bars_daily
    closes = {s: list(closes_of(s, now)) for s in {s for z in zs.values() for s in z}}
    contract_row = spread_contract(zs, closes, min_n=min_n, n_perm=n_perm)
    # ---- ledger: the latest day's z per name
    obs = []
    if zs:
        last = max(zs)
        for s, z in sorted(zs[last].items()):
            v, n = per_day[last][s]
            obs.append(sc.make(
                sensor_id=ENGINE, source_id=ENGINE, metric="news_sentiment_z", entity=s,
                kind="state", sensor_class="news_sentiment", asset_domain="equity",
                value=z, event_time=last.isoformat(), knowable_at=cut_of(last),
                knowable_basis="calendar", received_at=now, surprise_z=None,
                attributes={"sent_score": v, "n_docs": n, "lexicon": lexicon_version(),
                            "aliases": table.version, "cut_hour_utc": CUT_HOUR_UTC}))
    ledger_out: Any = {"status": "DRY_RUN"}
    if not dry_run:
        ledger_out = led.append(obs, now=now) if obs else {"appended": 0}
        se.publish(ENGINE, [contract_row], root=contracts_root,
                   extra={"class_book_needs": CLASS_BOOK_NEEDS})
    doc = {"engine": ENGINE, "at": now.isoformat(timespec="seconds"), "dry_run": dry_run,
           "documents": acc, "symbols": len(syms), "lexicon_version": lexicon_version(),
           "alias_version": table.version, "days_scored": len(per_day), "days_ranked": len(zs),
           "contracts": [contract_row], "lake_rows": lake, "ledger": ledger_out,
           "cells": {"status": "NONE_EMITTED",
                     "why": ("share CFDs may be hypothesised only by CROSS_SECTIONAL_FAMILIES or "
                             "NEWS_LANE_FAMILIES (universe_policy.may_hypothesise); "
                             "exogenous_conditioner is neither")},
           "class_book_needs": CLASS_BOOK_NEEDS, "authority": "NONE",
           "sources_refused": list(SOCIAL_REFUSED)}
    if not dry_run and report is not None:
        report.parent.mkdir(parents=True, exist_ok=True)
        tmp = report.with_suffix(f".tmp{os.getpid()}")
        tmp.write_text(json.dumps(doc, indent=1, sort_keys=True, default=str) + "\n", "utf-8")
        os.replace(tmp, report)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="per-share news sentiment (QG25-25)")
    ap.add_argument("--days", type=int, default=400)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    doc = run(now=datetime.now(UTC), days=a.days, dry_run=a.dry_run)
    print(json.dumps({k: doc[k] for k in ("at", "documents", "days_scored", "days_ranked")}
                     | {"verdict": doc["contracts"][0]["verdict"]}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
