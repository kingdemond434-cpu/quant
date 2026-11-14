"""Which lane an instrument belongs to: statistical hypothesis discovery, or event-driven.

PRINCIPAL'S ORDER, 2026-09-06: single-name equities are NOT hunted for statistical hypotheses.
They are traded on news, financial reports and earnings reaction. Forex, metals, energy, soft
commodities, indices, bonds and Fusion's crypto CFDs remain the hypothesis-discovery universe.

WHY THIS IS RIGHT AND NOT MERELY A PREFERENCE, recorded because a later reader will be tempted to
"restore breadth" by putting the shares back. Two independent reasons:

  A single name's hourly path is dominated by its own scheduled disclosures. An hypothesis of the
  form "Apple mean-reverts after a session-range breakout" is fitted across earnings dates,
  guidance, product events and index reconstitutions, and the fitted parameter is a blend of
  regimes that never recur in that mixture. The mechanism that actually moves the instrument --
  the announcement and the market's reaction function to it -- is not in the feature set at all.

  TRIAL COUNT IS A SHARED COST, and this is the part that is easy to miss. The deflated Sharpe
  charge and the SPA/PBO program-level tests divide the family-wise error budget across EVERY
  hypothesis the desk tested, so each equity cell raises the bar that every FX and metals cell
  must clear. Measured 2026-09-06: 597 trials in the campaign, and `deflated_sharpe` rejected 42
  of 42 judged cells. On that same docket 10,575 of 23,627 cells (44.8%) were single-name
  equities and a further 3,839 were equity tickers from a non-Fusion vocabulary -- about 61% of
  the multiple-testing charge, spent on the asset class least suited to the method, and paid for
  by the classes best suited to it.

AMENDED BY THE PRINCIPAL 2026-09-30: "do cross sectional add cross sectional and news not js news
change my order". Share CFDs now ALSO mint hypotheses in the cross-sectional class books
(`CROSS_SECTIONAL_FAMILIES`, ranked within the `equity` peer class), alongside the event lane.
Every other statistical family remains event-lane-only for them, for the two reasons above.

So this is not a reduction in breadth. It is the same evidence budget spent where the mechanism
being modelled is the mechanism actually present.

NO SYMBOL LIST, EVER. Routing is by ASSET CLASS, read from MetaTrader's own registry entry and
falling back to the desk's pattern classifier. A share CFD listed tomorrow is routed correctly
the day it appears, and no edit here is required -- the failure mode of a hand-kept list is that
it is right on the day it is written and silently wrong afterwards.

WHAT THIS IS NOT. Equities are not removed from the desk's universe: the MT5 universe mandate
stands, they remain tradable, their bars and ticks are still collected, and the news/earnings
lane is where their edge is sought. `lane()` says which process may mint a hypothesis about an
instrument -- never whether the desk may hold it.
"""
from __future__ import annotations

import json
import sys
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
UNIVERSE = BASE / "data" / "universe" / "universe.json"

#: The lane an instrument's edge is sought in.
HYPOTHESIS = "hypothesis"       # statistical discovery: the gauntlet, the miners, the sweeps
EVENT = "event"                 # news, financial reports, earnings reaction
UNCLASSIFIED = "unclassified"   # class unknown -- routed to NEITHER, and reported

def _norm(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().replace("_", " ").split())


def _norm_set(names: Iterable[Any]) -> frozenset[str]:
    """The declared class names, put through the SAME normaliser the values are.

    THE DEFECT THIS CLOSES, measured on the box 2026-09-23. `_norm` maps `_` to a space, so
    `asset_class_of` returns `'fx major'`, `'fx cross'`, `'fx exotic'` -- while the literals in
    `HYPOTHESIS_CLASSES` were spelled `fx_major`, `fx_cross`, `fx_exotic` and could therefore
    never match anything. Those three are the ONLY underscore-bearing entries in either set, so
    the casualty was exactly and only FX: 96 of the 251 symbols in MetaTrader's registry (68
    exotics, 21 crosses, 7 majors) read UNCLASSIFIED, and `may_hypothesise` was False for every
    one of them from the day this module landed (2026-09-07) until this was fixed.

    WHAT IT COST. FX is the FIRST thing named in the MT5 universe mandate, and `shadow_forward`
    asks this question before it will replay a forward clock: 24 of the desk's 28 ten-gate
    certificates sat at `REFUSED_BY_UNIVERSE_POLICY`, and 92 of its 148 enrolled clocks with
    them -- certified, clocked, and accruing nothing, because of a space.

    Normalising the DECLARATION rather than editing the three strings is the fix that keeps
    working: a later reader who adds `soft_commodity` or `precious_metals` in the spelling this
    file's own docstrings use gets a set entry that matches, instead of a silent hole.
    """
    return frozenset(_norm(name) for name in names)


#: Asset classes whose edge is sought through announcements rather than through price statistics.
#: Matched case- and separator-insensitively against both the registry's `asset_class` string and
#: the desk's pattern classifier, so "Equities", "equity" and "US Shares" all land here.
EVENT_DRIVEN_CLASSES = _norm_set({
    "equities", "equity", "equities us", "shares", "share", "stock", "stocks",
})

#: Everything the gauntlet and the miners may hunt. Declared positively: a class that appears in
#: neither set is UNCLASSIFIED and is hunted by nothing until somebody decides where it belongs.
#: An unknown instrument quietly joining the discovery universe is how a vocabulary from another
#: broker got 3,839 cells onto this docket in the first place.
#:
#: SPELLED HOWEVER THE WRITER LIKES, because `_norm_set` puts every entry through the same
#: normaliser the registry's and the classifier's answers go through. Before that, `fx_major`,
#: `fx_cross` and `fx_exotic` were dead letters and all 96 FX symbols were UNCLASSIFIED -- see
#: `_norm_set`. The underscore spellings are KEPT rather than rewritten: they are what
#: `mt5desk.universe.asset_class` actually returns, and a reader comparing the two files should
#: see the same words.
HYPOTHESIS_CLASSES = _norm_set({
    "forex", "forex majors", "forex crosses", "forex exotics",
    "fx", "fx_major", "fx_cross", "fx_exotic",
    "commodity", "commodities", "soft commodity", "soft commodities", "soft",
    "metal", "metals", "precious metals",
    "energy", "indices", "index", "bond", "bonds", "crypto", "cryptocurrency",
})


@lru_cache(maxsize=4)
def _registry_at(path: str, mtime_ns: int) -> dict[str, dict]:
    try:
        data = json.loads(Path(path).read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k).upper(): v for k, v in data.items() if isinstance(v, dict)}


def _registry() -> dict[str, dict]:
    """The broker registry at `UNIVERSE`, parsed once per (path, mtime).

    KEYED ON THE FILE, NOT ON NOTHING. This was a bare `lru_cache(maxsize=1)` with no key, so the
    first registry any caller in the process read was the registry for the life of the process:
    a rewritten universe.json was never seen, and a caller that pointed `UNIVERSE` elsewhere (a
    tmp registry in a test) left that registry cached for every later caller once `UNIVERSE`
    was restored. Measured 2026-09-29 under `pytest -n auto --dist loadfile`: a 9-symbol tmp
    registry from test_axis_proposer / test_graveyard_resurrection answered the real-registry
    routing test on the same worker -- "no equities were set aside, 1 > 50". A stat per call is
    the price of the answer being about the file that is actually there.
    """
    try:
        mtime = UNIVERSE.stat().st_mtime_ns
    except OSError:
        mtime = -1
    return _registry_at(str(UNIVERSE), mtime)


#: Kept so every caller that clears the cache after rewriting a registry in place still works.
_registry.cache_clear = _registry_at.cache_clear  # type: ignore[attr-defined]


def asset_class_of(symbol: str) -> str:
    """The instrument's class, from MetaTrader's registry first and the classifier second.

    THE REGISTRY WINS because it is the broker's own answer, derived from the symbol's path and
    sector rather than inferred from its name. The pattern classifier is the fallback for a
    symbol whose registry row has not synced yet -- it is good, but it reads tickers, and a
    ticker is exactly what lies about a share CFD called `3M` or `A`.
    """
    row = _registry().get(str(symbol).strip().upper())
    if not isinstance(row, dict):
        # NOT IN THE BROKER'S REGISTRY, SO NOT ROUTED. The pattern classifier's last rule is
        # `\d?[A-Z]{1,12} -> equity`, a deliberate catch-all that serves its own purpose (share
        # CFDs arrive as company names and it must not report a whole asset class as unknown) but
        # is far too generous to decide a lane with: `NOTREAL` classified as an equity and was
        # routed to the news desk. Routing is a decision about a real instrument; a string that
        # is not in the registry is not one, and it must reach UNCLASSIFIED where it is reported.
        return ""
    declared = _norm(row.get("asset_class"))
    if declared:
        return declared
    # In the registry but carrying no class of its own -- 3 of 251 today. Here the classifier is
    # trustworthy, because the symbol is known to be a real broker instrument and only its label
    # is missing.
    try:
        sys.path.insert(0, str(BASE))
        from mt5desk.universe import asset_class as _pattern_class
        return _norm(_pattern_class(symbol))
    except Exception:
        return ""


def lane(symbol: str) -> str:
    """`HYPOTHESIS`, `EVENT` or `UNCLASSIFIED` for `symbol`. Never raises."""
    klass = asset_class_of(symbol)
    if not klass:
        return UNCLASSIFIED
    if klass in EVENT_DRIVEN_CLASSES:
        return EVENT
    if klass in HYPOTHESIS_CLASSES:
        return HYPOTHESIS
    # A class the desk has never seen is NOT admitted by default. Absence of a rule is not a
    # permission, and defaulting to the discovery lane would let any new vocabulary spend the
    # trial budget before anybody noticed it had arrived.
    return UNCLASSIFIED


#: THE PRINCIPAL'S AMENDMENT OF 2026-09-30 to the two-lane order: "do cross sectional add cross
#: sectional and news not js news change my order". Single-name equities keep their news and
#: earnings lane AND are now ranked in cross-sectional class books. Only these families may mint
#: a hypothesis on a share CFD; every other statistical family stays event-lane-only for them,
#: because the single-name time-series argument above (a path dominated by its own disclosures,
#: and the shared trial budget) still holds for those. A cross-sectional book is a different
#: bet: it ranks a share against its peers on the same date, so each name's own disclosures are
#: the idiosyncratic noise the class book diversifies, not the signal.
#: Pinned to `mt5desk.families_cross_sectional.CROSS_SECTIONAL_FAMILIES` by a test.
CROSS_SECTIONAL_FAMILIES = frozenset({
    "cross_sectional_class_momentum", "cross_sectional_class_reversal",
    "cross_sectional_class_value", "cross_sectional_class_low_vol",
    "crisis_only_class_defensive", "lead_lag_class_catchup", "cross_sectional_class_carry",
})


#: THE NEWS LANE'S OWN FAMILIES (2026-09-30, same amendment: "cross sectional and news"). A share
#: CFD's edge is sought in news, reports and earnings reaction; these families fire ONLY on a dated
#: public view ABOUT the name (or its cross-market peer) that the desk first saw at a recorded
#: instant, so they are the event lane's executor, not a statistical hunt over the price path. They
#: are admitted for share CFDs exactly as the class books are; every other statistical family stays
#: out. `event_reaction` is NOT here: its events are the macro calendar, not news about the name.
#: `alt_release_drift` (2026-09-30) fires only on a dated free alt-data release that the
#: alt_proxies equity hand-off names as bearing on the share -- a public datum about the name's
#: demand, first seen at its recorded `available_time` -- so it is the event lane, not a hunt.
NEWS_LANE_FAMILIES = frozenset({"analyst_revision_drift", "analyst_cross_market_lead",
                                "alt_release_drift"})


def is_equity(symbol: str) -> bool:
    """True for a share CFD: the event lane's own asset class, from the broker's registry."""
    return lane(symbol) == EVENT and asset_class_of(symbol) in EVENT_DRIVEN_CLASSES


def may_hypothesise(symbol: str, family: object = None) -> bool:
    """True for instruments whose edge is sought statistically -- and, for a share CFD, only when
    `family` is one of the cross-sectional class books or the news lane's own families (principal
    2026-09-30)."""
    if lane(symbol) == HYPOTHESIS:
        return True
    fam = str(family or "")
    return (fam in CROSS_SECTIONAL_FAMILIES or fam in NEWS_LANE_FAMILIES) and is_equity(symbol)


def split(symbols) -> dict[str, list[str]]:
    """Group an iterable of symbols by lane -- for reports that must name what they set aside."""
    out: dict[str, list[str]] = {HYPOTHESIS: [], EVENT: [], UNCLASSIFIED: []}
    for symbol in symbols:
        out[lane(symbol)].append(symbol)
    for key in out:
        out[key] = sorted(set(out[key]))
    return out


# =============================================================================================
# PEER CLASSES FOR CROSS-SECTIONAL FAMILIES (2026-09-30).
#
# A cross-sectional hypothesis ranks an instrument AGAINST ITS CLASS at a point in time, so it
# needs an answer to "which instruments is this one ranked against", and that answer has to be
# the same in the gauntlet, the forward clock and the live executor. It is derived here, from the
# same broker registry the lane is, and never from a symbol list: a Fusion instrument listed
# tomorrow joins its class the day it appears.
#
# THE HYPOTHESIS LANE AND SHARE CFDs HAVE PEER CLASSES. Share CFDs rank as one `equity` class
# (the principal's amendment of 2026-09-30 to the two-lane order: cross-sectional books AND the
# news lane for single names). An UNCLASSIFIED symbol is ranked against nothing -- absence is not
# a permission here either.
#
# FIVE CLASSES, AND THE CONSTRUCTION RULES THAT KEEP ONE BET FROM BEING COUNTED TWICE:
#   fx_usd     every pair with a USD leg, read as the NON-USD CURRENCY's value in dollars
#              (EURUSD as-is, USDJPY inverted), so the rank is a rank of currencies -- the
#              construction in Menkhoff, Sarno, Schmeling & Schrimpf (2012).
#   fx_cross   pairs with no USD leg, ranked as pairs. Each is the difference of two USD legs, so
#              they are their own cross-section rather than extra members of the first one.
#   index      equity indices. The dollar basket (a symbol spelled USD...) is a currency and is
#              left out: ranking it beside NAS100 would be ranking an FX bet as an equity one.
#   commodity  metals, energy and softs as one class (Asness, Moskowitz & Pedersen 2013 rank
#              commodities as one book). A metal quoted in a second currency (XAUEUR, XAGEUR,
#              XAUAUD) is the metal times an FX rate and is left out for the same reason.
#   crypto     Fusion's crypto CFDs.
# Bonds have their own class but three members in the registry; below MIN_CLASS_MEMBERS a rank is
# a sort of three, and the class reports as too small rather than borrowing members.
# =============================================================================================

#: Members a class must have present on a date before any member of it is ranked on that date.
MIN_CLASS_MEMBERS = 5

_FX_CLASSES = _norm_set({"forex", "forex majors", "forex crosses", "forex exotics", "fx",
                         "fx_major", "fx_cross", "fx_exotic"})
_INDEX_CLASSES = _norm_set({"indices", "index"})
_COMMODITY_CLASSES = _norm_set({"commodity", "commodities", "soft commodity", "soft commodities",
                                "soft", "metal", "metals", "precious metals", "energy"})
_BOND_CLASSES = _norm_set({"bond", "bonds"})
_CRYPTO_CLASSES = _norm_set({"crypto", "cryptocurrency"})

#: The peer classes, in the order reports list them.
PEER_CLASSES: tuple[str, ...] = ("fx_usd", "fx_cross", "index", "commodity", "bond", "crypto",
                                 "equity")


def _pair_legs(symbol: str) -> tuple[str, str] | None:
    s = str(symbol).strip().upper()
    if len(s) == 6 and s.isalpha():
        return s[:3], s[3:]
    return None


def peer_class(symbol: str) -> str | None:
    """The cross-sectional class `symbol` is ranked within, or None. Never raises.

    `equity` for a share CFD. None for every other symbol outside the hypothesis lane, and for the
    two constructions that would
    count one bet twice (a metal quoted in a second currency, the dollar basket among indices).
    """
    try:
        if is_equity(symbol):
            return "equity"
        if lane(symbol) != HYPOTHESIS:
            return None
        klass = asset_class_of(symbol)
    except Exception:
        return None
    legs = _pair_legs(symbol)
    if klass in _FX_CLASSES:
        if legs is None:
            return None
        return "fx_usd" if "USD" in legs else "fx_cross"
    if klass in _INDEX_CLASSES:
        return None if str(symbol).strip().upper().startswith("USD") else "index"
    if klass in _COMMODITY_CLASSES:
        if legs is not None and legs[0].startswith("X") and legs[1] != "USD":
            return None
        return "commodity"
    if klass in _BOND_CLASSES:
        return "bond"
    if klass in _CRYPTO_CLASSES:
        return "crypto"
    return None


def usd_orientation(symbol: str) -> int:
    """+1 when the pair's price IS the non-USD currency in dollars (XXXUSD), -1 when it must be
    inverted to read that way (USDXXX), +1 for anything that is not a USD pair."""
    legs = _pair_legs(symbol)
    if legs is not None and legs[0] == "USD" and legs[1] != "USD":
        return -1
    return 1


def peer_classes() -> dict[str, list[str]]:
    """{class: members} over the whole registry, in the registry's own casing, one pass."""
    out: dict[str, list[str]] = {k: [] for k in PEER_CLASSES}
    for k, v in _registry().items():
        c = peer_class(k)
        if c is not None:
            out.setdefault(c, []).append(str(v.get("symbol") or k))
    return {k: sorted(set(v)) for k, v in out.items()}


def class_members(klass: str) -> list[str]:
    """Every registry symbol whose peer class is `klass`, sorted."""
    return list(peer_classes().get(str(klass), []))


# =============================================================================================
# REGIONS (2026-11-03): BREADTH BY COUNTRY, READ FROM THE REGISTRY, NEVER A SYMBOL LIST.
#
# THE NARROWING THIS ANSWERS. Several miners took the first N symbols of an ALPHABETICAL or
# FILE-SIZE order (`sorted(...)[:12]`, a budget that stops a sorted walk, the largest parquet
# files first). Every one of those orders puts the long-history majors first and the emerging
# currencies last -- USDTRY, USDZAR, ZARJPY and USDIDR sort to the tail of the alphabet, and their
# files are the youngest -- so the dark regions of REGION_GAP_RANK_2026-11-03 were dark on the
# symbol side too. `region_interleave` takes ONE symbol from each region in turn, so any cap of N
# spans N regions before it repeats one; nothing is removed from the walk, only reordered.
#
# A region is a COUNTRY CODE (ISO 3166 alpha-2, the same vocabulary the deep-forest grounds use),
# derived per symbol from MetaTrader's own registry: an FX pair's non-major leg (its profit
# currency when both legs are G10), an index's profit currency, `global` for a dollar-priced
# commodity, a crypto CFD or the dollar basket. The currency -> country table below is ISO 4217
# vocabulary: it names currencies, never instruments, so a pair listed tomorrow is placed the
# day it appears.
# =============================================================================================

#: G10 currencies. A pair with a non-G10 leg is placed in that leg's country.
G10_CURRENCIES: frozenset[str] = frozenset({"USD", "EUR", "JPY", "GBP", "CHF", "CAD", "AUD",
                                            "NZD", "SEK", "NOK"})
#: ISO 4217 -> ISO 3166 alpha-2 (EUR -> the euro area, `eu`).
CURRENCY_REGION: dict[str, str] = {
    "USD": "us", "EUR": "eu", "JPY": "jp", "GBP": "gb", "CHF": "ch", "CAD": "ca", "AUD": "au",
    "NZD": "nz", "SEK": "se", "NOK": "no", "DKK": "dk", "PLN": "pl", "HUF": "hu", "CZK": "cz",
    "RON": "ro", "BGN": "bg", "ISK": "is", "TRY": "tr", "ZAR": "za", "ILS": "il", "RUB": "ru",
    "UAH": "ua", "KZT": "kz", "MXN": "mx", "BRL": "br", "CLP": "cl", "COP": "co", "PEN": "pe",
    "ARS": "ar", "CNH": "cn", "CNY": "cn", "HKD": "hk", "SGD": "sg", "KRW": "kr", "TWD": "tw",
    "INR": "in", "IDR": "id", "THB": "th", "MYR": "my", "PHP": "ph", "VND": "vn", "PKR": "pk",
    "SAR": "sa", "AED": "ae", "QAR": "qa", "KWD": "kw", "EGP": "eg", "NGN": "ng", "KES": "ke",
    "MAD": "ma",
}
GLOBAL = "global"


def region_of(symbol: str) -> str:
    """The country a hypothesis-lane symbol's edge is local to, or `global`. Never raises.

    FX: the non-G10 leg if there is one (USDTRY -> tr, EURPLN -> pl, ZARJPY -> za); otherwise the
    profit currency of a G10 cross (EURGBP -> gb), and the non-USD leg of a G10 dollar pair
    (USDJPY -> jp). Indices: the profit currency (JPN225 -> jp, CHINAH -> hk). A metal quoted in
    another currency (XAUAUD) takes that currency's country. Everything else -> `global`.
    """
    try:
        sym = str(symbol).strip().upper()
        row = _registry().get(sym) or {}
        klass = asset_class_of(sym)
        legs = _pair_legs(sym)
        profit = str(row.get("currency_profit") or "").upper()
        if klass in _FX_CLASSES and legs is not None:
            em = [c for c in legs if c not in G10_CURRENCIES]
            if em:
                return CURRENCY_REGION.get(em[0], GLOBAL)
            non_usd = [c for c in legs if c != "USD"]
            pick = profit if profit in legs and profit != "USD" else (non_usd[0] if non_usd
                                                                      else "")
            return CURRENCY_REGION.get(pick, GLOBAL)
        if klass in _INDEX_CLASSES:
            if sym.startswith("USD"):
                return GLOBAL                                 # the dollar basket is FX
            return CURRENCY_REGION.get(profit, GLOBAL)
        if klass in _COMMODITY_CLASSES and legs is not None and legs[1] != "USD":
            return CURRENCY_REGION.get(legs[1], GLOBAL)
        if klass in _BOND_CLASSES:
            return CURRENCY_REGION.get(profit, GLOBAL)
    except Exception:
        return GLOBAL
    return GLOBAL


def hypothesis_regions() -> dict[str, list[str]]:
    """{region: hypothesis-lane symbols} over the whole registry. Share CFDs are NOT here: they
    are event-lane (and cross-sectional-class-book) instruments, never statistical ones."""
    out: dict[str, list[str]] = {}
    for k, v in _registry().items():
        if lane(k) != HYPOTHESIS:
            continue
        out.setdefault(region_of(k), []).append(str(v.get("symbol") or k))
    return {r: sorted(set(s)) for r, s in sorted(out.items())}


def region_interleave(symbols: Iterable[str], *, rotation: int = 0) -> list[str]:
    """`symbols` reordered one-per-region round robin, every symbol kept exactly once.

    Inside a region the input order is the starting order (so a caller's own priority -- file
    size, judged count -- decides which member opens at rotation 0). Regions are visited
    smallest-first, so a two-member region (TRY, ZAR) is reached on the first lap rather than
    after the eight-member euro area.

    ROTATION MOVES BOTH ORDERS, so a cap cannot starve anyone. Pass `r` opens on region
    `r % R` (R regions) and opens each region on its member `(r // R) % len(region)`. Over R
    consecutive passes every region is FIRST once; over R * (largest region) passes every member
    of every region has been first in its region at least once -- so any cap >= 1 reaches every
    symbol inside that many passes. Callers pass hours since the epoch.
    """
    buckets: dict[str, list[str]] = {}
    for s in dict.fromkeys(str(x) for x in symbols):
        buckets.setdefault(region_of(s), []).append(s)
    order = sorted(buckets, key=lambda r: (len(buckets[r]), r))
    if order and rotation:
        k = rotation % len(order)
        order = order[k:] + order[:k]
        lap = rotation // len(order)
        for r in order:
            b = buckets[r]
            j = lap % len(b)
            buckets[r] = b[j:] + b[:j]
    out: list[str] = []
    i = 0
    while len(out) < sum(len(v) for v in buckets.values()):
        for r in order:
            if i < len(buckets[r]):
                out.append(buckets[r][i])
        i += 1
    return out


def cap_line(ordered: list[str], chosen: list[str], cap: int) -> dict[str, Any]:
    """The missed-growth line a KEPT symbol cap owes (GROWTH GOVERNANCE: no cap without its
    line): how many eligible symbols the cap left out and which regions it never reached. The
    E[log W] price of the cap is UNMEASURED, and said so."""
    pick = set(chosen)
    left = [s for s in ordered if s not in pick]
    reached = {region_of(s) for s in chosen}
    unreached = sorted({region_of(s) for s in left} - reached)
    return {"cap": int(cap), "eligible": len(ordered), "chosen": len(chosen),
            "left_out": len(left), "regions_reached": sorted(reached),
            "regions_left_dark": unreached,
            "verdict": "NOT_BINDING" if not left else "UNMEASURED",
            "why": ("cap did not bind" if not left else
                    f"{len(left)} hypothesis-lane symbol(s) beyond the cap this pass; the hourly "
                    "rotation (over regions AND within each region) reaches every one within "
                    "regions x largest-region passes; the E[log W] cost is UNMEASURED")}


def breadth_window(candidates: Iterable[str], cap: int, *, rotation: int = 0
                   ) -> tuple[list[str], dict[str, Any]]:
    """The first `cap` of `region_interleave(candidates)`, and its `cap_line`."""
    ordered = region_interleave(candidates, rotation=rotation)
    chosen = ordered[:max(0, int(cap))]
    return chosen, cap_line(ordered, chosen, cap)
