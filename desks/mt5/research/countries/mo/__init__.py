"""Country pack `mo` -- MACAU, held as data; see pack.py.

Macau is on this desk's book for one reason that no other jurisdiction of its size can offer:
the DICJ publishes MONTHLY GROSS GAMING REVENUE ON THE FIRST WORKING DAY OF THE FOLLOWING
MONTH, unrevised, on a fixed clock. That is a zero-lag, never-revised, monthly read on mainland
Chinese discretionary consumption and on cross-border capital movement, and between 2014 and
2016 it was the best-known public proxy for the intensity of the mainland anti-corruption
campaign anywhere in the world. Everything else in this pack sits around that series.

The pataca is a PEG ON A PEG: MOP 1.03 = HKD 1.00 at the note-issuing banks, and the Hong Kong
dollar is itself held inside the HKMA's 7.75/7.85 convertibility band. A Macau shock therefore
reaches the dollar only through the Hong Kong band, and the `hk` pack owns that band -- so this
pack names the chain and never re-derives it. MOP is absent from the broker and is carried in
`TRANSMISSION_TARGETS`; the executable leg is HK50, CHINAH, USDHKD and the China risk complex.

The gaming operators are single names listed in Hong Kong and New York. Under the two-lane order
(2026-09-06) they are EVENT LANE ONLY: they appear here as actors and observables and never as an
executable instrument, a domain instrument or an edge target.

Macau's calendar is the pack's distinguishing fact. It carries BOTH the Chinese lunar festivals
(Lunar New Year, Ching Ming, Tuen Ng, the day after Mid-Autumn, Chung Yeung, the Winter Solstice)
which no weekday rule computes, AND the Catholic/Portuguese dates (Good Friday, the day before
Easter, All Souls', the Immaculate Conception) which ARE computable from Easter. Portuguese is
co-official and the Boletim Oficial is bilingual, so a Chinese-only crawl of Macau misses the
whole legal layer.
"""
from __future__ import annotations

__all__ = ["pack"]

from .pack import pack
