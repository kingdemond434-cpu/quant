"""THE CARIBBEAN: six island economies, one weather system, six different currency regimes.

WHAT THIS DEPARTMENT IS FOR, IN ONE SCREEN. The Dominican Republic, Jamaica, Cuba, Haiti,
Barbados and the Bahamas share one sea, one hurricane season, one freight constraint and one
tourism source market -- and they answer it with six MONETARY REGIMES that could not be further
apart: a managed float with a published intervention book (DOP), a free float run by one of the
first small-open-economy central banks to hike in 2021 (JMD), a state currency that was
redenominated OVERNIGHT on 2021-01-01 and now trades at an order-of-magnitude informal premium
(CUP), a collapsing float whose statistical institute has largely stopped publishing (HTG), and
TWO HARD USD PEGS that have never broken (BBD 2:1 since 1975, BSD 1:1). One shock, six regimes,
six published reaction functions: that is an identification strategy, and it is the only reason
these six belong in one pack rather than six thin ones.

THE THREE PHYSICAL FACTS THAT REACH A BROKER SYMBOL. Jamaica is a top-ten BAUXITE and ALUMINA
producer and the broker quotes XALUSD; the Jamaica Bauxite Institute publishes production monthly
and the refineries have been interrupted by dated, published events -- the Jamalco powerhouse fire
of 2021-08-22 took a refinery offline for more than a year. The Dominican Republic hosts PUEBLO
VIEJO, one of the largest gold mines in the world, whose output is published in Barrick's filings
and in Dominican export statistics, against XAUUSD. Cuba is a top-ten NICKEL producer at Moa, and
because Cuban statistics are thin the LAWFUL WINDOW is Sherritt International's public quarterly
reporting, against XNIUSD. Three metals, three published production counts, three broker symbols.

BE HONEST ABOUT THE SIZE OF THE EDGE. This is a SMALLER-EDGE region than the copper and oil packs
and the pack says so in writing. Jamaican alumina moves the ALUMINA assessment first and the
exchange ALUMINIUM price only partially; Cuban sugar is now a rounding error in a world balance it
once dominated; Haitian rice demand is real and reaches the desk only through a MIRROR statistic
on a grain the broker does not quote. Every one of those weaknesses is declared on the edge that
carries it, because a pack that overclaims spends the desk's shared trial budget on nothing.

WHAT IS ABSENT, AND IT IS THE PACK'S MOST VALUABLE OUTPUT. Not one of the six currencies is quoted
by this broker. Cuba publishes NO market exchange rate and has NO securities market. Haiti's
statistical institute has largely stopped. None of the six has a domestic retail margin-trading
ecology. Each of those is declared BY JURISDICTION AND BY LAYER in `NO_LAWFUL_GROUND` with the
LAWFUL SUBSTITUTE named beside it -- the Sherritt and Barrick filings, the USDA FAS and US Census
mirror statistics, the IMF Article IV record, ECLAC and CARICOM, the NOAA and NHC archives.

ACCESS AND LAWFULNESS. Cuba is under a long-standing US embargo. NOTHING in this pack touches any
entity's private systems and nothing bypasses an access control. Sanctions constrain TRANSACTIONS,
not the reading of published statistics, and the desk executes only broker symbols -- never a
Caribbean instrument.

NATIVE GROUND: SPANISH (the DR and Cuba), ENGLISH and JAMAICAN PATOIS (Jamaica, Barbados, the
Bahamas), and HAITIAN CREOLE plus French (Haiti). Creole is the language about 95% of Haitians
actually read; a French-only crawl of Haiti reads the elite and reports it as the country. The
Jamaican informal savings ecology -- "partner", the "box hand" -- is discussed in Patois and in
nothing else, and it is the retail ecology that actually exists there.

Data only; the mechanisms, tables and miners are in `pack.py`.
"""
#: The submodule that carries everything. Left as a SUBMODULE rather than re-exported as a name,
#: because `from .pack import pack` would shadow the module `countries.caribbean.pack` with the
#: function `pack()` and break every importer that reads the pack as a module (the tests,
#: `resolve_pack`, `load_custom_miners`).
__all__ = ["pack"]
