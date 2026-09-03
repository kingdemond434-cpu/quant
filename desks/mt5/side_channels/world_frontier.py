#!/usr/bin/env python3
"""THE CRAWL FRONTIER -- a source list the desk GROWS instead of one a person maintains.

WHY THIS IS SEPARATE FROM THE CRAWLER. The desk already has forty miners, each pointed at a
source somebody chose. That is a coverage ceiling set by human attention: a source nobody thought
of is a source the desk can never reach, and "we have not looked there" becomes indistinguishable
from "there is nothing there" (L1.28a). This module holds the part that has to outlive any single
crawl -- what the desk knows about, what each source has ever been WORTH, and what it learned by
following a link -- so the crawler can be stateless and the knowledge cannot be lost with it.

MAX ROI IS A RANKING, NOT AN ADJECTIVE. Every hour buys a bounded number of fetches, so the only
question that matters is which fetches. Each source carries its own measured yield -- executable
candidates produced per fetch -- and the frontier is spent highest-expected-yield first:

    score = yield_posterior x novelty x freshness_need / cost

with `yield_posterior` shrunk toward the host's family mean, because a source fetched twice that
produced one candidate is not twice as good as one fetched two hundred times for one hundred.
That is the same winner's-curse correction the allocator applies to sleeves, for the same reason.

A SOURCE IS NEVER DELETED, only starved. Deletion loses the evidence that it was tried, which is
how a dead source gets rediscovered and re-crawled forever; a starved one keeps its record and
its score, and revives the moment it produces again.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

BASE = Path(__file__).resolve().parent.parent
WORLD = BASE / "data" / "intelligence" / "world"
FRONTIER = WORLD / "frontier.json"

#: Pseudo-fetches of the no-yield prior. A source must produce more than noise before it out-ranks
#: one with a long record; 8 is roughly "one good hour" and keeps a promising newcomer reachable.
_PRIOR_FETCHES = 8.0

#: Pseudo-fetches of the global prior that a HOST must outweigh before its own mean is believed.
#: Hosts are the unit of politeness and of pooling: a page on a host that has produced before
#: inherits that host's mean, but only in proportion to how much the host has actually been tried.
_HOST_PRIOR = 8.0

#: A source that has failed this many times in a row is starved to the back of the queue. Never
#: removed -- see the module docstring.
_FAIL_STARVE = 6


@dataclass
class Source:
    """One crawlable URL and everything the desk has learned about it."""

    url: str
    host: str = ""
    lang: str = ""
    #: How the desk found it: "seed", or the URL that linked to it. Provenance for a source is
    #: the same requirement as provenance for a candidate.
    discovered_via: str = "seed"
    first_seen: str = ""
    last_fetched: str = ""
    fetches: int = 0
    failures: int = 0
    consecutive_failures: int = 0
    #: Executable candidates and leads this source has ever produced. The numerator of its yield.
    candidates: int = 0
    leads: int = 0
    #: Content hash of the last fetch, so an unchanged page costs nothing to notice.
    last_hash: str = ""
    unchanged_streak: int = 0

    def __post_init__(self) -> None:
        if not self.host:
            self.host = urlparse(self.url).netloc.lower()
        if not self.first_seen:
            self.first_seen = datetime.now(tz=UTC).isoformat(timespec="seconds")


def _read() -> dict[str, Any]:
    try:
        doc = json.loads(FRONTIER.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def load() -> dict[str, Source]:
    """Every known source. An unreadable frontier is EMPTY-AND-SAID-SO, never silently reseeded."""
    raw = _read()
    out: dict[str, Source] = {}
    for url, row in (raw.get("sources") or {}).items():
        if not isinstance(row, dict):
            continue
        known = set(Source.__dataclass_fields__)
        out[url] = Source(**{k: v for k, v in row.items() if k in known})
    return out


def save(sources: dict[str, Source], note: str = "") -> None:
    WORLD.mkdir(parents=True, exist_ok=True)
    hosts: dict[str, int] = {}
    for s in sources.values():
        hosts[s.host] = hosts.get(s.host, 0) + 1
    FRONTIER.write_text(json.dumps({
        "updated_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "n_sources": len(sources),
        "n_hosts": len(hosts),
        "note": note,
        "sources": {u: asdict(s) for u, s in sources.items()},
    }, indent=1), encoding="utf-8")


def host_yield(sources: dict[str, Source]) -> dict[str, tuple[float, float]]:
    """(candidates, fetches) per host -- the pool a page on that host is shrunk toward.

    BOTH NUMBERS, NOT THE RATIO. Returning a bare rate made the pooling a no-op for a host with
    one page: the "host mean" was that page's own rate, so shrinking toward it shrank nothing and
    a source fetched once that got lucky outranked one with two hundred fetches behind it. The
    denominator is what says how much the host's own mean may be believed.
    """
    agg: dict[str, list[float]] = {}
    for s in sources.values():
        agg.setdefault(s.host, [0.0, 0.0])
        agg[s.host][0] += s.candidates + 0.25 * s.leads
        agg[s.host][1] += s.fetches
    return {h: (c, f) for h, (c, f) in agg.items()}


def score(s: Source, hosts: dict[str, tuple[float, float]], global_mean: float) -> float:
    """Expected candidates from spending one fetch here. Higher is crawled sooner.

    SHRUNK TWICE, toward the host and then toward the global mean, exactly as the allocator
    shrinks a sleeve toward its family and then toward no-edge. A page fetched once that happened
    to yield a candidate is not the best source the desk owns, and ranking it first would spend
    every hour re-fetching lucky pages.
    """
    # A LEAD IS WORTH FAR LESS THAN A CANDIDATE, and 0.25 was not far enough. Candidates were
    # zero everywhere, so this ranked purely on leads -- which rewards whatever emits the most
    # LINKS. Measured 2026-09-03: the two biggest frontier expansions were
    # `forexfactory.com/brokers` (247 pages) and `quantt.co.uk/quant-firms` (116), a broker
    # directory and a firm directory. Neither can hold a testable claim, and both outranked
    # every dataset because they are excellent at producing links.
    #
    # 0.05 keeps a lead worth something -- a hub with no candidates yet is still how the
    # frontier grows -- while making one candidate worth twenty leads instead of four.
    raw = (s.candidates + 0.05 * s.leads) / s.fetches if s.fetches else 0.0
    lam = s.fetches / (s.fetches + _PRIOR_FETCHES)

    # THE HOST MEAN IS ITSELF SHRUNK, by how many fetches the host has behind it. Without this
    # the pooling is a no-op on a one-page host -- it shrinks the page toward its own rate -- and
    # a lucky single fetch outranks a source with two hundred. Same two-level structure the
    # allocator uses for sleeve -> family -> no-edge, and it fails the same way if either level
    # is allowed to believe itself.
    h_c, h_f = hosts.get(s.host, (0.0, 0.0))
    h_lam = h_f / (h_f + _HOST_PRIOR)
    host_mean = h_lam * (h_c / h_f if h_f else 0.0) + (1 - h_lam) * global_mean
    posterior = lam * raw + (1 - lam) * host_mean

    # NEVER-FETCHED IS AN OPPORTUNITY, NOT AN UNKNOWN TO AVOID. A source the desk has not tried
    # carries the global prior plus an exploration bonus, so the frontier cannot collapse onto
    # the handful of pages it already understands -- which is how a crawler stops being wide.
    if s.fetches == 0:
        posterior += 0.35 * max(global_mean, 0.05)

    # A PAGE THAT HANDS OVER DATA GOES FIRST. Not a preference -- the desk measured the two
    # input classes and they do not compete: structured feeds convert rows into executable
    # candidates at 100% (broker_swaps, 248 of 248), 96% and 64%, while PROSE converted 0 of
    # 341 across reddit, github, quant_se, bis_speeches, amarkets and this crawler's own rows.
    # That is not a tuning gap; the compiler's rule is "exact recipe or structured causal data
    # only, no prose-to-family guessing", so an article structurally cannot produce one.
    #
    # Applied as a MULTIPLIER on the posterior rather than a filter, so a prose page with real
    # measured yield still outranks a dataset that has repeatedly given nothing. Evidence wins;
    # this only decides who gets tried while the evidence is thin.
    try:
        from world_crawler import is_data_source
        if is_data_source(s.url):
            posterior *= 3.0
    except Exception:
        pass                                                     # ranking is never load-bearing

    # An unchanged page is cheap to skip and expensive to keep re-reading. The streak decays its
    # score geometrically and any change resets it -- a live page recovers immediately.
    posterior *= math.pow(0.6, min(s.unchanged_streak, 8))

    if s.consecutive_failures >= _FAIL_STARVE:
        posterior *= 0.01
    elif s.consecutive_failures:
        posterior *= math.pow(0.5, s.consecutive_failures)
    return float(posterior)


def due(sources: dict[str, Source], budget: int) -> list[Source]:
    """The `budget` sources worth fetching this hour, best expected yield first."""
    if not sources:
        return []
    hosts = host_yield(sources)
    tot_c = sum(s.candidates + 0.25 * s.leads for s in sources.values())
    tot_f = sum(s.fetches for s in sources.values())
    global_mean = (tot_c / tot_f) if tot_f else 0.05
    ranked = sorted(sources.values(), key=lambda s: -score(s, hosts, global_mean))

    # ONE HOST MAY NOT OWN THE HOUR. A single prolific domain would otherwise take every slot,
    # which is depth bought by giving up width -- and width is the whole point of a crawler that
    # discovers its own sources. Politeness and coverage happen to want the same rule.
    per_host_cap = max(2, budget // 8)
    seen: dict[str, int] = {}
    picked: list[Source] = []
    for s in ranked:
        if seen.get(s.host, 0) >= per_host_cap:
            continue
        seen[s.host] = seen.get(s.host, 0) + 1
        picked.append(s)
        if len(picked) >= budget:
            break
    return picked


#: A link is worth adding when its text or URL carries trading vocabulary in ANY language. The
#: desk does not read only English, and filtering to it would delete most of the world's retail
#: quant writing -- which is precisely the ground the principal asked to cover.
_VOCAB = (
    # en
    "trading|strategy|backtest|forex|indicator|expert advisor|breakout|scalp|algo|quant"
    # zh
    "|交易|策略|回测|外汇|指标|突破|量化|均线|套利"
    # ja
    "|取引|戦略|バックテスト|為替|指標|手法"
    # ko
    "|거래|전략|백테스트|외환|지표"
    # ru
    "|торговля|стратегия|бэктест|форекс|индикатор"
    # es / pt
    "|estrategia|operativa|backtesting|divisas|indicador|negociação|estratégia"
    # de / fr
    "|handel|strategie|indikator|stratégie|négociation"
    # ar
    "|تداول|استراتيجية|مؤشر"
)
RELEVANT = re.compile(_VOCAB, re.IGNORECASE)


def worth_following(url: str, anchor_text: str = "") -> bool:
    """Is this link plausibly quant ground? Cheap, recall-biased, and language-blind by design.

    BIASED TOWARD RECALL ON PURPOSE. A false positive costs one fetch, which the yield ranking
    then charges to that source forever. A false negative costs a ground the desk never learns
    exists, and nothing in the system can later notice the omission.
    """
    if not url.startswith(("http://", "https://")):
        return False
    low = f"{url} {anchor_text}".lower()
    if any(bad in low for bad in ("/login", "/signup", "/cart", "javascript:", ".pdf?", "/ads/")):
        return False
    return bool(RELEVANT.search(low))


def add(sources: dict[str, Source], url: str, via: str, lang: str = "") -> bool:
    """Record a newly discovered source. Returns True when it was genuinely new."""
    url = url.split("#")[0].strip()
    if not url or url in sources:
        return False
    sources[url] = Source(url=url, discovered_via=via, lang=lang)
    return True
