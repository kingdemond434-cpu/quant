#!/usr/bin/env python3
"""THE WORLD CRAWLER -- hourly, worldwide, multilingual, and it finds its own ground.

    "this scraper world wide should be hourly too ... deep and wide fully covering every bit of
     world wide web fr edges n datas"                        -- the principal, 2026-08/09

WHAT MAKES THIS DIFFERENT FROM THE FORTY MINERS. Each miner is pointed at a source a person
chose, which sets the desk's coverage to the ceiling of human attention: a ground nobody thought
of is one the desk can never reach, and its absence is indistinguishable from emptiness (L1.28a).
This crawler is pointed at a FRONTIER it grows itself -- every page it reads is also read for
links, every link that carries trading vocabulary in any language becomes a candidate source, and
every source carries its own measured yield so the next hour is spent where the last one paid.

MAX ROI IS THE SCHEDULER, and it is the only thing standing between "wide" and "useless". An hour
buys a bounded number of fetches; `world_frontier.due()` spends them highest-posterior-yield
first, shrunk toward the host mean and then the global mean so a lucky first fetch cannot capture
the budget, with an exploration bonus that keeps never-tried ground reachable and a per-host cap
that stops one prolific domain owning the hour. Depth and width are the same knob and this is it.

EVERYTHING IT FETCHES IS VAULTED POINT-IN-TIME. Raw bytes, gzipped, keyed by content hash with
the fetch timestamp -- never overwritten, so a claim can always be re-read against what the page
said WHEN IT SAID IT rather than what it says now. A crawler without that is a rumour mill: the
evidence for a candidate evaporates the moment the source edits the page.

WHAT IT EMITS. Rows in the miner-discovery contract that
`research/miner_candidate_compiler.py` already consumes, so a page stating an exact rule
(registered family + params + a symbol the broker quotes) becomes an executable candidate that
reaches the ten gates this hour, and everything else becomes a LEAD that steers the family-free
search. No row is invented and no family is guessed from a buzzword -- the compiler's own law.
"""
from __future__ import annotations

import argparse
import contextlib
import gzip
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import quote, urljoin, urlparse, urlsplit, urlunsplit

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "side_channels"))
sys.path.insert(0, str(BASE))

import world_frontier as wf  # noqa: E402  # type: ignore[import-not-found]

WORLD = BASE / "data" / "intelligence" / "world"
VAULT = WORLD / "vault"
REPORT = BASE / "reports" / "world_crawl.json"

#: Browser UA, because a bot string is refused or served a stub by a large share of the ground
#: this desk needs -- the gotcha recorded in the free-data-plane findings, where a healthy source
#: reads as dead purely from its User-Agent.
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

#: Per-request and whole-run budgets. The run budget is what makes this safe to put on an hourly
#: timer beside everything else on a 3.8 GB box: it stops on the clock, not when it runs out of
#: world, and the frontier makes the next hour resume rather than restart.
FETCH_TIMEOUT_S = 12
RUN_BUDGET_S = 900
DEFAULT_FETCHES = 60
MAX_BYTES = 1_500_000
#: Politeness gap between two requests to the same host, seconds.
HOST_GAP_S = 2.0
#: The frontier may not grow without bound on a box with no swap. New links past this are
#: DROPPED AND COUNTED, never silently discarded.
MAX_FRONTIER = 40_000


def log(msg: str) -> None:
    print(f"[{datetime.now(tz=UTC):%H:%M:%S}] {msg}", flush=True)


class _Extract(HTMLParser):
    """Links, anchor text and visible text. One pass, no third-party parser on the money box."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self.text: list[str] = []
        self._href: str | None = None
        self._skip = 0
        self.lang = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        d = dict(attrs)
        if tag in ("script", "style", "noscript"):
            self._skip += 1
        elif tag == "a" and d.get("href"):
            self._href = str(d["href"])
        elif tag == "html" and d.get("lang"):
            self.lang = str(d["lang"])[:8]

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "noscript") and self._skip:
            self._skip -= 1
        elif tag == "a":
            self._href = None

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        chunk = data.strip()
        if not chunk:
            return
        self.text.append(chunk)
        if self._href:
            self.links.append((self._href, chunk[:120]))


def _ascii_url(url: str) -> str:
    """Percent-encode a URL's non-ASCII parts. urllib raises UnicodeEncodeError without this.

    MEASURED on the first live crawl: `note.com/hashtag/システムトレード` -- a Japanese hub, exactly
    the ground this crawler exists to reach -- died with UnicodeEncodeError and was charged to
    that source as a failure. A crawler that cannot fetch a non-ASCII URL is not multilingual,
    and the failure is indistinguishable from a dead host.
    """
    try:
        url.encode("ascii")
    except UnicodeEncodeError:
        parts = urlsplit(url)
        netloc = parts.netloc
        with contextlib.suppress(UnicodeError):
            netloc = parts.netloc.encode("idna").decode("ascii")
        return urlunsplit((parts.scheme, netloc, quote(parts.path, safe="/%"),
                           quote(parts.query, safe="=&%?"), quote(parts.fragment, safe="%")))
    return url


def fetch(url: str) -> tuple[bytes | None, str]:
    """Bytes, or None with the reason. NEVER raises -- one bad page must not end the hour."""
    try:
        req = urllib.request.Request(_ascii_url(url), headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            # No language preference: asking for English is how a crawler that is supposed to
            # cover the world quietly stops covering most of it.
            "Accept-Language": "*",
        })
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_S) as resp:
            ctype = str(resp.headers.get("Content-Type", ""))
            if "html" not in ctype and "text" not in ctype and "json" not in ctype:
                return None, f"content-type {ctype.split(';')[0] or 'unknown'}"
            return resp.read(MAX_BYTES), ""
    except urllib.error.HTTPError as exc:
        return None, f"HTTP {exc.code}"
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return None, f"{type(exc).__name__}: {str(exc)[:60]}"
    except Exception as exc:
        return None, f"{type(exc).__name__}: {str(exc)[:60]}"


def vault(url: str, raw: bytes) -> str:
    """Store the fetch point-in-time and return its content hash.

    NEVER OVERWRITTEN. The same page fetched twice with the same bytes writes once; changed bytes
    write a second file. A candidate's evidence therefore survives the source editing the page,
    which is the difference between a citation and a rumour.
    """
    digest = hashlib.sha256(raw).hexdigest()[:20]
    host = (urlparse(url).netloc or "unknown").replace(":", "_")[:60]
    out = VAULT / host / f"{digest}.gz"
    if out.exists():
        return digest
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({
        "url": url,
        "fetched_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "sha256_20": digest,
        "bytes": len(raw),
    }).encode() + b"\n" + raw
    out.write_bytes(gzip.compress(payload))
    return digest


# ------------------------------------------------------------------------------ what a page says

#: Timeframe tokens, multilingual where the word differs. Used only to ANNOTATE a lead -- the
#: compiler decides what becomes executable, and this module never guesses a family.
_TF = re.compile(r"\b(M1|M5|M15|M30|H1|H4|D1|W1|MN|1m|5m|15m|30m|1h|4h|daily|weekly|"
                 r"分钟|小时|日线|時間足|日足)\b", re.IGNORECASE)

#: Mechanism vocabulary. A HIT IS A LEAD, NEVER A FAMILY. The compiler admits a family only when
#: the page names a registered one explicitly with params; this list exists so a lead can say
#: what it is ABOUT and steer the family-free search, which is the desk's own rule that a family
#: may not be guessed from a buzzword.
_MECH = {
    "breakout": r"breakout|break out|突破|ブレイク|돌파|пробой|ruptura",
    "mean_reversion": r"mean revers|reversion|回归|逆張り|평균회귀|возврат",
    "momentum": r"momentum|trend follow|动量|趋势|モメンタム|추세|импульс|tendencia",
    "carry": r"carry trade|swap rate|息差|carry|キャリー|캐리",
    "session": r"asian session|london open|new york open|亚盘|欧盘|美盘|東京時間|ロンドン",
    "gap": r"\bgap\b|跳空|窓開け|갭",
    "volatility": r"volatility|波动率|ボラティリティ|변동성|волатильность",
    "seasonality": r"seasonal|day of week|turn of month|季节性|曜日|계절성",
    "correlation": r"correlation|相关性|相関|상관관계|корреляц",
    "orderflow": r"order flow|liquidity|流动性|オーダーフロー|유동성|ликвидн",
}
_MECH_RE = {k: re.compile(v, re.IGNORECASE) for k, v in _MECH.items()}

#: A symbol claim is a 6-letter FX pair or a metal/index the desk might quote. Resolved against
#: the live registry by the compiler -- this only proposes.
_SYM = re.compile(r"\b(?:[A-Z]{6}|XAU[A-Z]{3}|XAG[A-Z]{3}|US30|US500|NAS100|GER40|UK100)\b")


def read_page(raw: bytes, url: str) -> dict[str, Any]:
    """Links, language and the trading claims a page makes. Pure; no network, no state."""
    try:
        text = raw.decode("utf-8", errors="replace")
    except Exception:
        return {"links": [], "symbols": [], "timeframes": [], "patterns": [], "lang": "",
                "title": "", "text_len": 0}
    parser = _Extract()
    with contextlib.suppress(Exception):
        parser.feed(text)                       # a malformed page still yields what it parsed
    body = " ".join(parser.text)[:400_000]

    title = ""
    m = re.search(r"<title[^>]*>(.*?)</title>", text, re.IGNORECASE | re.DOTALL)
    if m:
        title = re.sub(r"\s+", " ", m.group(1)).strip()[:200]

    return {
        "links": [(urljoin(url, href), anchor) for href, anchor in parser.links[:400]],
        "symbols": sorted(set(_SYM.findall(body)))[:24],
        "timeframes": sorted({t.upper() for t in _TF.findall(body)})[:8],
        "patterns": sorted({k for k, rx in _MECH_RE.items() if rx.search(body)}),
        "lang": parser.lang,
        "title": title,
        "text_len": len(body),
    }


def to_discovery(url: str, page: dict[str, Any], digest: str) -> dict[str, Any] | None:
    """A page as a miner-contract row, or None when it claims nothing worth carrying.

    NOTHING IS INVENTED HERE. `symbols` are tokens the page actually contains and the compiler
    resolves them against the live Fusion registry; `patterns` say what the page is ABOUT so the
    family-free search can be steered; no `family` or `params` is emitted, because this crawler
    cannot know that a page's prose is a registered family's exact rule and guessing one is the
    precise failure `miner_candidate_compiler` was written to stop.

    Confidence is the count of independent things the page asserted, not a feeling: a page naming
    a symbol, a timeframe and a mechanism is worth more than one naming a symbol.
    """
    if not page["symbols"] and not page["patterns"]:
        return None
    signals = (bool(page["symbols"]) + bool(page["timeframes"]) + bool(page["patterns"]))
    return {
        "source": "world_crawler",
        "title": page["title"] or url[:120],
        "url": url,
        "published": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "symbols": page["symbols"],
        "timeframes": page["timeframes"],
        "patterns": page["patterns"],
        "confidence": round(0.15 + 0.20 * signals, 2),
        # PROVENANCE, so a candidate that reaches the gauntlet can be traced to the exact bytes
        # that proposed it -- the vault entry is keyed by this hash.
        "lang": page["lang"],
        "vault_sha": digest,
        "host": urlparse(url).netloc,
    }


# ------------------------------------------------------------------------------------ the crawl

#: Ground the desk starts from when the frontier is empty. A SEED, NEVER A LIMIT -- the same law
#: `fetch_universe.SEED_CANDIDATES` follows. Every one of these is a hub whose links lead outward,
#: chosen so the first hour reaches several languages rather than one; after that the frontier is
#: whatever the crawler found, and this list stops mattering.
SEEDS = (
    "https://www.mql5.com/en/code/mt5/experts",
    "https://www.mql5.com/zh/code",
    "https://www.mql5.com/ja/code",
    "https://www.forexfactory.com/forums",
    "https://www.reddit.com/r/algotrading/top/?t=week",
    "https://quantocracy.com/",
    "https://www.quantstart.com/articles/",
    "https://xueqiu.com/",
    "https://www.joinquant.com/help/api/help",
    "https://uqer.datayes.com/",
    "https://zhuanlan.zhihu.com/quant",
    "https://qiita.com/tags/systemtrade",
    "https://note.com/hashtag/システムトレード",
    "https://smart-lab.ru/blog/",
    "https://www.rankia.com/foros/bolsa",
    "https://github.com/topics/algorithmic-trading",
    "https://github.com/topics/mt5",
    "https://arxiv.org/list/q-fin.TR/recent",
    "https://papers.ssrn.com/sol3/JELJOUR_Results.cfm?form_name=journalBrowse&journal_id=203",
)


def seed(sources: dict[str, wf.Source]) -> int:
    added = 0
    for url in SEEDS:
        if wf.add(sources, url, via="seed"):
            added += 1
    return added


def crawl(budget: int = DEFAULT_FETCHES, run_budget_s: int = RUN_BUDGET_S,
          seconds_per_host: float = HOST_GAP_S) -> dict[str, Any]:
    """One hour's crawl. Returns the report it writes."""
    started = time.time()
    sources = wf.load()
    n_seeded = seed(sources)
    if n_seeded:
        log(f"seeded {n_seeded} hub(s); frontier now {len(sources)}")

    picked = wf.due(sources, budget)
    log(f"frontier {len(sources)} source(s) across "
        f"{len({s.host for s in sources.values()})} host(s); crawling {len(picked)} this pass")

    rows: list[dict[str, Any]] = []
    discovered = dropped = unchanged = 0
    failures: Counter[str] = Counter()
    langs: Counter[str] = Counter()
    last_host_hit: dict[str, float] = {}

    for src in picked:
        if time.time() - started > run_budget_s:
            log(f"run budget {run_budget_s}s spent; {len(picked)} planned, stopping here. "
                f"The frontier resumes next hour rather than restarting.")
            break

        gap = seconds_per_host - (time.time() - last_host_hit.get(src.host, 0.0))
        if gap > 0:
            time.sleep(min(gap, seconds_per_host))
        last_host_hit[src.host] = time.time()

        raw, why = fetch(src.url)
        src.fetches += 1
        src.last_fetched = datetime.now(tz=UTC).isoformat(timespec="seconds")
        if raw is None:
            src.failures += 1
            src.consecutive_failures += 1
            failures[why.split(":")[0]] += 1
            continue
        src.consecutive_failures = 0

        digest = vault(src.url, raw)
        if digest == src.last_hash:
            # UNCHANGED IS A MEASUREMENT, not a wasted fetch: it decays this source's score so
            # the hour moves to ground that is actually moving.
            src.unchanged_streak += 1
            unchanged += 1
            continue
        src.last_hash, src.unchanged_streak = digest, 0

        page = read_page(raw, src.url)
        if page["lang"]:
            src.lang = page["lang"]
        langs[src.lang or "??"] += 1

        row = to_discovery(src.url, page, digest)
        if row:
            rows.append(row)
            src.leads += 1

        # RECURSION: every page read is also read for where to go next. This is the whole
        # difference between a crawler and a list of miners.
        for href, anchor in page["links"]:
            if len(sources) >= MAX_FRONTIER:
                dropped += 1
                continue
            if wf.worth_following(href, anchor) and wf.add(sources, href, via=src.url):
                discovered += 1

    wf.save(sources, note=f"crawl {datetime.now(tz=UTC):%Y-%m-%dT%H:%MZ}")

    elapsed = round(time.time() - started, 1)
    report = {
        "generated_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "elapsed_s": elapsed,
        "planned": len(picked),
        "fetched": sum(1 for s in picked if s.last_fetched),
        "rows_emitted": len(rows),
        "new_sources_discovered": discovered,
        "frontier_size": len(sources),
        "frontier_hosts": len({s.host for s in sources.values()}),
        "unchanged_pages": unchanged,
        "dropped_at_frontier_cap": dropped,
        "languages": dict(langs.most_common()),
        "failures": dict(failures.most_common()),
        # THE CAP IS REPORTED, NOT SILENT. A crawler that quietly stops discovering because it
        # hit a bound looks exactly like a web that ran out of pages (L1.28a).
        "frontier_cap": MAX_FRONTIER,
        "note": ("Rows are LEADS in the miner-discovery contract. No family or params is emitted: "
                 "miner_candidate_compiler admits an executable candidate only from a page that "
                 "names a registered family explicitly, and guessing one from a buzzword is the "
                 "failure it exists to prevent."),
    }

    if rows:
        stamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M")
        out = WORLD / f"discoveries_{stamp}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(rows, indent=1), encoding="utf-8")
        log(f"-> {out.relative_to(BASE)} ({len(rows)} row(s))")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=1), encoding="utf-8")
    log(f"crawled {report['fetched']}/{report['planned']} in {elapsed}s | "
        f"{len(rows)} lead(s) | +{discovered} new source(s) | "
        f"frontier {len(sources)} across {report['frontier_hosts']} host(s) | "
        f"langs {dict(langs.most_common(6))}")
    if failures:
        log(f"failures: {dict(failures.most_common(6))}")
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fetches", type=int, default=DEFAULT_FETCHES)
    ap.add_argument("--budget-s", type=int, default=RUN_BUDGET_S)
    ap.add_argument("--host-gap", type=float, default=HOST_GAP_S)
    args = ap.parse_args()
    crawl(args.fetches, args.budget_s, args.host_gap)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
