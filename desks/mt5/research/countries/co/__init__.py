"""COLOMBIA -- oil, coffee, and the only country in this command whose farm-gate price is an
explicit published FORMULA in the exchange rate.

Colombia is a TRANSMISSION-ONLY pack: USDCOP is not in this broker's registry and neither is the
COLCAP. What makes it worth a department anyway is a mechanism no other country here has. The
Federacion Nacional de Cafeteros publishes a DAILY internal reference price for coffee that is
computed, openly, from the New York 'C' contract, the Colombian mild differential and the TRM --
so the peso is an ARITHMETIC TERM in the price a Colombian farmer receives, with the formula in
public. Everywhere else in this command the currency-to-producer link has to be estimated; here
it is published, which makes it the cleanest available test of whether a terms-of-trade channel
works through price or through quantity.

The second reason is oil. Crude is roughly a third of Colombian exports, Ecopetrol is majority
state-owned, and the Cano Limon-Covenas pipeline is attacked often enough that supply
interruptions are a dated, counted event class with a public register.

`pack.py` holds the department as data: BanRep's calendar, the TRM's two-day chain, the coffee
formula, the options-based FX intervention rule with its 20% trigger, the Emiliani Monday-shifting
holiday law, and the transmission seeds into XBRUSD, XTIUSD, COFARA and the EM peers.
"""
from __future__ import annotations

__all__ = ["pack"]
