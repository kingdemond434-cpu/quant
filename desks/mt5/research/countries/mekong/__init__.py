"""Country pack `mekong` -- MYANMAR, CAMBODIA AND LAOS, held as data; see pack.py.

THREE ECONOMIES THAT ARE PHYSICAL EXTENSIONS OF THEIR NEIGHBOURS, WHICH IS WHAT MAKES THEM A
LEADING INDICATOR RATHER THAN NOISE. Myanmar's offshore gas is burned in Thai power stations.
Laos's rivers are turned into electricity under long-term contracts with the Thai, Vietnamese and
Cambodian grids. Cambodia's factories cut cloth for buyers whose orders are placed in Europe and
the United States and whose inputs come from China and Vietnam. None of the three is large; all
three sit UPSTREAM of something large, and upstream is where a shock is dated first.

WHAT EARNS THE PACK, one mechanism per jurisdiction and none of them a copy of `th` or `vn`:

  * MYANMAR. The Yadana and Zawtika fields supply a material share of the gas Thailand burns for
    power, through published cross-border pipelines with published maintenance shutdowns -- a
    genuine, dated, physical input into Thai electricity and therefore into the Thai industrial
    cycle. And Kachin State is the source of most of the world's HEAVY rare-earth feedstock
    (dysprosium and terbium), shipped to China and counted in CHINESE CUSTOMS DATA BY ORIGIN, so
    the 2024-2025 capture of the Chipwi and Pangwa mining zone and the border closure that
    followed is a dated, published disruption to a supply chain with no substitute.
  * CAMBODIA. A FULLY DOLLARISED ECONOMY WITH A RIEL THAT EXISTS MAINLY AS SMALL CHANGE. The
    National Bank publishes its riel-promotion operations and the dollarisation share, which
    makes Cambodia a clean natural experiment on what a floating currency actually buys a small
    open economy -- with Laos and Vietnam, its neighbours, as the two controls.
  * LAOS. The battery of Southeast Asia, whose output is bounded by Mekong reservoir levels that
    the Mekong River Commission publishes DAILY BY STATION, and simultaneously the most
    debt-distressed economy in the region: a kip that lost more than half its value in 2022-2023
    and published inflation above forty per cent.

NONE OF THE THREE CURRENCIES IS QUOTED BY THIS BROKER. MMK, KHR and LAK are all carried in
`TRANSMISSION_TARGETS` with their regimes, their parallel-market spreads and their routes into
USDTHB, USDCNH, USDSGD and the commodity complex. Rare earths, hydroelectricity, garments, jade
and milled rice have no broker contract either, and each is routed with its control named.

THREE SCRIPTS, AND AN ENGLISH-ONLY CRAWL READS NONE OF THEM: Burmese, Khmer and Lao. The pack
carries terminology and query territories in all three, plus the Thai and Chinese MIRROR
vocabulary, because for two of these three countries the buyer's statistics are better than the
seller's.

AND WHERE A LAYER GENUINELY DOES NOT EXIST, THE PACK SAYS SO AND NAMES THE SUBSTITUTE. Myanmar's
official statistics have largely stopped publishing since 2021 and its exchange has effectively
no tape; Laos has no domestic academic economics ground; none of the three has a retail trading
ecology. Each gap is declared per jurisdiction in `NO_LAWFUL_GROUND` with the lawful substitute
beside it -- mirror customs, the Mekong River Commission, the ADB and IMF, the exile press.
"""
from __future__ import annotations

#: The submodule this department is. NOT imported here on purpose: `countries.load("mekong")`
#: imports `countries.mekong.pack` by name, and binding the module's own `pack()` FUNCTION onto
#: this package would shadow the module for every `from countries.mekong import pack`.
__all__ = ["pack"]
