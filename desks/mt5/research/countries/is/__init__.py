"""ICELAND: 390,000 people, no grid connection to anywhere, and 2% of the world's aluminium.

WHY ICELAND IS NOT A SMALL NORWAY. Six things belong to this economy and to no other in the
desk's book, and each one is why a domain in `pack.py` exists rather than a row inside a generic
European or Nordic domain:

  1. IT IS THE PUREST POWER-TO-METAL ECONOMY ON EARTH. Iceland generates essentially 100% of its
     electricity from hydro and geothermal, sells roughly three quarters of it to three
     aluminium smelters, and has NO INTERCONNECTOR TO ANYWHERE. The power cannot be exported as
     electricity, so it is exported as metal. That makes the Icelandic reservoir level a
     PHYSICAL BOUND ON WORLD ALUMINIUM SUPPLY, published weekly, by a state-owned utility, in
     Icelandic -- and it makes Icelandic smelters the only large ones on earth whose marginal
     cost does not move with gas.

  2. THE HYDROLOGICAL YEAR IS THE PRODUCTION YEAR. Thorisvatn and Halslon fill on snow and
     glacier melt from May to September and draw down from October to April. A poor water year
     means CURTAILMENT: the utility cuts power to the smelters and to the fishmeal plants, by
     contract, and it has done so repeatedly. Nothing else in this department has a weather
     series that bounds a world commodity's supply on a published clock.

  3. THE FISH QUOTA IS A DATED DECISION WITH A ZERO OPTION. The Marine and Freshwater Research
     Institute advises on cod before each fishing year (1 September to 31 August) and on capelin
     through the winter surveys; the capelin advice has been ZERO in whole seasons. Capelin is
     reduced to fishmeal and fish oil, which substitutes for soymeal in aquaculture feed, so an
     Icelandic quota decision is a dated supply event on a feed complex the broker quotes.

  4. THE CAPITAL CONTROLS ARE A NAMED ERA AND THEY INVALIDATE EVERY POOLED ISK STUDY. Controls
     were imposed on 2008-11-28 and substantially lifted on 2017-03-14, with an offshore-krona
     auction in between. A currency series spanning that boundary is two different objects with
     one name, and this pack refuses to let a study pool them.

  5. THE SPECIAL RESERVE REQUIREMENT IS A RARE, EXPLICIT CAPITAL-FLOW-MANAGEMENT TOOL. From
     2016 the central bank required a fraction of new foreign inflows into krona-denominated
     bonds and deposits to be held, unremunerated, for a year -- a dated, numeric tax on carry
     that was set at 40%, cut to 20% and then to 0%. Three dated steps of a policy instrument
     almost no other country has ever published.

  6. THE GROUND MOVES. The Reykjanes peninsula has erupted repeatedly since 2021; the town of
     Grindavik was evacuated in November 2023 and the Svartsengi power plant sits inside the
     affected area. The met office publishes a seismic and aviation colour-code feed, and the
     2010 Eyjafjallajokull ash cloud is the measured precedent for European air freight.

WHAT IS EXECUTABLE AND WHAT IS NOT. THE KRONA IS NOT A BROKER SYMBOL. Neither is the OMXI15, the
Icelandic government bond curve, the CPI-indexed bond, the Landsvirkjun power contract, the fresh
fish auction price or North Atlantic container freight. Every one is named in
`TRANSMISSION_TARGETS` with the symbols its mechanism actually reaches -- XALUSD above all -- so
an absent instrument produces a transmission hypothesis and never a cell that can never be
filled (L1.49).

WHERE A LAYER DOES NOT EXIST, THIS PACK SAYS SO. A country of 390,000 people has no retail
margin-statistics ecology: no domestic CFD or margin broker publishes flow, no authority
publishes a retail-leverage series, and residents were legally barred from foreign securities
accounts for most of a decade. `LAYER_ABSENCES` declares that layer ABSENT with the reason. A
declared absence is a measurement; a padded row is not (L1.28a).

THE TWO-LANE ORDER (2026-09-06). Iceland's market commentary is four or five names -- the banks,
the fishing quota holders, the airline, the fish-processing equipment maker. Every one appears
here as an ACTOR only. No share CFD appears in any instrument tuple in this department.
"""
from __future__ import annotations

__all__ = ["pack"]
