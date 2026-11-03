"""PROP-FIRM PAYOUT SHOWCASES -> STRATEGY CLAIMS -> CHARGED GAUNTLET CELLS (2026-11-03).

THE ASK (principal 2026-10-30, BACKLOG row 38): reverse-engineer the top public payout earners
and payout leaderboards of FTMO, Topstep and the famous MT5 prop firms worldwide into gauntlet
cells, as an extension of the absurd-return reverse-engineering miner or beside it, whichever
gives the most focus and ROI -- and make sure the producer actually produces cells.

WHAT THE PUBLIC GROUND ACTUALLY HOLDS (surveyed 2026-11-03, written down so nobody re-surveys it):
  * Payout LEADERBOARDS carry no mechanism. FXIFY shows a masked name, a country and an amount;
    The5ers shows first name + initial + amount; FTMO's leaderboard rows load client-side and the
    served HTML has none; fundedtrading.com publishes firm-wallet totals and says it never shows
    traders. A name and a dollar figure cannot be turned into fills -- doing so would be
    fabrication, the thing provider_reverse refuses (book_forensics header, the HTML-blob rule).
  * The MECHANISM lives in the firms' own published trader stories and interviews (FTMO blog
    "Successful Traders Stories" / "Top Traders: Strategies", e.g. "how a gold scalper secured
    $50,333 in 2 weeks"; The5ers, FundedNext, Topstep, E8, FXIFY spotlights). Those state the
    instrument, the session, the style, the R:R and the holding period in prose.
  * Firms publish SELECTION base rates. Topstep's 2025 disclosure: 16.8% of Combines completed,
    51.8% of individuals reached Funded at least once, 33.3% of Funded participants received a
    payout, 0.71% of Express participants called to Live. That is the survivorship of the ground:
    a showcase is drawn from the top tail of a population that mostly failed.

SO THIS IS SEPARATE FROM THE GENOME, ON PURPOSE. The trader genome (book_forensics) measures
style base rates over alive + dead statements; a story corpus has no dead rows, so feeding it to
those base rates would print survivor-only rates as population ones. Here a story is an IDEA
SOURCE (the 10-13 ruling: idea provenance never blocks a cell; method is what is audited), and
the cells go through the SAME door the genome uses: proposer_common.screen -> deflate -> donate,
with every look charged (alt_proxies._donate, null passes into null_pass_trials.jsonl).

PIPELINE, each stage counted so conversion is visible (PROP_SHOWCASE.json `funnel`):
  harvest   firm sitemaps (robots.txt Sitemap lines, else /sitemap.xml) -> story-slug URLs ->
            polite fetch (robots consulted, unreadable robots = NOT fetched, 3 s spacing, a cap
            per firm per pass, no login, no cookies, no paywall/CAPTCHA/rate-limit crossing) ->
            raw text vaulted under data/intelligence/prop_showcase/ (gitignored; never in the
            public repo -- only the structured claims and the URL leave the box).
  extract   deterministic lexicon: instruments, sessions, styles, stated R:R, holding horizon,
            stated payout. No LLM seat sees the text (cheap, reproducible, auditable).
  cells     (style, session) -> registered family + a SMALL preregistered grid; instruments
            mapped to the desk's MT5 symbols (futures stories -> the CFD on the same underlying).
            Support = distinct stories backing one cell; cells ranked by support.
  screen    pc.screen on the desk's own H1 bars at the fill-hour cost; deflated over every look
            the pass ran (variants included). Proposals donated; nulls charged.

SESSION HOURS ARE BROKER STAMP HOURS (NY+7, the desk's clock; families read stamp hours, see
families._h1). On NY+7 the London and New York opens are fixed stamps year-round (London 08:00
= stamp 10, NY 09:30 = stamp 16:30 -> 16), except the 2-3 weeks a year the US and UK DST dates
differ. Tokyo 09:00 JST = stamp 02 (US summer) / 03 (US winter); the grid carries both.

IT PROPOSES, IT NEVER PROMOTES. Nothing here writes a sleeve, certificate, clock or book.
Yield to certificates, forward enrolment and promotable sleeves is measured downstream by
productivity_census (source `prop_showcase_story`), and this report copies that row back so the
producer sees its own conversion every pass.

    python desks/mt5/research/prop_showcase_miner.py [--apply] [--no-fetch]
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
SOURCE = "prop_showcase_story"
INTEL = DESK / "data" / "intelligence" / "prop_showcase"
CLAIMS = DESK / "data" / "prop_showcase_claims.jsonl"
SEEN = INTEL / "seen.json"
REPORT = DESK / "reports" / "PROP_SHOWCASE.json"
PRODUCER_YIELD = DESK / "reports" / "PRODUCER_YIELD.json"
PRODUCTIVITY_CENSUS = DESK / "reports" / "PRODUCTIVITY_CENSUS.json"
NULL_TRIALS = DESK / "data" / "null_pass_trials.jsonl"
AGENT = "quant-research-reader/1.0 (+public pages only)"
DELAY_S = 3.0
MAX_NEW_PER_FIRM = 40
MAX_SITEMAPS = 12
MIN_BARS = 3000
#: Cells screened per pass at most (the budget is also wall-clock bounded).
MAX_CELLS = 120

#: Firm-published selection base rates (stamped on every candidate; never a gate).
SELECTION_PRIORS: dict[str, Any] = {
    "topstep_2025": {
        "url": "https://www.topstep.com/",
        "read_utc": "2026-11-03",
        "combines_completed": 0.168, "reached_funded_once": 0.518,
        "funded_received_payout": 0.333, "express_called_to_live": 0.0071,
        "quote": ("33.3% of all individual participants at the Funded Level received a "
                  "payout")},
    "rule": ("a showcase is the top tail of a population that mostly failed; the story is a "
             "hypothesis source, the gauntlet and the forward lane are the evidence"),
}

#: Public story ground per firm. `paths` keeps the sitemap to its blog/news trees; `slug` picks
#: trader stories and strategy write-ups out of them. Firms are MT5/CFD or futures (Topstep,
#: Apex: their futures stories map to the CFD on the same underlying).
FIRMS: dict[str, dict[str, Any]] = {
    "ftmo": {"home": "https://ftmo.com", "paths": ("/blog/", "/en/blog/")},
    "the5ers": {"home": "https://the5ers.com", "paths": ("/blog", "/trader", "/success")},
    "fundednext": {"home": "https://fundednext.com", "paths": ("/blog", "/success")},
    "topstep": {"home": "https://www.topstep.com", "paths": ("/blog", "/trader")},
    "e8": {"home": "https://e8markets.com", "paths": ("/blog", "/news")},
    "fxify": {"home": "https://fxify.com", "paths": ("/blog", "/news")},
    "fundingpips": {"home": "https://fundingpips.com", "paths": ("/blog",)},
    "alpha_capital": {"home": "https://alphacapitalgroup.uk", "paths": ("/blog", "/news")},
    "apex": {"home": "https://apextraderfunding.com", "paths": ("/blog",)},
    "fintokei": {"home": "https://www.fintokei.com", "paths": ("/blog", "/jp/blog")},
}
STORY_SLUG = re.compile(
    r"(trader|scalp|secur|earn|reward|payout|interview|stor(y|ies)|spotlight|strateg|funded|"
    r"success|journey|profit|withdraw|how-[a-z]+-[a-z]+-)", re.I)

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
                out.append(("asia_momentum", {"asia_start": windows[0][0],
                                              "asia_end": windows[0][1], **extra}))
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
        elif style == "news":
            out.append(("usd_session_shock", {**extra}))
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


# ------------------------------------------------------------------------------- harvest
class _Fetcher:
    """Polite GET: robots consulted per host (unreadable = refuse), fixed spacing, no cookies."""

    def __init__(self, delay_s: float = DELAY_S) -> None:
        self.delay_s = delay_s
        self.robots: dict[str, Any] = {}
        self.last = 0.0
        self.log: dict[str, int] = {}

    def _count(self, k: str) -> None:
        self.log[k] = self.log.get(k, 0) + 1

    def _raw(self, url: str, limit: int = 3_000_000) -> tuple[int, bytes]:
        """One GET through the desk's polite_fetch (certifi trust store, header/meta charset,
        per-host spacing) with retries=0, so a 429 stays a counted wall, never a retry loop."""
        wait = self.delay_s - (time.monotonic() - self.last)
        if wait > 0:
            time.sleep(wait)
        self.last = time.monotonic()
        try:
            from libs.data import polite_fetch as pf
        except Exception:
            pf = None
        if pf is not None:
            r = pf.get(url, headers={"User-Agent": AGENT}, retries=0, max_bytes=limit,
                       leg=SOURCE)
            return int(r.status or 0), (r.text or "").encode("utf-8")
        req = urllib.request.Request(url, headers={"User-Agent": AGENT})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                body = resp.read(limit)
                if resp.headers.get("Content-Encoding") == "gzip":
                    body = gzip.decompress(body)
                return int(resp.status), body
        except urllib.error.HTTPError as exc:
            return int(exc.code), b""
        except Exception:
            return 0, b""

    def robot(self, home: str) -> Any:
        host = urllib.parse.urlsplit(home).netloc
        if host not in self.robots:
            from urllib.robotparser import RobotFileParser
            code, body = self._raw(f"{urllib.parse.urlsplit(home).scheme}://{host}/robots.txt")
            if code in (401, 403, 429) or code == 0 or code >= 500:
                self.robots[host] = None           # unreadable or walled: fetch nothing here
                self._count("robots_refused")
            else:
                rp = RobotFileParser()
                rp.parse(body.decode("utf-8", "replace").splitlines() if code == 200 else [])
                self.robots[host] = rp
        return self.robots[host]

    def get(self, url: str) -> bytes | None:
        rp = self.robot(url)
        if rp is None or not rp.can_fetch(AGENT, url):
            self._count("robots_disallowed")
            return None
        code, body = self._raw(url)
        if code in (401, 402, 403, 429):
            self._count(f"walled_{code}")          # a wall is a counted absence, never crossed
            return None
        if code != 200:
            self._count(f"http_{code}")
            return None
        self._count("fetched")
        return body


def _sitemap_urls(f: _Fetcher, home: str) -> list[str]:
    rp = f.robot(home)
    if rp is None:
        return []
    maps = list(rp.site_maps() or []) or [home.rstrip("/") + "/sitemap.xml",
                                          home.rstrip("/") + "/sitemap_index.xml"]
    urls: list[str] = []
    seen_maps: set[str] = set()
    while maps and len(seen_maps) < MAX_SITEMAPS:
        m = maps.pop(0)
        if m in seen_maps:
            continue
        seen_maps.add(m)
        body = f.get(m)
        if not body:
            continue
        locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", body.decode("utf-8", "replace"))
        for loc in locs:
            loc = html.unescape(loc)
            if loc.endswith(".xml") or ".xml?" in loc:
                if re.search(r"post|blog|news|stor|article|page", loc, re.I):
                    maps.append(loc)
            else:
                urls.append(loc)
    return urls


def _story_urls(urls: list[str], paths: tuple[str, ...]) -> list[str]:
    out = []
    for u in urls:
        p = urllib.parse.urlsplit(u).path
        if any(p.startswith(x) for x in paths) and STORY_SLUG.search(p.rsplit("/", 2)[-2]
                                                                     if p.endswith("/")
                                                                     else p.rsplit("/", 1)[-1]):
            out.append(u)
    return out


def _text(body: bytes) -> tuple[str, str | None, str]:
    """(visible text, published date if the page states one, title)."""
    s = body.decode("utf-8", "replace")
    pub = None
    m = re.search(r"(?:article:published_time|datePublished)[\"']?[^>]{0,40}?(?:content=|:)"
                  r"\s*[\"']([^\"']+)", s)
    if m:
        pub = m.group(1)[:25]
    tm = re.search(r"<title[^>]*>(.*?)</title>", s, re.S | re.I)
    title = html.unescape(re.sub(r"\s+", " ", tm.group(1))).strip()[:200] if tm else ""
    s = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip(), pub, title


def _load_seen() -> dict[str, str]:
    try:
        return json.loads(SEEN.read_text("utf-8"))
    except (OSError, ValueError):
        return {}


def harvest(fetcher: _Fetcher | None = None, firms: dict[str, dict[str, Any]] | None = None,
            budget_s: float = 1500.0) -> dict[str, Any]:
    """New stories -> claim rows appended to CLAIMS. Raw text vaulted on the box only."""
    f = fetcher or _Fetcher()
    started = time.monotonic()
    seen = _load_seen()
    rep: dict[str, Any] = {"by_firm": {}}
    new_claims: list[dict[str, Any]] = []
    for firm, cfg in (firms or FIRMS).items():
        if time.monotonic() - started > budget_s:
            rep["by_firm"][firm] = {"skipped": "budget"}
            continue
        urls = _sitemap_urls(f, cfg["home"])
        stories = [u for u in _story_urls(urls, cfg["paths"]) if u not in seen]
        row = {"sitemap_urls": len(urls), "story_urls_new": len(stories), "read": 0,
               "claims_with_mechanism": 0}
        for u in stories[:MAX_NEW_PER_FIRM]:
            if time.monotonic() - started > budget_s:
                break
            body = f.get(u)
            now = datetime.now(UTC).isoformat(timespec="seconds")
            seen[u] = now
            if not body:
                continue
            text, pub, title = _text(body)
            digest = hashlib.sha256(text.encode()).hexdigest()
            INTEL.mkdir(parents=True, exist_ok=True)
            vault = INTEL / f"{digest[:16]}.txt.gz"
            if not vault.exists():
                vault.write_bytes(gzip.compress(text.encode()))
            row["read"] += 1
            claim = {"firm": firm, "url": u, "title": title, "published_time": pub,
                     "available_time": now, "knowable_from": pub or now,
                     "text_sha256": digest, **extract(title + " " + text)}
            if claim["styles"] and claim["instruments"]:
                row["claims_with_mechanism"] += 1
            new_claims.append(claim)
        rep["by_firm"][firm] = row
    if new_claims:
        CLAIMS.parent.mkdir(parents=True, exist_ok=True)
        with CLAIMS.open("a", encoding="utf-8") as fh:
            for c in new_claims:
                fh.write(json.dumps(c, sort_keys=True) + "\n")
    INTEL.mkdir(parents=True, exist_ok=True)
    SEEN.write_text(json.dumps(seen, indent=0), encoding="utf-8")
    rep["fetch_log"] = f.log
    rep["new_claims"] = len(new_claims)
    return rep


def load_claims(path: Path | None = None) -> list[dict[str, Any]]:
    """Newest claim per URL."""
    best: dict[str, dict[str, Any]] = {}
    try:
        lines = (path or CLAIMS).read_text("utf-8").splitlines()
    except OSError:
        return []
    for ln in lines:
        try:
            c = json.loads(ln)
        except ValueError:
            continue
        if isinstance(c, dict) and c.get("url"):
            best[c["url"]] = c
    return list(best.values())


# ------------------------------------------------------------------------------- screen + donate
def _family_fn(name: str) -> Any:
    try:
        from mt5desk import families
    except ImportError:
        return None
    fn = getattr(families, f"family_{name}", None)
    return fn if callable(fn) else None


def propose(claims: list[dict[str, Any]], budget_s: float = 1200.0,
            write: bool = True) -> dict[str, Any]:
    from research import proposer_common as pc
    try:
        from research.universe_policy import may_hypothesise
    except Exception:
        def may_hypothesise(_s: str) -> bool:                   # type: ignore[misc]
            return True
    started = time.monotonic()
    meta = pc.universe_meta()
    have = {p.stem.removesuffix("_H1") for p in pc.UNI.glob("*_H1.parquet")}
    allc = cells(claims, {s for s in have if may_hypothesise(s)})
    screened: list[dict[str, Any]] = []
    skipped: dict[str, int] = {}

    def skip(why: str) -> None:
        skipped[why] = skipped.get(why, 0) + 1

    bars_cache: dict[str, Any] = {}
    for c in allc[:MAX_CELLS]:
        if time.monotonic() - started > budget_s:
            skip("budget exhausted")
            continue
        fn = _family_fn(c["family"])
        if fn is None:
            skip(f"family {c['family']} not registered")
            continue
        sym = c["symbol"]
        if sym not in bars_cache:
            bars_cache[sym] = pc.bars(sym)
        d = bars_cache[sym]
        if d is None or len(d) < MIN_BARS:
            skip("too few H1 bars")
            continue
        cost = pc.cost_frac(sym, meta, d["close"])
        if cost is None:
            skip("no contract terms to price the round trip")
            continue
        try:
            sig = fn(d, **c["params"])
        except Exception as exc:
            skip(f"family raised {type(exc).__name__}")
            continue
        sc = pc.screen(d, sig or [], cost, pc.artifact_hours(d)) if sig else None
        body = dict(sc) if sc else {"n_independent": 0, "gross_per_trade": 0.0,
                                     "t_gross": 0.0, "clears_cost": False,
                                     "net_per_trade": round(-cost, 8),
                                     "cost_frac": round(cost, 8)}
        body["t_gross"] = float(body.get("t_gross") or 0.0)
        pid = hashlib.sha256(json.dumps(c["params"], sort_keys=True).encode()).hexdigest()[:8]
        screened.append({"cell": f"{sym}.{c['family']}.showcase_{pid}", **c, **body,
                         "screened": bool(sc)})
    if len(allc) > MAX_CELLS:
        skipped["over the per-pass cell cap (next pass)"] = len(allc) - MAX_CELLS
    swept = pc.deflate(screened)
    proposals = pc.best_per_cell(swept)
    cands = []
    for r in proposals:
        cands.append(pc.candidate(
            SOURCE, r["symbol"], r["family"], dict(r["params"]),
            mechanism=(f"prop-firm payout showcase: {'/'.join(r['styles'])} "
                       f"{'/'.join(r['sessions']) or 'any-session'} on {r['symbol']}, backed by "
                       f"{r['support']} published funded-trader stor(y/ies) across "
                       f"{len(r['firms'])} firm(s) ({', '.join(r['firms'])}); survivor-only "
                       f"ground, see selection_prior"),
            title=f"{r['cell']} from prop-firm payout showcases",
            evidence={**{k: r.get(k) for k in ("n_independent", "gross_per_trade",
                                              "net_per_trade", "cost_frac", "t_gross",
                                              "t_deflated_sweep", "n_tests_sweep",
                                              "t_deflated_lifetime", "n_tests_lifetime")},
                      "showcase_support": r["support"], "showcase_firms": r["firms"],
                      "showcase_stories": r["stories"], "selection_prior": SELECTION_PRIORS}))
    rep: dict[str, Any] = {"cells_built": len(allc), "tests_run": len(screened),
                           "cells_proposed": len(proposals), "skipped": skipped,
                           "top_cells": [{k: r.get(k) for k in (
                               "cell", "support", "firms", "styles", "sessions",
                               "n_independent", "t_gross", "t_deflated_sweep")}
                               for r in swept[:25]]}
    if write and screened:
        from research import alt_proxies as ap
        paths = ap.Paths(NULL_TRIALS.parent.parent)
        by_family: dict[str, int] = {}
        for r in screened:
            by_family[str(r["family"])] = by_family.get(str(r["family"]), 0) + 1
        rep["charge"] = ap._donate(paths, SOURCE, cands, len(screened), by_family,
                                   datetime.now(tz=UTC))
    return rep


def _own_yield() -> dict[str, Any]:
    """This producer's conversion, copied back from the census every pass: the PRODUCER_YIELD
    verdict (PRODUCING / STARVED / DEAD) and every PRODUCTIVITY_CENSUS number keyed to it
    (certificates, forward, live -- the census attributes by lineage, never by guesswork)."""
    out: dict[str, Any] = {}
    try:
        doc = json.loads(PRODUCER_YIELD.read_text("utf-8"))
        rows = [r for r in doc.get("producers") or []
                if isinstance(r, dict) and "prop_showcase" in str(r.get("producer", ""))]
        out["producer_yield"] = rows[0] if rows else "not yet in the census (first passes)"
    except (OSError, ValueError):
        out["producer_yield"] = "UNMEASURED: PRODUCER_YIELD.json unreadable"
    found: dict[str, Any] = {}

    def walk(o: Any, path: str, depth: int) -> None:
        if depth > 4 or not isinstance(o, dict):
            return
        for k, v in o.items():
            if "prop_showcase" in str(k):
                found[f"{path}/{k}".lstrip("/")] = v
            else:
                walk(v, f"{path}/{k}", depth + 1)
    try:
        walk(json.loads(PRODUCTIVITY_CENSUS.read_text("utf-8")), "", 0)
        out["census"] = found or "no certificate/forward/live row attributed yet"
    except (OSError, ValueError):
        out["census"] = "UNMEASURED: PRODUCTIVITY_CENSUS.json unreadable"
    return out


def run(budget_s: float = 1800.0, write: bool = True, fetch: bool = True) -> dict[str, Any]:
    """The daily clock: harvest new stories, then screen and donate the claim cells."""
    for p in (str(DESK), str(DESK / "research"), str(ROOT)):
        if p not in sys.path:
            sys.path.insert(0, p)
    t0 = time.monotonic()
    h = harvest(budget_s=budget_s * 0.4) if fetch else {"skipped": "--no-fetch"}
    claims = load_claims()
    mech = [c for c in claims if c.get("styles") and c.get("instruments")]
    prop = propose(claims, budget_s=max(60.0, budget_s - (time.monotonic() - t0)),
                   write=write)
    doc = {"at": datetime.now(UTC).isoformat(timespec="seconds"), "source": SOURCE,
           "harvest": h,
           "funnel": {"stories_held": len(claims), "stories_with_mechanism": len(mech),
                      "cells_built": prop["cells_built"], "cells_screened": prop["tests_run"],
                      "cells_proposed": prop["cells_proposed"],
                      "donated": (prop.get("charge") or {}).get("donated", 0)},
           "by_firm_claims": {f: sum(1 for c in mech if c["firm"] == f) for f in FIRMS},
           "proposer": prop, "yield": _own_yield(), "selection_prior": SELECTION_PRIORS,
           "rules": {"fetch": "public pages only; robots consulted, unreadable = not fetched; "
                              "walls (401/402/403/429) counted, never crossed; raw text stays "
                              "on the box",
                     "trials": "every screened cell is a look, deflated in-sweep and charged "
                               "to the lifetime count (donation or null_pass_trials)",
                     "promotes": "never"}}
    if write:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    return {"tests_run": prop["tests_run"], "cells_proposed": prop["cells_proposed"],
            "stories": len(claims)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--no-fetch", action="store_true")
    a = ap.parse_args(argv)
    print(json.dumps(run(write=a.apply, fetch=not a.no_fetch), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
