"""DENMARK: the hardest peg on the book, defended by a RATE SPREAD and by INTERVENTION.

WHY DENMARK IS NOT A SMALLER SWEDEN AND NOT A EURO MEMBER WITH A DIFFERENT FLAG. Six things
belong to this economy and to no other in the desk's book, and each one is why a domain in
`pack.py` exists rather than a row inside a generic European domain:

  1. EURDKK IS A HARD PEG INSIDE ERM II AT 7.46038 WITH A FORMAL +/-2.25% BAND, and Denmark is
     the ONLY member of ERM II. The band is a treaty number, not a preference, and the pack
     carries it as a FUNCTION (`band_edges`, `band_position`) so the distance to the edge is a
     computed state rather than a story. Denmark has never used more than a small fraction of
     that band: the operating band the Nationalbank actually defends is roughly +/-0.35% around
     the central rate, and that gap between the LEGAL band and the OPERATED band is itself the
     mechanism -- it is what makes EURDKK the lowest-realised-volatility pair the broker quotes.

  2. THE DEFENCE IS AN INDEPENDENT POLICY RATE AND AN INTERVENTION BOOK, NOT AN ECB FOLLOW.
     Danmarks Nationalbank has exactly one objective -- the fixed rate -- and it runs its own
     policy rate against the ECB's to get it. In October 2008 it RAISED while the ECB CUT. In
     January 2015 it cut four times in eleven days to -0.75%, and the Ministry of Finance, on
     the bank's recommendation, SUSPENDED ALL GOVERNMENT BOND ISSUANCE so that foreign buyers
     had nothing to buy. Through the 2022-23 ECB hiking cycle it repeatedly raised by LESS than
     the ECB. The DN-minus-ECB spread is therefore a published, dated, two-sided policy series
     that exists for no other currency on this desk, and the intervention statistics are
     published monthly beside it.

  3. TWO MECHANISMS LIVE IN THE SAME SYMBOL AND THEY ARE OPPOSITES. Because spot cannot move,
     EURDKK carries (a) a micro-band MEAN REVERSION that exists nowhere else on the book, and
     (b) a CARRY/SPREAD mechanism which, in a regime where spot variance is near zero, DOMINATES
     the spot mechanism in every risk-adjusted sense. The pack says both, mints cells for both,
     and refuses to let a spot study quietly be a carry study.

  4. THE MORTGAGE MARKET IS THE RATES MARKET. Danish realkredit is the world's oldest covered
     bond system (1795 onward) and one of the largest relative to GDP anywhere; the balance
     principle makes every loan a pass-through of a listed bond, the callable 30-year at par
     gives every borrower a free prepayment option, and the adjustable-rate loans are refinanced
     at AUCTIONS on a published clock in late February, late May, late August and late November.
     Those four windows are a domestic rates event with a date, and the November one -- which
     refixes the January reset -- is the largest single funding event in the Danish year.

  5. THE PENSION SECTOR IS BIGGER THAN THE ECONOMY AND IT HEDGES IN EUR AND USD. Danish
     labour-market pensions run assets far above GDP with liabilities discounted on a euro
     curve, so their hedge ratios and their quarter-end rebalancing are a real, dated FX flow
     into EURUSD and into the krone's own book.

  6. THE PHYSICAL ECONOMY IS READABLE AND UNUSUAL. Maersk moves a measurable share of world
     container capacity; Energinet publishes wind generation and DK1/DK2 power prices on a free
     API at high frequency; the Tyra field was shut in September 2019 and returned in March 2024,
     flipping Denmark from a gas exporter to an importer and back on two dated days; and the
     Danish pig chain prices itself weekly and sells into China.

WHAT IS EXECUTABLE AND WHAT IS NOT. The OMXC25, the Danish government curve, the realkredit
bonds themselves, CITA/CIBOR, the DK1/DK2 power price and the TTF gas benchmark are all ABSENT
from the broker registry. Every one of them is named in `TRANSMISSION_TARGETS` with the symbols
its mechanism actually reaches, so an absent instrument produces a transmission hypothesis and
never a cell that can never be filled (L1.49).

THE TWO-LANE ORDER (2026-09-06). Danish market commentary is dominated by four names -- Novo
Nordisk, A.P. Møller-Maersk, Ørsted, Danske Bank -- and every one of them is an EVENT-lane
instrument. They appear in this pack as ACTORS and as index-composition facts only. No share CFD
appears in any instrument tuple in this department.
"""

from __future__ import annotations

__all__ = ["pack"]
