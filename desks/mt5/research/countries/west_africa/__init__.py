"""WEST AFRICA -- one pack, five jurisdictions, one hard peg: CI, GN, ML, BF and SN.

The department answers for Cote d'Ivoire, Guinea, Mali, Burkina Faso and Senegal at once
because four of the five share ONE CENTRAL BANK and ONE CURRENCY -- the BCEAO and the XOF,
pegged to the euro at 655.957 and guaranteed by the French Treasury -- and the fifth, Guinea,
is the control that makes the peg measurable by floating instead. Ghana (`gh`) has its own
pack and this one is its declared COMPLEMENT: Ghana and Cote d'Ivoire are together about 60%
of world cocoa and they JOINTLY set the Living Income Differential, so the two packs are one
pricing system and this one carries the Ivorian half -- the Conseil du Cafe-Cacao's decreed
farmgate price, its forward export-contract auctions and its weekly arrivals-at-port census --
rather than repeating COCOBOD's.

FOUR PUBLISHED, DATED, PRICE-RELEVANT MECHANISMS EARN THE TRIAL BUDGET. Cote d'Ivoire is the
world's largest cocoa producer at roughly 40% of it and its state DECREES a guaranteed farmgate
price twice a year and sells the crop FORWARD a year ahead through published auctions, against
two liquid broker contracts. Guinea is the world's largest bauxite exporter and holds Simandou,
and its dated disruptions move alumina and therefore XALUSD -- with Chinese customs publishing
bauxite by origin every month as the mirror statistic. Mali and Burkina Faso are top-fifteen
gold producers that rewrote their mining codes in 2023-2024 and, in Mali's case, suspended the
exports of a mine worth roughly 1.5% of world supply. And the CFA franc's hard peg makes every
euro move a ONE-FOR-ONE terms-of-trade shock to four commodity exporters at once.

XOF and GNF are ABSENT from the broker and both are named in `TRANSMISSION_TARGETS` with their
regimes and their carriers. Bauxite, alumina, iron ore and cashew have no contract anywhere and
each says so. No single-name equity appears in any instrument tuple (two-lane order,
2026-09-06) and no crypto-exchange ground is hunted (mandate 2026-08-18).

Data only; see pack.py. `pack()` builds the framework object, `mine(ctx)` is the department
entry, and `cells()` is what it mints for the gauntlet. NOTHING is re-exported here on purpose:
`from countries.west_africa import pack` must resolve to the MODULE, exactly as it does for
every sibling department, and a convenience re-export of the `pack()` FUNCTION would shadow it.
"""

__all__ = ["pack"]
