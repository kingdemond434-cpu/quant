"""CZECHIA: the only central bank in Europe that ran a HARD FX FLOOR and then walked away from
it, and the only one that hedges its own reserves into equities.

WHY CZECHIA IS NOT A SMALLER POLAND AND NOT A GERMAN PROVINCE. Six things belong to this economy
and to no other on the desk's book, and each one is why a domain exists rather than a line in a
generic CEE domain:

  1. THE EUR/CZK FLOOR AT 27.00 IS THE CLEANEST REGIME BOUNDARY IN MODERN FX. The CNB announced
     it on 2013-11-07 as an unlimited one-sided commitment at the zero lower bound and abandoned
     it on 2017-04-06. Inside the floor the koruna's downside did not exist: the distribution is
     TRUNCATED, realised volatility is a policy choice, and every option, carry and momentum
     statistic estimated across that boundary is estimated on two different random variables
     glued together. The pack carries the two dates, the intervention volumes and what the era
     INVALIDATES, so a study that pools it says so out loud.
  2. THE COUNTERPARTY WAS KNOWN AND SO WAS THE TRADE. Between 2015 and 2017 the floor was the
     most crowded convergence trade in Europe: offshore accounts bought koruna at 27.00 knowing
     the CNB had to sell them EUR at that price, and the reserves rose from about 35% to over
     70% of GDP paying for it. The exit produced no gap and a slow grind -- which is itself the
     measurement, and the reason CZ-D is a POSITIONING domain and not a shock domain.
  3. THE RESERVES ARE HEDGED INTO EQUITIES. Having bought a balance sheet the size of the
     economy, the CNB put part of it into a global equity tranche and, from 2024, into a
     declared gold programme. A central bank whose reserve return depends on the world equity
     tape has an incentive function no textbook models, and its portfolio rebalancing is a real
     institutional flow into EUSTX50/GER40/US500 and XAUUSD.
  4. CZECH INDUSTRY IS A SUBCONTRACTED LIMB OF THE GERMAN AUTOMOTIVE CHAIN. Industry is about a
     third of gross value added and vehicles about a quarter of exports, with Germany taking
     roughly a third of the total. That reaches this desk as an INDEX transmission -- GER40 and
     EUSTX50, never Skoda and never Volkswagen -- because the two-lane order (2026-09-06)
     forbids hunting a single name statistically. Skoda, CEZ and Komercni banka are ACTORS here
     and appear in no instrument tuple in this pack.
  5. THE COUNTRY IS A NET POWER EXPORTER INSIDE A COUPLED MARKET. OTE runs the Czech day-ahead
     auction, coupled to the German, Austrian, Polish, Slovak and Hungarian zones through SDAC
     at a 12:00 CET gate; CEPS publishes the physical cross-border flows; the marginal Czech
     plant is lignite or gas. The gas leg is executable (XNGUSD) and the smelter leg is
     executable (XALUSD) -- power itself is not quoted here and is named as a transmission
     target rather than pretended into a symbol.
  6. THE HEDGER IS A CORPORATE, NOT A HOUSEHOLD. Czech mortgages are FIXED for three to five
     years, so a tightening cycle arrives at the household years late through a refixation wave;
     the FX exposure that matters is the exporter's forward book, which is sold into month-ends
     and was famously long koruna at the floor. That is a different transmission shape from
     Poland's WIBOR-floating household and from Hungary's converted FX loans.

WHAT IS EXECUTABLE AND WHAT IS NOT. EURCZK and USDCZK ARE quoted by this broker, which makes
Czechia one of the few packs on the desk whose own currency is directly tradable; the PX index,
Czech government bonds, PRIBOR, the CNB's 2W repo rate, the OTE day-ahead power price and the
EUA allowance are NOT, and each is named in `TRANSMISSION_TARGETS` with the broker symbols its
mechanism reaches. An absent instrument produces a transmission hypothesis here, never a cell
that can never be filled (L1.49).

THE TEN SOURCE LAYERS ARE ALL POPULATED AND NONE IS DECLARED ABSENT. Czechia is an open-data EU
member state with a digitised gazette, a public statistical database, a public time-series API
at the central bank and an active native-language retail ground -- so every layer has a real
root, and the honest measurement is that this country has no missing layer. The one genuine
physical absence is named inside the layer instead: Czechia is LANDLOCKED and has no port
authority, so the physical-economy layer is built on power, gas and rail rather than on berths.
"""
from __future__ import annotations

__all__ = ["pack"]
