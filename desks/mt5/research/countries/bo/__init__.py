"""BOLIVIA: a HARD PEG whose reserves ran out in public, on top of the world's largest lithium.

WHAT THIS DEPARTMENT IS FOR, IN ONE SCREEN. Every other Andean pack on this desk is a floating or
managed currency with a metal underneath it. Bolivia is the opposite: 6.96 bolivianos to the
dollar, unchanged since 2 November 2011, carried by a central bank whose usable reserves visibly
exhausted between 2014 and 2024 while the official rate did not move a centavo. A pegged currency
whose reserve backing is emptying -- with the emptying published monthly, and with a SECOND price
for the same currency quoted in the business pages beside it -- is a state this desk has nowhere
else, and the PREMIUM between the two prices is pure arithmetic on two published numbers.

THE MECHANISMS. Ley 1503 of May 2023 explicitly authorised the Banco Central to trade its reserve
gold and buy domestic production, which turns a reserve decision into a dated, lawful, published
supply observable on XAUUSD -- most sovereign gold sales are inferred from an IMF table months
later, and this one has a law with a number. Bolivia is a top-five TIN producer and a top-ten
producer of SILVER, ZINC and LEAD out of Huanuni, Colquiri, San Cristobal and the Cerro Rico
complex; tin is not quoted here, so it is routed through the metals co-produced from the same
concentrates rather than pretended away. The Salar de Uyuni holds the largest identified LITHIUM
resource on earth and has produced almost none of it across a decade of signed and cancelled
agreements. YPFB's GAS exports peaked in 2014 and fell on a published schedule, and in 2024 the
Argentine leg REVERSED -- the same steel now carries Vaca Muerta gas north toward Brazil. And the
SUBSIDISED DIESEL import bill, paid in dollars and sold at a decreed boliviano price, is the
mechanism that consumed the reserves in the first paragraph: every domain here connects to that.

WHAT IS ABSENT. The boliviano is not quoted by this broker, and neither is tin, lithium, the BBV
tape or the sovereign curve. Each is named in `TRANSMISSION_TARGETS` with its regime and the
broker symbols that carry its economics, so an absent instrument produces a transmission
hypothesis and never a cell that can never be filled (L1.49). Two SERIES are declared absent
outright in `POSITIONING_SOURCES`: there is no boliviano positioning data anywhere, and no
foreign-holdings series for the local curve -- so the Peruvian and Brazilian "foreign share of
the curve" observable has no counterpart here and must not be reached for.

THE ROSTER. `libs/research/forests.py` does not yet name `bo` on the latam roster (BR, MX, CL,
CO, PE, AR), so the parity fence cannot credit any pack for it. This department is written AHEAD
of the roster and says so in `ROSTER_STATE` rather than looking like a country the fence already
counted; the mechanism exists whether or not a list mentions it.

THE NEIGHBOURS. `INTERACTIONS` names five. `pe` is the sharpest: a shared border, a shared
Aymara- and Quechua-speaking population, a shared blockade repertoire and the same four metals --
so a simultaneous Bolivian and Peruvian closure is one weather system and a lone one is each
other's control. `cl` and `ar` are the other two corners of the lithium triangle and, for Chile,
the port Bolivian concentrate actually leaves through. `br` is the gas offtaker whose own import
series is the faster and more reliable half of the pair. `cn` is the buyer and the lithium
counterparty.

THE TWO-LANE ORDER (2026-09-06) IS ENFORCED HERE. San Cristobal's parent, Petrobras and the Santa
Cruz exporters are ACTORS and never instruments. No share CFD appears in any instrument tuple.

NATIVE GROUND: Spanish, QUECHUA, AYMARA and GUARANI -- all official under article 5 of the 2009
constitution. The cooperative miners of Potosi and Oruro organise in Quechua and Aymara; the
Chaco gas fields sit on Guarani territory and the Asamblea del Pueblo Guarani negotiates the
royalties that fund them. Erbol broadcasts in Aymara and Quechua. A Spanish-only crawl of Bolivia
misses the two constituencies that can stop a mine and a gas field respectively.

Data only; the mechanisms, tables and miners are in `pack.py`.
"""
#: The submodule that carries everything. Left as a SUBMODULE rather than re-exported as a name,
#: because `from .pack import pack` would shadow the module `countries.bo.pack` with the function
#: `pack()` and break every importer that reads the pack as a module (the tests, `resolve_pack`,
#: `load_custom_miners`).
__all__ = ["pack"]
