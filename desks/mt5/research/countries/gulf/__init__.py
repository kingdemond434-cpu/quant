"""THE FOUR SMALLER GULF STATES -- Qatar, Kuwait, Oman and Bahrain, as four different machines.

`pack.py` is the whole department as data, and it exists as the COMPLEMENT of `sa` and `ae`
rather than as a smaller copy of either. Saudi Arabia is the marginal barrel and a weekly
point-of-sale print; the Emirates are the region's dollar funding and its trade throughput. What
lives here is what belongs to neither: Qatar's DATED North Field capacity schedule (77 -> 110 ->
126 -> 142 mtpa) and the shift of its long-term SPAs from Brent slopes toward hub indexation;
Kuwait's dinar, the ONLY Gulf currency pegged to an undisclosed basket rather than to the dollar,
and the fiscal law -- 10% of revenue to the Future Generations Fund, no debt law, a General
Reserve Fund that must sell -- that makes the state a legally forced seller of global assets;
Oman's membership of OPEC+ WITHOUT membership of OPEC, its DME Oman marker as the Asian sour
benchmark, and the only major Gulf loading points OUTSIDE the Strait of Hormuz; and Bahrain's
0.376 peg, the clearest "peg with an external guarantee" case in the world, with BHIBOR as the
region's cheapest public stress gauge.

THE FOUR JURISDICTIONS ARE DECLARED, not inferred. `pack.JURISDICTIONS` is ("qa", "kw", "om",
"bh") and that tuple is what `check_regional_parity.jurisdictions_of` counts -- a multi-country
pack that declares nothing is credited with ONE country, which would leave three of the parity
fence's twenty-six unanswered while the work sat on disk.

NONE OF THE FOUR CURRENCIES IS QUOTED BY THIS BROKER. QAR, KWD, OMR and BHD are all named in
`TRANSMISSION_TARGETS` with their peg parameters, and every mechanism terminates in gas, crude,
gold, the dollar legs, the Asian buyers' currencies, the Treasury tenors or the risk indices.
QatarEnergy, KPC, OQ, Bapco, Nakilat and the listed Gulf banks are ACTORS and TERMINOLOGY only --
the two-lane order (2026-09-06) forbids putting a single name on a docket. No crypto-exchange
ground is hunted anywhere here (mandate 2026-08-18), which is worth saying twice in a Gulf pack
because Bahrain licenses crypto venues and the temptation is local.

Nothing in this package is imported at package-import time: `pack()` costs something to build and
the scheduler asks for it by name.
"""
from __future__ import annotations

__all__ = ["pack"]
