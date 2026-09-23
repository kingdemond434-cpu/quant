"""BLACK SEA -- Ukraine (`ua`) and Belarus (`by`) as one grain-and-fertiliser plane.

TWO JURISDICTIONS, ONE PHYSICAL MECHANISM, AND THAT IS WHY THEY SHARE A PACK. Ukraine was about
a tenth of world wheat exports, a sixth of corn and roughly 45% of the world's sunflower oil;
Belarus is about a fifth of world potash. One supplies the grain and the other supplies the
nutrient the next crop is grown with -- and between 2020 and 2025 BOTH were re-routed by dated,
published, lawful-to-read interventions. The corridor that closed Odesa and the transit ban that
closed Klaipeda are the same kind of object: an administered change to a physical route, with a
signature date, against a liquid futures complex. Writing them as two packs would test the same
freight shock twice and never test it against itself.

WHAT THIS PACK ADDS THAT ITS SIBLINGS DO NOT. `ru` owns the budget rule, the tax date and the
Urals discount; `kz` owns the CPC/Tengiz route and the tenge; `pl` owns the NBP and the zloty;
`tr` owns the Turkish reaction function; `cee_balkans` owns the Danube's lower reach and the
Constanta export pace. NONE of them owns the Black Sea Grain Initiative's vessel table, the
Ukrainian maritime corridor, the hryvnia's three wartime eras, the potash route through
Lithuania, or the published Belarusian currency basket. Those are this pack's ground, and
`INTERACTIONS` names the seams where they meet the siblings so the desk stops testing each
country in isolation.

LAWFULNESS. Both jurisdictions sit under sanctions regimes. NOTHING here touches a sanctioned
entity's private systems and nothing bypasses an access control. Everything is PUBLIC official
statistics, PUBLIC international-organisation data (FAO AMIS, UN Comtrade, IGC, USDA FAS GAIN,
the UN's own published BSGI vessel and inspection table) and PUBLIC press. Sanctions constrain
TRANSACTIONS, not the reading of published statistics -- and the desk executes broker symbols
only, never a Ukrainian or Belarusian instrument. `ACCESS_CONSTRAINTS` in `pack.py` says it in
the pack's own data, where a miner can read it.
"""
from __future__ import annotations

#: `pack()` lives in `pack.py` and is NOT re-exported here on purpose: re-exporting it would
#: shadow the `pack` SUBMODULE for every `from countries.black_sea import pack` in the tests and
#: in the miners, which is the one import this department actually does.
__all__ = ["pack"]
