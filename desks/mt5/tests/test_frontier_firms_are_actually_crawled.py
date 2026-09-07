"""A watched organisation with no address is one the miner reads about by accident.

`frontier_supervisor.scout()` filters the intelligence roots for rows that MENTION a tracked firm,
and `registry.FIRMS` lists twenty-two of them. But `Firm.sources` names source KINDS
("official_site", "careers_page") and carries no addresses, so before `HOMEPAGES` existed no firm
page was seeded anywhere on this desk: the only rows the scout could match were incidental
mentions in material gathered for something else. An hourly organ whose entire subject is those
organisations had no path to their own words.

These tests pin the wiring and the honesty of its coverage report -- not the contents of anyone's
website, which this suite cannot and should not reach.
"""
from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlsplit

BASE = Path(__file__).resolve().parent.parent
for _p in (str(BASE), str(BASE / "side_channels")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from frontier_intel import registry  # noqa: E402


def test_every_homepage_key_names_a_registered_firm() -> None:
    """A typo'd key seeds nothing and reports nothing -- it just quietly does not exist."""
    unknown = sorted(set(registry.HOMEPAGES) - set(registry.BY_NAME))
    assert not unknown, f"HOMEPAGES names organisations not on the registry: {unknown}"


def test_the_seed_list_is_non_empty_and_deduplicated() -> None:
    seeds = registry.crawl_seeds()
    assert seeds, "no firm pages seeded -- the scout can only match accidental mentions"
    assert len(seeds) == len(set(seeds))


def test_every_seed_is_https() -> None:
    """Plain http on a public research page is a downgrade the desk has no reason to accept."""
    for url in registry.crawl_seeds():
        assert urlsplit(url).scheme == "https", url
        assert urlsplit(url).netloc, url


def test_coverage_gaps_are_reported_rather_than_hidden() -> None:
    """The two absences are deliberate and each has a reason on the record.

    `citadelsecurities.com` answers 403 to a non-browser client, so seeding it would buy a refusal
    out of a bounded fetch budget every single run; "exchange & venue research" is a category
    rather than one organisation and has no single address. Pinned so coverage cannot quietly
    erode -- if a firm loses its page, this test says so instead of the miner going quiet about it.
    """
    assert registry.unseeded_firms() == ("Citadel Securities", "exchange & venue research")


def test_the_four_named_chinese_ai_quants_are_all_seeded() -> None:
    """The group the principal asked for by name.

    Watching them without an address is the exact failure this file exists to prevent.
    """
    for name in ("High-Flyer", "Lingjun", "Ubiquant", "Minghong"):
        assert registry.HOMEPAGES.get(name), f"{name} is watched but has no page to read"


def test_the_crawler_seeds_exactly_what_the_registry_declares() -> None:
    """One table, two consumers: adding a firm gives it a seed in the same edit.

    The alternative is a second list that agrees with the registry until the day it does not, and
    a firm watched-but-never-fetched is invisible precisely because everything looks configured.
    """
    import world_crawler

    assert world_crawler.frontier_seeds() == registry.crawl_seeds()


def test_the_crawler_still_starts_if_the_frontier_package_moves() -> None:
    """A crawler that cannot start because an unrelated package moved is the worse outcome.

    The rest of the ground -- official statistics, exchange data, the point-in-time archives that
    are the only source class that has ever converted here -- is still worth covering.
    """
    import world_crawler

    # The TOP-LEVEL name, not the submodule. A None entry for `frontier_intel.registry` does not
    # block `from frontier_intel import registry`: the package object already has the attribute
    # bound, so the import succeeds from cache and the test would pass without exercising the
    # fallback at all. Poisoning the top-level name is what actually raises.
    original = sys.modules.get("frontier_intel")
    sys.modules["frontier_intel"] = None               # type: ignore[assignment]
    try:
        assert world_crawler.frontier_seeds() == ()
    finally:
        if original is not None:
            sys.modules["frontier_intel"] = original
        else:
            sys.modules.pop("frontier_intel", None)


def test_no_seed_targets_a_crypto_exchange() -> None:
    """MT5 UNIVERSE MANDATE (principal 2026-08-18).

    No miner, hunter, query or channel list may target a crypto-exchange-native universe. A seed
    list is a channel list, and a frontier crawl is a plausible route for one to creep back in.
    """
    banned = ("binance", "bybit", "okx", "hyperliquid", "coinbase", "kraken", "deribit",
              "bitmex", "kucoin", "gate.io", "dydx")
    for url in registry.crawl_seeds():
        host = urlsplit(url).netloc.lower()
        for word in banned:
            assert word not in host, f"{url} targets a crypto exchange"
