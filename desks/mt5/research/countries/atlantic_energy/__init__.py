"""THE ATLANTIC HYDROCARBON PROVINCE: Guyana, Trinidad and Tobago, Venezuela, Suriname.

WHAT THIS DEPARTMENT IS FOR, IN ONE SCREEN. Four countries sit on one geological and one
commercial trend between the Orinoco and the Demerara, and between them they hold the fastest
supply RAMP on earth, the western hemisphere's LNG and ammonia hub, the largest proven reserve
base on the planet running at a fraction of capacity, and the next sanctioned deepwater
development in the same trend. This broker quotes XBRUSD, XTIUSD and XNGUSD directly, so every
one of those is an executable question rather than an interesting fact.

THE MECHANISM NOBODY MODELS AS A SERIES. Guyana went from ZERO to roughly 650,000 barrels a day
in six years, and it did it on a PUBLISHED, DATED, SANCTIONED SCHEDULE: each floating production
vessel has a sanction date, a nameplate capacity and a first-oil target announced by the operator
and by Guyana's Ministry of Natural Resources years in advance. A dated multi-year supply curve
against a liquid contract is the cleanest input an oil-balance mechanism can have, and almost
nobody carries it as a scheduled series. `sanctioned_capacity_on(day)` is that series, and the
per-vessel cells of domain AE-A are what it mints.

THE SOVEREIGN WHOSE REVENUE IS A PUBLISHED FORMULA. Guyana's 2016 Stabroek production-sharing
agreement caps cost recovery at 75% of revenue, splits the remaining profit oil 50/50 and adds a
2% royalty. `government_take(revenue, costs)` computes it. The Natural Resource Fund publishes
monthly receipts and its withdrawal rule is statutory under the 2021 NRF Act, and the lifting
entitlements are announced CARGO BY CARGO. There is no other country on this desk whose fiscal
take can be computed from the oil price with a published formula.

THE GAS THAT IS RUNNING OUT AND THE FERTILISER THAT DEPENDS ON IT. Trinidad's gas is in
structural decline, which shows up in Atlantic LNG train utilisation, in the cross-border Dragon
licence that the United States granted, revoked and re-granted on dated published days, and in
the ammonia and methanol output of Point Lisas. Trinidadian ammonia is a real share of Atlantic
basin nitrogen supply, and nitrogen cost is an input to CORN and WHEAT acreage economics. That
chain is testable and it is carried here with its control named.

THE SUPPLY THAT IS A FUNCTION OF A LICENCE. Venezuelan production moves on the dated, published,
lawful-to-read administrative acts of a foreign treasury: General Licence 44 of 18 October 2023,
its replacement by GL 44A on 17 April 2024, the individual company licences and the 2025 changes.
`sanctions_state(day)` returns which regime was in force. OPEC publishes Venezuelan output in TWO
series that disagree -- direct communication and secondary sources -- and the GAP between them is
itself an observable that `opec_gap()` measures.

THE FORWARD CONTROL. Suriname sanctioned Block 58 (GranMorgu) in October 2024 with first oil
targeted for 2028, in the same trend as Guyana and on a later clock. A second ramp with a
different date is the negative control the Guyanese series has never had.

WHAT IS ABSENT. GYD, TTD, VES and SRD are NONE OF THEM QUOTED by this broker, and neither are
ammonia, methanol, LNG, the Merey heavy-sour grade or any local bond or equity. Every one is
named in `TRANSMISSION_TARGETS` with the broker symbols that carry its economics and the basis
risk written down: Henry Hub is NOT Atlantic LNG, and a study that swapped one for the other
would be measuring the arbitrage rather than the shock.

LAWFULNESS. Venezuela is under a sanctions regime. Nothing in this pack touches a sanctioned
entity's private systems and nothing bypasses an access control. Everything is PUBLIC: OFAC's own
published licences and FAQs, OPEC's Monthly Oil Market Report, EIA, the US Federal Register,
published court dockets, national statistics and the press. Sanctions constrain TRANSACTIONS, not
the reading of published administrative acts -- and the desk executes only broker symbols, never
a Venezuelan, Guyanese, Trinidadian or Surinamese instrument.

NATIVE GROUND: English (Guyana and Trinidad, where it is the official language and therefore the
native ground rather than a shortcut), SPANISH (Venezuela), DUTCH and SRANAN TONGO (Suriname),
and Guyanese Creolese, in which Kaieteur News writes its best-read column and in which the
backdam gold economy is actually discussed.

WHAT IS DECLARED ABSENT. Venezuela's national statistics office stopped publishing most series
for years and PDVSA has published no audited accounts since 2016. That gap is one of the most
important facts in this pack, so it is declared by name in `NO_LAWFUL_GROUND` with its LAWFUL
SUBSTITUTE beside it -- OPEC secondary sources, the Venezuelan Finance Observatory, mirror
customs data from the United States and China, and tanker-tracking press reports.

Data only; the mechanisms, tables and miners are in `pack.py`.
"""
#: The submodule carries everything. Left as a SUBMODULE rather than re-exported as a name,
#: because `from .pack import pack` would shadow the module `countries.atlantic_energy.pack` with
#: the function `pack()` and break every importer that reads the pack as a module (the tests,
#: `resolve_pack`, `load_custom_miners`).
__all__ = ["pack"]
