"""CENTRAL AMERICA: the chokepoint that publishes its own constraint, and six monies on one
isthmus.

WHAT THIS DEPARTMENT IS FOR, IN ONE SCREEN. Panama, Guatemala, Honduras, Costa Rica, Nicaragua
and El Salvador share one isthmus, one trade structure, one harvest calendar, one drought and one
migration corridor -- and run FOUR DIFFERENT MONETARY REGIMES on top of it. Six packs would split
every mechanism here down the middle and charge the desk's shared trial budget six times for one
question; holding them together is what turns the differences between them into controls.

THE MECHANISM NOBODY ELSE MINES. The Autoridad del Canal de Panama publishes booking slots,
transits per day, the MAXIMUM AUTHORISED DRAFT, its auction results and the daily level of Gatun
Lake -- in advisories to shipping, in advance, with a stated effective date. It is the only one of
the three great maritime chokepoints whose operator publishes its own binding constraint. In
2023-2024 the Gatun drought cut bookable transits from about 36 a day to 22 and a single slot
cleared near four million dollars at auction. That is a measurable physical constraint on world
trade against contracts the broker quotes: US Gulf grain to Asia (CORN, WHEAT, SOYBEAN), LPG and
refined product (XNGUSD, XTIUSD, XBRUSD) and container freight into US retail. SUEZ AND BAB
EL-MANDEB ARE NAMED AS THE CONTROL: when one chokepoint closes the other's traffic is the
counterfactual, and 2023-2024 constrained both at once for unrelated reasons -- which makes the
pair a control only if both series are carried, and a confound if either is dropped.

WHAT ELSE BELONGS TO THIS ISTHMUS. It is the world's high-grade washed-arabica belt, and each of
five origins publishes MONTHLY export volumes through a national coffee institute that issues the
export permit -- so the number is a count, not a survey -- on an October-to-September harvest
year, with COFROB as the non-belt control and the Brazilian frost and drought as the other half
of a genuine two-origin substitution. Remittances are a fifth to a quarter of GDP in four of the
six and every one of those central banks publishes them monthly against a US labour market whose
policy acts are dated. Cobre Panama -- about 1.5% of world copper -- was ORDERED CLOSED by the
Panamanian Supreme Court in November 2023, a judicial supply shock this desk has almost no other
instance of. And El Salvador's 2021 Bitcoin Law and its 2023-2024 eurobond rally are a dated
sovereign-credit sequence.

THE NATURAL EXPERIMENT. Panama has used the dollar since 1904 with NO CENTRAL BANK AT ALL; El
Salvador dollarised in 2001 and kept a central bank with no instrument; Guatemala runs a managed
float with a PUBLISHED participation rule, Honduras a band with an allocation auction, Costa Rica
a real inflation-targeting float, and Nicaragua a crawl that was stepped to zero in 2024. Six
neighbours, one trade structure, four monetary regimes, and every input published.

WHAT IS ABSENT. PAB AND SVC ARE THE UNITED STATES DOLLAR and are labelled as the dollar rather
than as proxies for it -- a proxy carries basis risk and an identity does not. GTQ, HNL, CRC and
NIO are absent from the broker, as are the canal slots, the container-freight indices and the LPG
complex; each is named in `TRANSMISSION_TARGETS` with its regime and the symbols that carry its
economics, so an absent instrument becomes a transmission hypothesis and never a cell that can
never be filled (L1.49).

WHERE A LAYER GENUINELY DOES NOT EXIST, IT IS DECLARED. Panama has no central bank and therefore
no policy rate, no monetary aggregates and no reserve series -- which is a FACT ABOUT THE COUNTRY
and not a gap, with the Superintendencia de Bancos' banking statistics and the FOMC's own
decisions named as the lawful substitutes. El Salvador's central bank has no instrument.
Nicaragua's independent press operates in exile and its statistical publication has narrowed, with
mirror customs, the IMF Article IV and the labelled exile outlets named as the substitutes. Those
measured refusals live in `NO_LAWFUL_GROUND` and the tests check that each one is true.

THE MANDATE BOUNDARY IS STATED IN FULL. The Salvadoran bitcoin material is a SOVEREIGN POLICY and
FISCAL observable, routed into the broker's own BTCUSD CFD and into the country's credit story. No
crypto-exchange universe is hunted, no venue order book, exchange feed or exchange statistic is
named as a source anywhere in this department, and `ACCESS_CONSTRAINTS` says so by name.

THE TWO-LANE ORDER (2026-09-06) IS ENFORCED HERE. First Quantum, the sugar mills, the apparel
groups, the liner operators and the banks of the Centro Bancario Internacional are ACTORS and
never instruments. No share CFD appears in any instrument tuple in this department.

NATIVE GROUND: Spanish for all six, plus K'ICHE', Q'EQCHI' AND KAQCHIKEL for the Guatemalan
highlands, where the coffee actually grows and where the land-and-labour disputes that interrupt a
harvest are decided in community assembly and reported first in the community press. A
Spanish-only crawl of Guatemala reads the capital's account of the altiplano and calls it the
altiplano.

Data only; the mechanisms, tables and miners are in `pack.py`.
"""
#: The submodule that carries everything. Left as a SUBMODULE rather than
#: re-exported as a name, because `from .pack import pack` would shadow the module
#: `countries.central_america.pack` with the function `pack()` and break every importer
#: that reads the pack as a module (the tests, `resolve_pack`, `load_custom_miners`).
__all__ = ["pack"]
