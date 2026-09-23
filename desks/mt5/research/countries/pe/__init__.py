"""PERU: the world's second copper and second silver mine, read through its CONFLICT CALENDAR.

WHAT THIS DEPARTMENT IS FOR, IN ONE SCREEN. Peru is the #2 copper producer on earth (~2.6 Mt/yr),
the #2 silver producer, a top-ten gold producer, the largest zinc producer in the Americas and a
top-three lead producer -- and this broker quotes XCUUSD, XAGUSD, XAUUSD, XZNUSD and XPBUSD
directly. No other country on this desk lines its physical production series up with tradable
instruments five metals deep, which is why this pack's cell count is high and honest at once.

THE MECHANISM NOBODY ELSE MINES. The Defensoria del Pueblo -- a constitutionally independent
ombudsman -- publishes a MONTHLY report naming every active social conflict in the country by
case, province, actor and state. The socio-environmental mining subset of that report is a
PHYSICAL SUPPLY SERIES on a liquid metal: Las Bambas alone ships about 2% of world copper down
one road, the Corredor Vial Minero del Sur, and that road has been blocked for weeks at a time
with dated starts and dated ends. A published, lawful, dated supply-interruption series that
essentially no systematic desk reads is the single best reason this department exists.

WHAT ELSE BELONGS TO THIS ECONOMY. MINEM publishes production BY MINE AND BY METAL every month,
not a national total. The BCRP publishes its own daily FX intervention -- the amount, by day --
plus the CDR and swap cambiario books it uses instead of spot, which makes the sol's famously low
volatility a POLICY OUTPUT and therefore the cleanest control this desk has for "does political
risk move a currency". The politics are a dated event series rather than a mood: six presidents
since 2016 and a self-coup that began about 11:40 Lima on 2022-12-07 and ended in an arrest the
same afternoon. And the anchoveta -- the world's largest single-species fishery, quota-managed by
resolucion ministerial and CANCELLED outright in 2023 -- is a genuine input to the soymeal ration.

WHAT IS ABSENT. The SOL IS NOT QUOTED here, and neither is USDCLP, the BVL index, the soberanos
curve, the LME cash contracts or the fishmeal FOB assessment. Every one is named in the pack's
`TRANSMISSION_TARGETS` with the broker symbols that carry its economics, so an absent instrument
becomes a transmission hypothesis and never a cell that can never be filled (L1.49).

THE `cl` PACK IS THE NEAREST NEIGHBOUR AND THE SHARPEST CONTROL, NEVER A DUPLICATE. `countries/cl`
is written as "Chile (with Peru)" and owns the Chilean union calendar, the AFP multifondo switch
and the pre-announced BCCh intervention programme. This pack owns the conflict calendar, the
mine-level production count and the CDR/swap book. Chile's supply risk is a LABOUR NEGOTIATION on
a published cycle; Peru's is a ROAD closed by a community assembly. Each is the other's negative
control, and `INTERACTIONS` names that edge first and explicitly.

THE TWO-LANE ORDER (2026-09-06) IS ENFORCED HERE. Southern Copper, Buenaventura, Credicorp,
Volcan, Nexa, Exalmar and TASA are ACTORS in this pack and never instruments. No share CFD appears
in any instrument tuple.

NATIVE GROUND: Spanish, QUECHUA and AYMARA. The last two are official languages under article 48
of the constitution wherever they predominate -- which is exactly where the mines are. The
community assembly that votes a blockade sits in Quechua, the prior-consultation record under Ley
29785 is kept in it, and Servindi and the regional radios report it in it. A Spanish-only crawl
of Peruvian conflict reads the reaction and never the decision.

Data only; the mechanisms, tables and miners are in `pack.py`.
"""
#: The submodule that carries everything. Left as a SUBMODULE rather than
#: re-exported as a name, because `from .pack import pack` would shadow the module
#: `countries.pe.pack` with the function `pack()` and break every importer that
#: reads the pack as a module (the tests, `resolve_pack`, `load_custom_miners`).
__all__ = ["pack"]
