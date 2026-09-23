"""THE MAGHREB ENERGY AND MINERALS PLANE -- Algeria, Libya, Tunisia and Mauritania.

`pack.py` is the whole department as data, and it exists as the COMPLEMENT of `ma` rather than as
a bigger copy of it: Morocco imports energy and these four export it. Algeria is the European
Union's third-largest pipeline gas supplier and became Italy's largest after 2022, and the flow
is PUBLISHED DAILY by the receiving TSOs -- Transmed at Mazara del Vallo in Snam's entry table,
Medgaz at Almeria in Enagas's. Libya is the most volatile OPEC producer on earth and its outages
are DATED, NAMED AND PUBLISHED by terminal, which makes them as close to an instrument for an oil
supply shock as this market offers. Tunisia is the transit state that takes an in-kind royalty on
Italy's Algerian gas, a top-three olive-oil producer on a dated campaign, a world-scale phosphate
producer halted by dated labour actions, and a live sovereign-stress case with published decision
points. Mauritania is iron ore on the longest train in the world, an Atlantic fishery licensed to
EU and Chinese fleets, and the Mauritanian half of Greater Tortue Ahmeyim -- a gas field it
SHARES WITH SENEGAL, which makes this pack and `west_africa` one physical system.

THE FOUR JURISDICTIONS ARE DECLARED, not inferred. `pack.JURISDICTIONS` is ("dz", "ly", "tn",
"mr") and that tuple is what `check_regional_parity.jurisdictions_of` counts -- a multi-country
pack that declares nothing is credited with ONE country, which would leave three of the parity
fence's gaps unanswered while the work sat on disk.

NOTHING LOCAL IS EXECUTABLE. DZD, LYD, TND and MRU are all absent from the broker registry, and
so are the European gas hubs this pack is really about: TTF, PSV and PVB are not Fusion symbols.
Every one is named in `TRANSMISSION_TARGETS` with its regime and its carriers. HENRY HUB IS
REGISTERED AS A CONTROL AND NOT A PROXY: the two benchmarks decoupled by an order of magnitude in
2022, and a study that substituted one for the other measured the LNG arbitrage and reported a
European supply shock.

ACCESS AND LAWFULNESS. Libya has two competing administrations and Libyan entities have been
subject to UN and national measures. NOTHING HERE TOUCHES ANY ENTITY'S PRIVATE SYSTEMS AND
NOTHING BYPASSES AN ACCESS CONTROL: every source is public -- NOC and Sonatrach announcements,
OPEC's MOMR, IEA and EIA releases, the Italian and Spanish TSOs' published flows, ENTSOG
transparency, national statistics and central-bank publications, UN Panel of Experts reports and
the public press. The desk executes only broker symbols and never a Maghreb instrument. Sonatrach,
the NOC, CPG, SNIM and ETAP are ACTORS and TERMINOLOGY only -- the two-lane order (2026-09-06)
forbids putting a single name on a docket -- and no crypto-exchange ground is hunted anywhere
(mandate 2026-08-18).

Nothing in this package is imported at package-import time: `pack()` costs something to build and
the scheduler asks for it by name.
"""
from __future__ import annotations

__all__ = ["pack"]
