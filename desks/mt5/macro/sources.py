"""SOURCES -- pluggable readers, and a coverage map that NAMES what the desk cannot see.

WHY COVERAGE IS A FIRST-CLASS OUTPUT AND NOT A README LINE. An unnamed blind spot is a silent
failure: the ledger shows no events in a domain, every statistic conditioned on that domain reads
"no effect", and nothing anywhere says the desk was never looking. A NAMED blind spot is a
purchasing decision the principal can act on in an afternoon. So `coverage()` enumerates the
domains this layer is meant to see, says which source covers each, and prints the uncovered ones
as the report's headline.

THE DOMAIN LIST IS A COVERAGE CHECKLIST, NOT THE EVENT TAXONOMY -- and the distinction is the
whole reason this package has two lists instead of one. The taxonomy (`taxonomy.py`) is open and
discovered, because an event class nobody anticipated must still be recorded. This list is closed
and enumerable because it answers a different question: what have we deliberately gone looking
for? Failing to look somewhere is knowable in advance; failing to anticipate an event class is
not. An item from a source in one domain that turns out to be about something entirely different
is classified by the taxonomy, not by its source's domain tags.

BREADTH BEFORE DEPTH, at least until the ledger has sample. A shallow reader that records
everything with honest uncertainty is worth more right now than a deep CPI parser that cannot see
an OPEC decision, because the missing OPEC decision is invisible and the shallow CPI row is
merely imprecise. Every source here is therefore a headline-level reader; structured parsers come
after the ledger says which domains actually move the book.

LAWFULNESS IS RECORDED PER SOURCE, NOT ASSUMED. Each source declares its licence, its terms URL
and whether robots.txt was honoured, and those travel onto every row it produces. A source that
cannot declare a licence is declared UNDECLARED and its rows say so -- which is a flag for review,
not a blocker on recording. Public and licensed information only; nothing in this module has a
path to anything else.

NETWORK IS BEHIND THE INTERFACE. `RssSource` is the only thing here that touches the network, it
delegates to the desk's existing keyless `free_data.rss_fetch`, and it degrades to an empty list
on any failure. `FakeSource` satisfies the same protocol, which is what makes every consumer in
this package testable with no network at all. The live fetch is the one part of this package that
cannot be verified offline.
"""

from __future__ import annotations

import importlib
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from .schema import content_id, now_iso

DESK = Path(__file__).resolve().parents[1]

#: THE COVERAGE CHECKLIST. What this layer is meant to be able to see, so that what it cannot see
#: is a named gap rather than a silence. Adding a domain here does not change what the desk can
#: observe -- only a source does that -- it changes what the desk ADMITS it is missing, which is
#: why the list is deliberately more ambitious than the current source set.
DOMAINS: tuple[str, ...] = (
    "central_bank_decisions", "central_bank_speech_minutes", "statistics_us",
    "statistics_europe", "statistics_asia", "statistics_other", "rates_futures_repricing",
    "sovereign_credit", "corporate_credit", "bank_counterparty_stress", "elections_politics",
    "fiscal_budget", "trade_policy_tariffs", "sanctions_export_controls",
    "conflict_escalation", "commodity_supply_shock", "labour_strikes", "weather_harvest",
    "shipping_chokepoints", "energy_inventories", "opec_decisions", "regulatory_exchange",
    "index_reconstitution", "equity_earnings_guidance", "fx_intervention_pegs",
    "natural_disasters", "volatility_options_repricing",
)

__all__ = [
    "DOMAINS",
    "FakeSource",
    "RawItem",
    "RssSource",
    "Source",
    "coverage",
    "default_sources",
]


@dataclass(frozen=True)
class RawItem:
    """What a source hands back before anything has been scored. Deliberately dumb."""

    source_id: str
    title: str
    url: str = ""
    body: str = ""
    published_at: str | None = None
    happened_at: str | None = None
    received_at: str = field(default_factory=now_iso)
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def event_id(self) -> str:
        return content_id(self.source_id, self.title, self.url, self.published_at)


@runtime_checkable
class Source(Protocol):
    source_id: str
    tier: str
    licence: str
    terms_url: str
    robots_ok: bool | None
    domains: tuple[str, ...]
    retrieval: str

    def fetch(self) -> Sequence[RawItem]:
        """Everything currently available. Deduplication is the LEDGER's job, not the source's --
        a source that dedupes internally loses the evidence that an item was re-published, which
        is itself information about how a story developed."""


@dataclass
class FakeSource:
    """Deterministic offline source. The test surface for every consumer in this package."""

    source_id: str = "fake"
    tier: str = "SPECIALIST"
    licence: str = "test-fixture"
    terms_url: str = ""
    robots_ok: bool | None = True
    domains: tuple[str, ...] = ()
    retrieval: str = "fixture"
    items: Sequence[RawItem] = ()

    def fetch(self) -> Sequence[RawItem]:
        return list(self.items)


@dataclass
class RssSource:
    """One first-party RSS/Atom feed, read through the desk's existing keyless fetcher.

    First-party government and central-bank feeds are the strongest sources available without a
    licence: they are the primary document rather than a report about one, they are published for
    exactly this purpose, and their terms permit it. They are also SLOW relative to a wire -- the
    feed is generated after the release -- and `credibility.py` measures that lateness separately
    rather than letting reliability stand in for speed.
    """

    source_id: str
    url: str
    tier: str = "OFFICIAL"
    licence: str = "public-first-party-feed"
    terms_url: str = ""
    robots_ok: bool | None = None
    domains: tuple[str, ...] = ()
    retrieval: str = "rss"

    def fetch(self) -> Sequence[RawItem]:
        fetcher = _rss_fetcher()
        if fetcher is None:
            return []
        out: list[RawItem] = []
        try:
            rows = fetcher(self.url)
        except Exception:
            # A source that throws must not take the pass down with it: one dead feed is one
            # dead feed, and the coverage report is where that becomes visible.
            return []
        for item in rows or []:
            title = str(item.get("title", "")).strip()
            if not title:
                continue
            link = str(item.get("link", "") or item.get("guid", "") or item.get("id", "")).strip()
            pub = (item.get("pubDate") or item.get("published") or item.get("updated"))
            out.append(RawItem(
                source_id=self.source_id, title=title, url=link,
                published_at=str(pub) if pub else None,
                received_at=datetime.now(UTC).isoformat(),
                extra={"feed": self.url}))
        return out


def _rss_fetcher() -> Any:
    """`free_data.rss_fetch`, imported lazily and only if the desk tree is present.

    Lazy because this package must import on a box with nothing but the ledger, and because the
    desk's research directory is not a package -- it goes on sys.path the way every other desk
    organ does it.
    """
    research = str(DESK / "research")
    if research not in sys.path:
        sys.path.insert(0, research)
    try:
        # importlib rather than a bare `import free_data`: the desk's research directory is not
        # a package, so a static import needs a type-ignore whose usefulness flips depending on
        # whether the checker can see that tree -- and an ignore that is required on one box and
        # flagged unused on another is exactly the straddle this repo has already paid for once.
        module = importlib.import_module("free_data")
    except Exception:
        return None
    return getattr(module, "rss_fetch", None)


#: The first-party feeds the desk already reaches keylessly, tagged with the domains each one
#: actually covers. Tags are conservative: a central bank's press feed carries decisions and
#: speeches, and it does NOT carry OPEC or shipping, so it is not tagged with them.
_OFFICIAL_FEEDS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("FED", "https://www.federalreserve.gov/feeds/press_all.xml",
     ("central_bank_decisions", "central_bank_speech_minutes", "bank_counterparty_stress")),
    ("BLS", "https://www.bls.gov/feed/news_release_all.xml", ("statistics_us",)),
    ("ECB", "https://www.ecb.europa.eu/rss/press.html",
     ("central_bank_decisions", "central_bank_speech_minutes")),
    ("BOJ", "https://www.boj.or.jp/en/announcements/rss.rdf",
     ("central_bank_decisions", "central_bank_speech_minutes", "fx_intervention_pegs")),
    ("BOE", "https://www.bankofengland.co.uk/rss/news",
     ("central_bank_decisions", "central_bank_speech_minutes")),
    ("SNB", "https://www.snb.ch/en/node/10532/rss",
     ("central_bank_decisions", "fx_intervention_pegs")),
)


def default_sources() -> list[RssSource]:
    """The sources this desk can lawfully reach today, with no key and no licence purchase.

    Six first-party central-bank and statistics feeds. That is a narrow slice of `DOMAINS`, and
    `coverage()` says exactly how narrow rather than letting the ledger imply the world is quiet.
    """
    return [RssSource(source_id=sid, url=url, domains=doms)
            for sid, url, doms in _OFFICIAL_FEEDS]


def coverage(sources: Sequence[Any] | None = None) -> dict[str, Any]:
    """Which domains are covered, which are blind, and what each blind spot costs.

    `licensed_gaps` names the things that cannot be fixed with more code, only with a purchase or
    an agreement. The economic calendar is the sharpest of them: `data/news_schedule.json` starts
    EMPTY by design -- "no invented release data, ever" -- so the desk currently has NO scheduled
    release times, NO consensus figures and NO actuals. Without consensus there is no surprise z
    at all, which is why `surprise.py` returns UNMEASURED on this box for every scheduled release.
    """
    srcs = list(default_sources() if sources is None else sources)
    covered: dict[str, list[str]] = {}
    for s in srcs:
        for d in getattr(s, "domains", ()):
            covered.setdefault(d, []).append(getattr(s, "source_id", "?"))
    blind = [d for d in DOMAINS if d not in covered]
    return {
        "at": now_iso(),
        "n_sources": len(srcs),
        "sources": [{"id": getattr(s, "source_id", "?"), "tier": getattr(s, "tier", "UNKNOWN"),
                     "licence": getattr(s, "licence", "UNDECLARED"),
                     "retrieval": getattr(s, "retrieval", "unknown"),
                     "domains": list(getattr(s, "domains", ()))} for s in srcs],
        "domains_total": len(DOMAINS),
        "domains_covered": sorted(covered),
        "domains_blind": blind,
        "coverage_fraction": round(len(covered) / len(DOMAINS), 3),
        "licensed_gaps": [
            {"gap": "economic calendar with consensus AND actuals",
             "evidence": ("desks/mt5/data/news_schedule.json starts EMPTY by design; "
                          "libs/regime/event_state.py records that the desk's calendar vintages "
                          "carry forecast and previous but no actual"),
             "consequence": ("no surprise z for any scheduled release anywhere in the world -- "
                             "surprise.py returns UNMEASURED, so no scheduled release can earn "
                             "capital authority"),
             "remedy": "a licensed calendar feed"},
            {"gap": "a real-time wire",
             "evidence": "every source above is a first-party feed generated after the event",
             "consequence": ("median arrival is tens of seconds to minutes behind the tape, so "
                             "the unpriced fraction on fast events is small or zero and the "
                             "allocator interrupt will correctly almost never fire"),
             "remedy": "a licensed low-latency wire"},
            {"gap": "sub-minute price series",
             "evidence": ("desks/mt5/data/universe/ holds H1 for 24 symbols and M15 for 3; no "
                          "tick tape"),
             "consequence": ("priced-versus-unpriced returns UNMEASURABLE for any event whose "
                             "publish-to-receive lag is under an hour on those instruments"),
             "remedy": "M1 bars or a tick tape for the instruments the desk reacts on"},
        ],
        "note": ("This is a COVERAGE checklist -- what the desk went looking for. It is NOT the "
                 "event taxonomy, which is open and discovered (taxonomy.py). An item that turns "
                 "out to be about something nobody listed is still recorded and still scored."),
    }
