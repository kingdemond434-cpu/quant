"""What each MT5 instrument is economically a function of -- named driver sets, one per claim.

THE DEFECT THIS REPLACES. `orthogonal_sweep._factor_symbols` builds ONE factor basket for the
entire sweep: the longest-history instrument from each asset class, deepened to eight. Every
symbol in the universe is then regressed on the same eight instruments. That basket is chosen by
DATA DEPTH, so it says nothing about why one instrument should explain another, and the residual
it leaves is the same object for gold, for the Nikkei and for 3M. 140 cross_asset_residual
candidates were built that way and `funnel_census` records the result: 348 failures, zero
certificates. A residual with no economic identity is not a hypothesis, it is a subtraction.

WHAT A DRIVER SET IS. A small NAMED group of Fusion-tradeable instruments together with the
reason they should price the target, e.g.

    XAUUSD ~ USDX + UST10Y + XAGUSD + US500
    "gold is a zero-coupon dollar asset: it is priced off the dollar, off the real rate it
     competes with, off its own metals complex, and off the risk appetite that bids it"

Each set is a separate falsifiable claim, not a bigger regression. XAUUSD against the dollar
alone and XAUUSD against the dollar plus real rates are two different statements about what gold
is, and the desk should be allowed to find that one of them leaves a tradeable residual and the
other does not. Kitchen-sink regressions hide exactly that.

WHY THE DRIVERS ARE INSTRUMENTS RATHER THAN SERIES. Every driver named here is a symbol in the
Fusion registry, so `family_inputs.resolve` rebuilds the cell from `factor_symbols` with no new
acquisition, the forward engine can enrol it, and -- the part that matters -- the residual is a
spread the desk could actually hold. `ΔReal Yield` in the principal's formula is UST10Y here:
the traded price of the ten-year, whose returns are the negative of yield changes up to
convexity. That is the honest tradeable version of the quantity, and it beats a FRED series that
publishes at a lag the family would have to pretend it did not have.

WHAT IS DERIVED AND WHAT IS DECLARED. Asset class, quote currency, symbol legs and bar depth are
READ FROM THE REGISTRY -- no symbol list is hardcoded, so the map moves as the offering does.
The economic priors themselves ARE declared, because they have to be: `AUD is a commodity
currency` is a claim about the world that no amount of reading `universe.json` will produce, and
burying it in a correlation screen would only mean the desk had learned it from the same prices
it is about to trade. Every declared prior below carries its reason, and gate 1 judges it.

CRYPTO. The 14 crypto symbols here are Fusion CFDs read from the desk's own registry, which the
standing mandate names as part of the MT5 universe. No crypto-exchange venue is contacted, no
exchange-native universe is enumerated, and nothing here is hunted anywhere but Fusion.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

#: Symbol roles resolved BY NAME, in preference order, against whatever the registry actually
#: carries. These are the six latent forces the sets below are built from; a role that resolves
#: to nothing simply drops the sets that need it, and the engine reports the drop rather than
#: substituting a proxy nobody chose.
ROLES: dict[str, tuple[str, ...]] = {
    # The dollar itself is an instrument on this offering. Regressing on USDX is strictly better
    # than a synthesised basket: the beta is against something the desk can quote and hedge.
    "USD": ("USDX", "EURUSD"),
    # Traded ten-year price. Its return is minus the yield change: the real-rate term.
    "RATES": ("UST10Y", "UST05Y", "UKGILT"),
    "RISK": ("US500", "NAS100", "AUS200"),
    "GOLD": ("XAUUSD", "XAUEUR"),
    "OIL": ("XBRUSD", "XTIUSD"),
    "GROWTH": ("XCUUSD", "CHINAH", "HK50"),
}

#: Currencies whose exchange rate is a claim on a specific export, and the role that prices it.
#: DECLARED, with the reason, because it is economics rather than data. Used only to add a
#: commodity leg to a pair that already gets the dollar and rates sets.
COMMODITY_CURRENCIES: dict[str, tuple[str, str]] = {
    "AUD": ("GROWTH", "Australia's terms of trade are industrial metals and bulk commodities"),
    "NZD": ("GROWTH", "New Zealand's export receipts move with global growth demand"),
    "CAD": ("OIL", "Canada is a net crude exporter and CAD tracks the crude it sells"),
    "NOK": ("OIL", "Norway's currency is a claim on North Sea crude revenue"),
    "ZAR": ("GOLD", "South Africa's export base and reserves are precious metals"),
    "BRL": ("GROWTH", "Brazil's currency moves with the commodity complex it exports"),
    "CLP": ("GROWTH", "Chile's export receipts are overwhelmingly copper"),
    "MXN": ("OIL", "Mexico's fiscal receipts carry a large crude component"),
    "RUB": ("OIL", "Russia's external account is dominated by energy exports"),
}

#: Currencies bid when risk is sold. Their crosses get a risk-appetite set rather than a
#: commodity one.
HAVEN_CURRENCIES = frozenset({"JPY", "CHF"})

#: The dollar index is classed `Indices` by the broker but it is not an equity index; it is the
#: USD role. Naming it here keeps it out of every index peer group, where it would otherwise
#: masquerade as a regional equity market.
_NOT_AN_EQUITY_INDEX = frozenset({"USDX"})

PRECIOUS = ("XAUUSD", "XAGUSD", "XPTUSD", "XPDUSD")
INDUSTRIAL = ("XCUUSD", "XALUSD", "XNIUSD", "XZNUSD", "XPBUSD")
ENERGY_SYMS = ("XTIUSD", "XBRUSD", "XNGUSD")

#: A driver set is worthless below this; two names is a pair spread, which the desk already has
#: as `relative_value`. One name is allowed ONLY for the identity sets (triangle, quanto, crude
#: spread) where the single driver IS the economic claim.
MAX_DRIVERS = 5


@dataclass(frozen=True)
class DriverSet:
    """One economic claim about what prices an instrument."""

    target: str
    name: str
    drivers: tuple[str, ...]
    why: str

    @property
    def cell(self) -> str:
        return f"{self.target}.{self.name}"


def _class(meta: dict, sym: str) -> str:
    row = meta.get(sym) if isinstance(meta, dict) else None
    return str((row or {}).get("asset_class") or "")


def _ccy(meta: dict, sym: str) -> str:
    row = meta.get(sym) if isinstance(meta, dict) else None
    return str((row or {}).get("currency_profit") or "")


def _bars(meta: dict, sym: str) -> int:
    row = meta.get(sym) if isinstance(meta, dict) else None
    try:
        return int((row or {}).get("bars") or 0)
    except (TypeError, ValueError):
        return 0


def _role(role: str, meta: dict, have: set[str], exclude: Iterable[str] = ()) -> str | None:
    skip = set(exclude)
    for cand in ROLES.get(role, ()):
        if cand in have and cand not in skip:
            return cand
    return None


def _legs(sym: str, meta: dict) -> tuple[str, str] | None:
    if _class(meta, sym) not in {"Forex", "Forex Exotics"}:
        return None
    if len(sym) != 6 or not sym.isalpha():
        return None
    return sym[:3].upper(), sym[3:].upper()


def _usd_leg_instrument(ccy: str, have: set[str]) -> str | None:
    """The instrument that prices one currency against the dollar, either way round."""
    if ccy == "USD":
        return None
    for cand in (f"{ccy}USD", f"USD{ccy}"):
        if cand in have:
            return cand
    return None


def _add(out: list[DriverSet], target: str, name: str,
         drivers: Iterable[str | None], why: str) -> None:
    """Append a set, dropping unresolved roles and the target itself, deduplicated and capped."""
    seen: list[str] = []
    for d in drivers:
        if d and d != target and d not in seen:
            seen.append(d)
    if not seen or len(seen) > MAX_DRIVERS:
        return
    if any(s.drivers == tuple(seen) for s in out if s.target == target):
        return
    out.append(DriverSet(target=target, name=name, drivers=tuple(seen), why=why))


def _soft_peers(sym: str, softs: list[str]) -> list[str]:
    """Same-crop peers, found by shared name structure rather than a hardcoded crop table.

    The offering carries three genuine same-crop pairs -- arabica/robusta coffee, London/New York
    cocoa, white/raw sugar -- and their basis is one of the oldest real relative-value trades in
    commodities. A shared 3-character prefix or 4-character suffix picks exactly those out and
    leaves CORN, COTTON, WHEAT, SOYBEAN and OJ (which share nothing but an alphabet) alone.
    """
    peers = []
    for other in softs:
        if other == sym:
            continue
        if sym[:3] == other[:3] or (len(sym) >= 4 and len(other) >= 4 and sym[-4:] == other[-4:]):
            peers.append(other)
    return peers


def driver_sets(target: str, meta: dict[str, Any],
                available: Iterable[str] | None = None) -> list[DriverSet]:
    """Every economically plausible driver set for one instrument, each a separate hypothesis."""
    have = set(available) if available is not None else set(meta)
    if target not in have:
        return []
    cls = _class(meta, target)
    out: list[DriverSet] = []
    usd = _role("USD", meta, have, exclude=[target])
    rates = _role("RATES", meta, have, exclude=[target])
    risk = _role("RISK", meta, have, exclude=[target])

    legs = _legs(target, meta)
    if legs:
        base, quote = legs
        # THE TRIANGLE IS THE STRONGEST PRIOR ON THE DESK. EURGBP is EURUSD divided by GBPUSD up
        # to the spread; regressing the cross on its two dollar legs is an identity, not a fit,
        # so what is left over is cross-specific flow and nothing else. This is the residual
        # Simons described the equity book trading, expressed in FX.
        tri = [x for x in (_usd_leg_instrument(base, have),
                           _usd_leg_instrument(quote, have)) if x]
        if len(tri) == 2:
            _add(out, target, "triangle", tri,
                 f"{target} is {tri[0]} against {tri[1]} up to the cross spread; the residual is "
                 "flow specific to this cross rather than to either currency")
        _add(out, target, "dollar_rates", [usd, rates],
             "an exchange rate is a relative claim on two policy rates, priced against the "
             "dollar and the term structure it competes with")
        for ccy in (base, quote):
            role_reason = COMMODITY_CURRENCIES.get(ccy)
            if role_reason:
                role, why = role_reason
                _add(out, target, f"commodity_{ccy.lower()}",
                     [_role(role, meta, have, exclude=[target]), usd],
                     f"{why}, so {ccy} is partly a commodity price wearing a currency's name")
        if HAVEN_CURRENCIES & {base, quote}:
            _add(out, target, "risk_appetite", [risk, usd],
                 "a haven leg makes this pair a risk-appetite instrument: it is bid when equity "
                 "risk is sold, independently of either country's rates")

    elif cls == "Commodities" and target in PRECIOUS:
        _add(out, target, "dollar_real_rates", [usd, rates],
             "a precious metal is a zero-coupon dollar asset: it is priced off the dollar it is "
             "quoted in and off the real rate it forgoes")
        _add(out, target, "precious_complex", [p for p in PRECIOUS if p in have and p != target],
             "the precious complex shares a monetary and a physical bid; what one metal does "
             "that the others do not is specific to it")
        _add(out, target, "full_monetary",
             [usd, rates, next((p for p in PRECIOUS if p in have and p != target), None), risk],
             "the full monetary statement: dollar, real rate, own complex and the risk appetite "
             "that decides whether the metal is a hedge or a position")

    elif cls == "Commodities" and target in INDUSTRIAL:
        _add(out, target, "growth_dollar",
             [_role("GROWTH", meta, have, exclude=[target]), usd],
             "an industrial metal is a claim on global manufacturing demand, quoted in dollars")
        _add(out, target, "industrial_complex",
             [m for m in INDUSTRIAL if m in have and m != target][:MAX_DRIVERS],
             "base metals share smelting, freight and China demand; the leftover is specific to "
             "this metal's own inventory and supply")

    elif cls in {"Commodities", "Energy"} and target in ENERGY_SYMS:
        others = [e for e in ENERGY_SYMS if e in have and e != target]
        if others:
            _add(out, target, "energy_complex", others,
                 "crude grades and gas share the same demand and freight; the Brent-WTI basis is "
                 "a transport and inventory spread, not a directional oil view")
        _add(out, target, "dollar_risk", [usd, risk],
             "energy is a dollar-quoted cyclical: the dollar prices it and risk appetite decides "
             "how much of the cycle is discounted")

    elif cls == "Commodities":
        # Currency-quoted metals (XAUEUR, XAGEUR, XAUAUD): a quanto of a USD metal.
        base = target[:3]
        quote_ccy = _ccy(meta, target) or target[3:]
        usd_metal = next((m for m in PRECIOUS + INDUSTRIAL if m in have and m.startswith(base)),
                         None)
        fx = _usd_leg_instrument(quote_ccy, have) if quote_ccy else None
        if usd_metal and fx:
            _add(out, target, "quanto_triangle", [usd_metal, fx],
                 f"{target} is {usd_metal} converted through {fx}: an arithmetic identity, so the "
                 "residual is quoting and liquidity friction rather than a view on the metal")
        _add(out, target, "dollar_real_rates", [usd, rates],
             "a metal quoted in another currency still answers to the dollar and the real rate")

    elif cls == "Soft Commodity":
        softs = sorted(s for s in have if _class(meta, s) == "Soft Commodity")
        peers = _soft_peers(target, softs)
        if peers:
            _add(out, target, "crop_basis", peers[:MAX_DRIVERS],
                 "two contracts on the same crop differ by grade, delivery point and freight; "
                 "that basis is a physical spread with its own mean and its own shocks")
        _add(out, target, "dollar_growth", [usd, _role("GROWTH", meta, have, exclude=[target])],
             "an agricultural contract is a dollar-quoted claim on demand; weather is the "
             "residual this set is built to expose")

    elif cls == "Indices" and target not in _NOT_AN_EQUITY_INDEX:
        regional = sorted(s for s in have
                          if _class(meta, s) == "Indices" and s not in _NOT_AN_EQUITY_INDEX
                          and s != target and _ccy(meta, s) == _ccy(meta, target))
        world = _role("RISK", meta, have, exclude=[target])
        if world:
            _add(out, target, "global_beta", [world],
                 "equity indices share one global risk factor; what a market does beyond it is "
                 "its own economy, its own currency and its own session")
        if regional:
            _add(out, target, "regional_peers", regional[:MAX_DRIVERS],
                 "indices sharing a quote currency share a central bank and a trading session, "
                 "so the leftover is composition rather than macro")
        _add(out, target, "rates_dollar", [rates, usd, world],
             "an equity index is a discounted cash-flow claim: the discount rate and the dollar "
             "price it before any earnings news does")

    elif cls == "Bonds":
        _add(out, target, "curve", [b for b in have
                                    if _class(meta, b) == "Bonds" and b != target][:MAX_DRIVERS],
             "two points on a yield curve move with one level factor; the residual is slope, "
             "which is a policy expectation rather than a duration bet")
        _add(out, target, "dollar_risk", [usd, risk],
             "sovereign duration is priced against the currency it is issued in and against the "
             "risk assets it competes with")

    elif cls == "Crypto":
        btc = "BTCUSD" if "BTCUSD" in have else None
        if btc and target != btc:
            _add(out, target, "btc_beta", [btc],
                 "an alternative coin's CFD is dominated by one common crypto factor; the "
                 "residual is what is specific to this coin rather than to the asset class")
        _add(out, target, "risk_dollar", [risk, usd, _role("GOLD", meta, have, exclude=[target])],
             "a crypto CFD trades as a high-beta risk asset quoted in dollars, with a competing "
             "store-of-value bid")

    elif cls == "Equities" or (not cls and _ccy(meta, target)):
        home = {"USD": "US500", "EUR": "GER40", "GBP": "UK100", "JPY": "JPN225",
                "AUD": "AUS200", "CAD": "CA60", "HKD": "HK50"}.get(_ccy(meta, target))
        market = home if home in have else _role("RISK", meta, have, exclude=[target])
        if market:
            _add(out, target, "market_beta", [market],
                 "a single name is its market plus what is specific to the company; the residual "
                 "IS the idiosyncratic return, which is the object the equity book trades")
            _add(out, target, "market_rates", [market, rates, usd],
                 "a single name discounted properly: market beta, the discount rate, and the "
                 "dollar that prices its foreign revenue")
    return out


def universe_driver_sets(meta: dict[str, Any],
                         available: Iterable[str] | None = None,
                         min_bars: int = 0) -> list[DriverSet]:
    """Every hypothesis this map can state, over every instrument the desk actually holds bars for.

    A set is kept only when the TARGET and EVERY DRIVER clear `min_bars`: a driver with no
    history does not merely weaken the regression, it truncates the joint sample for the target
    as well, because the panel is an inner join. That truncation is how one 8,079-bar instrument
    in the old global basket cost XAUUSD forty thousand bars on every cell it appeared in.
    """
    have = set(available) if available is not None else set(meta)
    if min_bars > 0:
        have = {s for s in have if _bars(meta, s) >= min_bars}
    out: list[DriverSet] = []
    for target in sorted(have):
        out.extend(driver_sets(target, meta, have))
    return out
