"""GLOBAL / INSTITUTIONAL: the last region at zero, and the reason was one missing directory.

MEASURED 2026-09-24, and the shape of it is exactly the Japan defect of the day before.

`libs/research/attribution.py:121` declares thirteen regions. Twelve of them hold cells --
Japan 1452, LatAm 377, Africa 327, Europe 253, down to Russia/CIS 18 -- and
`desks/mt5/reports/REGION_RATCHET.json` publishes the thirteenth as

    "regions_empty": ["Global/institutional"],  "min": 0,  "median": 105,  "max": 1452

with `high_water: 0` and `fell_to_zero: []`: it has never held one. Not a regression, not a
ratchet failure, and -- the thing worth writing down -- **not latency**. The region holds 99
grounds, 77 of them crawled, carrying 384 verbatim claims, and `pack_cells` reached its ENTIRE
backlog inside budget on the pass that produced those numbers:

    PACK_CELLS.json   grounds_reached_this_pass 57   backlog_with_documents_and_no_cell 57
                      cells_emitted_this_pass 0      cells_created_this_pass 0

Every one of those grounds was walked and every one was REFUSED, four minutes after the last of
its claims landed. `pack_cells_cursor.json` agrees from the other side: the world offset for
every institutional ground reads 0, because `emit_world`'s no-targets early return does not carry
`claims_read` and so never advances a cursor. Zeros that are refusals, not un-reached rows.

WHAT REFUSED THEM, TO THE LINE. `pack_cells.emit_world` returns at `pack_cells.py:739-745` when
`targets` is empty, and `targets` comes from `country_pack(row["country"])` at `:655`.
`country_pack` (`:407-427`) resolves a pack by importing `countries.<country>.pack`. The
`country` on these 99 grounds is the string `institutional` (87) or `global` (12) -- a LANE, not
an ISO code -- and `research/countries/` held 74 packs and neither of those two. So rung 1 of the
mapping ladder could not fire, and the refusal message is the instruction this file follows:

    "country 'institutional' has no pack under research/countries/, so the ground names no MT5
     instrument; add the pack (EXECUTABLE_INSTRUMENTS) and it converts on the next pass"

The lower rungs cannot rescue it either, and that is measured too. Rung 2
(`jurisdiction_of_documents`, `:519`) reads a ccTLD and returns "" for any gTLD -- and these
hosts are `www.gold.org`, `www.silverinstitute.org`, `icsg.org`, `www.icco.org`, `www.eia.gov`,
`www.jodidata.org`, `data.worldbank.org`, `data-explorer.oecd.org`, `www.cboe.com`,
`efts.sec.gov`, `www.bis.org`, `www.federalreserve.gov`, `www.fao.org`, `fbx.freightos.com`,
`www.balticexchange.com`, every one a gTLD. Rung 3 (`instruments_named_in_documents`, `:569`)
needs a symbol of five or more characters to appear verbatim in the held text, and the held text
is landing-page navigation. 36 of the 38 document-holding grounds ended at rung 4, UNMAPPED. The
two that did convert (`drewry.co.uk`) resolved through rung 2 to the `uk` pack, so their 48 cells
were stamped Europe: the region's only converting grounds donate their cells to another region.

WHAT THIS PACK IS. A door with a DERIVED instrument list, and nothing else. It states no
mechanism, owns no miner, runs on no clock and judges nothing. `REGION_COMMAND = "institutional"`
is already crosswalked by `libs/research/attribution.py:162`
(`"INSTITUTIONAL": "Global/institutional"`), so a cell minted through it is stamped with the
region at birth by the machinery that already exists.

WHY THE LIST IS DERIVED AND NEVER TYPED (the Japan pack's rule, kept). Typing a list of tickers
would be a CLAIM about the broker; reading the registry is a MEASUREMENT of it. Two measured
tiers, intersected with `data/universe/universe.json` and with the two-lane mandate:

  1. THE GLOBAL BENCHMARK COMPLEX. Every symbol the broker quotes whose asset class in
     MetaTrader's own registry is a commodity, a soft, a metal, an energy or an index -- the
     subject matter of the World Gold Council, the Silver Institute, the ICSG, the ICCO, the EIA,
     JODI, the FAO, the Baltic Exchange, Freightos and CBOE. These bodies publish about the
     BENCHMARK, which is precisely what an index or a metal CFD is.
  2. THE DOLLAR AXIS. USDX and the USD majors the broker quotes, because the Federal Reserve, the
     BIS, the New York Fed, the World Bank, the OECD, the NBER and cbrates publish about policy
     rates and the dollar, and the dollar is how that information reaches this book.

`universe_policy.may_hypothesise` filters both tiers, so the two-lane mandate is enforced at the
source: a single-name share CFD can never enter this list however a registry row is spelled, and
a symbol absent from the registry is UNCLASSIFIED and is not admitted by absence. Bonds are
included where the broker quotes them and crypto is NOT: no body in this lane publishes a
benchmark for a crypto CFD, and adding one would be inventing a subject for a ground rather than
reading it.

WHAT THIS DOES NOT CLAIM. That any of these grounds has an edge. A cell is a QUESTION the ten
gates get to answer; minting one asserts nothing. What was wrong was that 384 claims could not
become a single question, which made the region's emptiness unfalsifiable -- and an unfalsifiable
zero is the one reading this desk treats as a defect rather than a result (L1.28a).
"""
from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[3]      # countries/institutional/pack.py -> desks/mt5
UNIVERSE = BASE / "data" / "universe" / "universe.json"

CODE = "INSTITUTIONAL"
NAME = "Global / institutional"
REGION_COMMAND = "institutional"
REGION_DESK = "GLOBAL_INSTITUTIONAL"
FOREST = "institutional"
CURRENCY = "USD"
JURISDICTIONS: tuple[str, ...] = ("global", "institutional")
NATIVE_LANGUAGES: tuple[str, ...] = ("en",)
COT_CURRENCY = ""
FISCAL_YEAR_END = ""
EXPORT_ECONOMY = "not_an_economy"
RETAIL_LEVERAGE_REGIME = "not_a_jurisdiction"

MISSION = ("hold the lane so the multilateral and benchmark-publishing grounds the crawler "
           "already reaches -- the World Gold Council, the Silver Institute, the ICSG, the ICCO, "
           "the EIA, JODI, the FAO, the BIS, the Fed, the OECD, the World Bank, CBOE, the Baltic "
           "Exchange -- name the MT5 benchmarks they publish about. The mechanisms are not here; "
           "this pack is the declaration `pack_cells.country_pack` reads.")

#: Asset classes, as MetaTrader's own registry spells them, whose instruments ARE the benchmarks
#: these bodies publish. Matched through `universe_policy.asset_class_of`, never against a symbol
#: list: a symbol the broker reclassifies moves between tiers with no edit here.
BENCHMARK_CLASSES: frozenset[str] = frozenset({
    "commodity", "commodities", "soft commodity", "soft commodities", "soft",
    "metal", "metals", "precious metals", "energy", "indices", "index", "bond", "bonds",
})

#: The dollar axis. `USDX` is the index itself; the rest are read off the registry as the USD
#: majors it is built from, so a broker that stops quoting one drops it on the next process start.
DOLLAR_AXIS_INDEX = "USDX"
DOLLAR_LEGS: tuple[str, ...] = ("EUR", "JPY", "GBP", "CHF", "CAD", "SEK", "AUD", "NZD", "CNH")


def _quoted() -> tuple[str, ...]:
    """Every symbol the broker's own universe registry lists. Empty when it cannot be read."""
    try:
        doc = json.loads(UNIVERSE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ()
    return tuple(str(k) for k in doc) if isinstance(doc, dict) else ()


def _policy() -> Any:
    """`research.universe_policy`, the mandate's own asset-class router, or None.

    Resolved by name rather than by an `import` statement because this package is reached from
    two different sys.path shapes (the repository root and `desks/mt5`), exactly as
    `pack_cells.py:564` reaches the same module.
    """
    for name in ("research.universe_policy", "universe_policy"):
        try:
            return importlib.import_module(name)
        except ImportError:
            continue
    return None


def _hypothesisable(symbol: str) -> bool:
    """The two-lane mandate, applied at the source rather than downstream of it."""
    pol = _policy()
    return bool(pol.may_hypothesise(symbol)) if pol is not None else False


def _class_of(symbol: str) -> str:
    pol = _policy()
    return str(pol.asset_class_of(symbol) or "").strip().lower() if pol is not None else ""


def _benchmarks(quoted: tuple[str, ...]) -> tuple[str, ...]:
    """Tier 1: every quoted commodity, soft, metal, energy, index or bond the desk may hunt."""
    return tuple(sorted(s for s in quoted
                        if _class_of(s) in BENCHMARK_CLASSES and _hypothesisable(s)))


def _dollar_axis(quoted: tuple[str, ...]) -> tuple[str, ...]:
    """Tier 2: the dollar index and the USD majors the broker actually quotes."""
    out: list[str] = [DOLLAR_AXIS_INDEX] if (DOLLAR_AXIS_INDEX in quoted
                                             and _hypothesisable(DOLLAR_AXIS_INDEX)) else []
    for leg in DOLLAR_LEGS:
        for sym in (f"USD{leg}", f"{leg}USD"):
            if sym in quoted and _hypothesisable(sym) and sym not in out:
                out.append(sym)
                break
    return tuple(out)


def _executable() -> tuple[str, ...]:
    quoted = _quoted()
    out: list[str] = []
    for sym in _benchmarks(quoted) + _dollar_axis(quoted):
        if sym not in out:
            out.append(sym)
    return tuple(out)


#: DERIVED at import from the broker's registry and the two-lane mandate. Never typed. An
#: unreadable registry yields an EMPTY tuple, which restores the exact refusal this pack exists to
#: end -- and that is deliberate: a pack that guessed an instrument when it could not measure one
#: would put a fabricated subject under 384 real claims.
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = _executable()

#: The grounds this pack gives an instrument to. Documentation of what the crawler's registry
#: ALREADY holds -- never a new crawl target, and never a source of grounds: the source registry
#: remains the only one of those.
KNOWN_GROUNDS: tuple[dict[str, Any], ...] = (
    {"id": "forest:institutional:www.gold.org", "host": "www.gold.org",
     "publishes": "World Gold Council demand trends, central-bank purchases and ETF flows"},
    {"id": "forest:institutional:www.silverinstitute.org", "host": "www.silverinstitute.org",
     "publishes": "the Silver Institute's supply/demand balance and industrial offtake"},
    {"id": "forest:institutional:icsg.org", "host": "icsg.org",
     "publishes": "International Copper Study Group refined-market balances"},
    {"id": "forest:institutional:www.icco.org", "host": "www.icco.org",
     "publishes": "International Cocoa Organization grindings and stock estimates"},
    {"id": "forest:institutional:www.eia.gov", "host": "www.eia.gov",
     "publishes": "US crude, product and natural-gas inventories and the STEO"},
    {"id": "forest:institutional:www.jodidata.org", "host": "www.jodidata.org",
     "publishes": "the joint organisations oil and gas production and stock database"},
    {"id": "forest:institutional:data.worldbank.org", "host": "data.worldbank.org",
     "publishes": "the pink sheet commodity price series and the global indicator set"},
    {"id": "forest:institutional:data-explorer.oecd.org", "host": "data-explorer.oecd.org",
     "publishes": "OECD composite leading indicators and policy-rate series"},
    {"id": "forest:institutional:www.cboe.com", "host": "www.cboe.com",
     "publishes": "the volatility indices every index cell conditions risk state on"},
    {"id": "forest:institutional:www.bis.org", "host": "www.bis.org",
     "publishes": "BIS effective exchange rates, triennial turnover and cross-border claims"},
    {"id": "forest:institutional:www.federalreserve.gov", "host": "www.federalreserve.gov",
     "publishes": "the policy rate, H.4.1 balance sheet and the broad dollar index"},
    {"id": "forest:institutional:www.fao.org", "host": "www.fao.org",
     "publishes": "the FAO food price index and cereal supply/demand balances"},
    {"id": "forest:institutional:fbx.freightos.com", "host": "fbx.freightos.com",
     "publishes": "container freight rates on the lanes that carry the physical complex"},
    {"id": "forest:institutional:www.balticexchange.com", "host": "www.balticexchange.com",
     "publishes": "dry-bulk freight indices, the oldest traded read on physical demand"},
)

BOUNDARIES: tuple[str, ...] = (
    "this pack states no mechanism: it declares an instrument set and a region and nothing else, "
    "and it must never grow a miner, a rule, a calendar or a threshold",
    "EXECUTABLE_INSTRUMENTS is derived at import from the broker's registry and the two-lane "
    "mandate; it is never hard-coded and never widened by hand",
    "an unreadable registry yields an empty tuple and the grounds go back to being refused with "
    "their reason published -- absence is reported, never guessed around",
    "nothing here judges, sizes, caps or vetoes anything",
)
