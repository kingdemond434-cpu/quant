"""HUNGARY: six broker-quoted crosses on one currency, a two-rate emergency regime that breaks
any study pooling across it, and a political conditionality switch with a dated FX reaction.

WHY HUNGARY EARNS ITS OWN DEPARTMENT, AND WHY IT IS NOT A LOUDER CZECHIA. Six things belong to
this economy and to no other on the desk's book:

  1. THE DESK QUOTES SIX HUF CROSSES -- EURHUF, USDHUF, AUDHUF, CHFHUF, GBPHUF and NZDHUF. That
     is the widest exotic cross set this broker offers for any single country, and it is the
     reason this pack matters out of proportion to Hungary's size: six simultaneous observations
     of ONE currency against six different funding legs let a study DECOMPOSE a move into the
     HUF common factor and the cross-specific residual, which no single-cross pack can do. A
     shock that shows up in all six is Hungary; a shock that shows up in CHFHUF alone is
     Switzerland; a shock in AUDHUF and NZDHUF alone is the carry complex.
  2. THE ONE-DAY DEPOSIT RATE WAS A SECOND POLICY RATE, AND IT REACHED 18%. From 2022-10-14 the
     MNB ran an overnight deposit quick tender far above its own 13% base rate, so for eleven
     months "the Hungarian policy rate" was two different numbers depending on which one you
     meant. The instruments converged back to the base rate in September 2023. ANY study that
     pools a policy-rate series across that window is pooling two regimes, and any carry
     calculation that used the base rate underestimated the real funding cost by up to five
     percentage points.
  3. THE EU FUNDS SWITCH IS A DATED POLITICAL EVENT WITH A MEASURABLE FX REACTION. The
     conditionality mechanism was triggered against Hungary, cohesion money was suspended by a
     Council decision, and tranches were released later in exchange for legislative milestones.
     These are published decisions on published dates, with a large forced EUR-to-HUF
     conversion behind each one and a political discount priced into the forint between them.
     Czechia, which faced none of it, is the clean control.
  4. THE 2015 FOREX-LOAN CONVERSION PERMANENTLY REMOVED A CHANNEL FROM THE FORINT'S BETA. Until
     forintositas, Hungarian households owed hundreds of billions of forints in CHF-denominated
     mortgages, so a CHF rally fed straight back into domestic balance sheets and into the
     forint itself. The conversion at administratively fixed rates, funded out of MNB reserves,
     cut that loop. CHFHUF before 2015 and CHFHUF after 2015 are not the same relationship, and
     this pack carries the boundary rather than averaging across it.
  5. THE ENERGY POSITION IS A POLICY POSITION. Hungary kept a pipeline-crude exemption from the
     EU's Russian oil ban, so its refining margin has carried a discount other European refiners
     do not get; the household utility price cap has been a fiscal and inflation instrument
     since 2013 and was narrowed in 2022; and Paks II is a decade-long, state-financed nuclear
     decision that shapes the gas call. Each reaches this desk through XBRUSD and XNGUSD.
  6. THE CALENDAR ITSELF IS MOVED BY DECREE. Hungary REARRANGES working days around public
     holidays: a minister's decree turns a Monday or Friday into a rest day and a nearby
     Saturday into a working day. The statutory holidays are computable from the Labour Code and
     Easter; the swaps are NOT, they are declared each year, and this pack carries them as a
     dated table with its status rather than pretending a rule exists.

WHAT IS EXECUTABLE AND WHAT IS NOT. The six HUF crosses are all quoted here, which makes almost
every Hungarian mechanism a fillable cell. The BUX index, Hungarian government bonds, BUBOR, the
MNB's own instruments, the retail MAP Plusz programme and the HUDEX power and gas contracts are
NOT quoted, and every one is named in `TRANSMISSION_TARGETS` with the broker symbols its
mechanism reaches.

THE TWO-LANE ORDER (2026-09-06). Hungarian market commentary is dominated by four names -- OTP,
MOL, Richter and Magyar Telekom are most of the BUX -- and every one of them is an EVENT-lane
instrument. They enter this pack only as ACTORS, and no share CFD appears in any instrument
tuple in this file.

ALL TEN SOURCE LAYERS ARE POPULATED AND NONE IS DECLARED ABSENT. Hungary publishes a digitised
gazette (Magyar Kozlony), a public central-bank time-series library, an open statistical
database and an active native-language retail and practitioner ground. The honest measurement
here is that no layer is missing.
"""
from __future__ import annotations

__all__ = ["pack"]
