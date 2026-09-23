"""EAST AFRICA -- one pack, three treasuries, one physical economy: ET, TZ and UG.

The department answers for Ethiopia, Tanzania and Uganda at once because they ARE one physical
system with three currencies: Ugandan crude will leave through a Tanzanian port on the EACOP
line to Tanga, Congolese and Zambian copper leaves through Dar es Salaam on the Central
Corridor, and gold mined or bought anywhere in the three moves on the same lorries. Kenya
(`ke`) is the regional financial and logistics hub of all three and has its own pack; this one
is its declared COMPLEMENT -- `ke` owns Mombasa, the Northern Corridor, the published CBK
buy/sell spread and the Kenyan two-season rainfall cycle, and this pack owns the Central
Corridor, the three currencies Kenya does not carry, and the Ethiopian BELG and KIREMT seasons
that are not Kenya's long and short rains.

THREE PUBLISHED, DATED, PRICE-RELEVANT MECHANISMS EARN THE TRIAL BUDGET. The Bank of Tanzania
BUYS DOMESTIC GOLD for reserves and the state requires licensed miners to offer a share of
output at home, on a top-fifteen producer of about fifty tonnes a year. Ethiopia FLOATED THE
BIRR on 2024-07-29 after decades of a crawling peg and the currency lost more than half its
value within weeks, changing the export economics of the world's fifth-largest arabica crop.
Uganda BECOMES AN OIL PRODUCER in 2025-2026 from Tilenga and Kingfisher through a pipeline
that ends in Tanzania. A fourth is a window rather than a flow: Uganda's official gold exports
have run an order of magnitude above its own mine production, and the 2021 export levy switched
that declared route off and then on again, on a series the Bank of Uganda publishes monthly.

ETB, TZS and UGX are ABSENT from the broker and every one is named in `TRANSMISSION_TARGETS`
with its regime, its parallel-market spread and the symbols its economics route into. No
single-name equity appears in any instrument tuple (two-lane order, 2026-09-06) and no
crypto-exchange ground is hunted (mandate 2026-08-18).

Data only; see pack.py. `pack()` builds the framework object, `mine(ctx)` is the department
entry, and `cells()` is what it mints for the gauntlet. NOTHING is re-exported here on purpose:
`from countries.east_africa import pack` must resolve to the MODULE, exactly as it does for
every sibling department, and a convenience re-export of the `pack()` FUNCTION would shadow it.
"""

__all__ = ["pack"]
