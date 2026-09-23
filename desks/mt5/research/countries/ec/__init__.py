"""ECUADOR: the cleanest dollarised shock-absorber on earth, read through oil, power and shrimp.

WHY THIS DEPARTMENT EXISTS AND WHY IT IS NOT A PARAGRAPH IN `pe` OR `co`. Ecuador has had NO
DOMESTIC CURRENCY SINCE 9 JANUARY 2000. It uses the United States dollar. There is no exchange
rate, no policy rate, no open-market operation and NO LENDER OF LAST RESORT: the Banco Central
del Ecuador is a clearing house and a reserve custodian, not a monetary authority. Every external
shock that Peru's BCRP absorbs in the sol and Colombia's BanRep absorbs in the peso must, in
Ecuador, be absorbed by the REAL ECONOMY and the FISCAL BALANCE, because there is nothing else to
absorb it. `pe` and `co` float; this one cannot. That is a natural experiment the desk owns three
packs' worth of controls for, and it is the whole thesis of this department.

WHAT IT SHIPS, AND ALL OF IT LANDS ON A BROKER SYMBOL. An OPEC member until 1 January 2020,
exporting Oriente and Napo heavy sour crude down two pipelines that the Coca river keeps cutting.
The world's largest exporter of farmed SHRIMP and of BANANAS, and a top-three CACAO exporter whose
fino de aroma share grew as West Africa failed. Mirador (copper, Chinese-owned, first concentrate
2019) and Fruta del Norte (gold, 2019) put the country on XCUUSD and XAUUSD. XBRUSD, XTIUSD,
XNGUSD, XAUUSD, XCUUSD, UKCOCOA, USCOCOA, SUGAR, COFARA, CORN, SOYBEAN, USDCNH, USDBRL, USDMXN and
US500 are every one of them in the broker's registry.

THE FOUR MECHANISMS NOBODY ELSE ON THIS DESK CARRIES.

  1. A SOVEREIGN ELECTORATE VOTED A FIELD SHUT. On 20 August 2023, on a published ballot counted
     by the Consejo Nacional Electoral, Ecuadorians voted to leave the ITT crude of Block 43 in
     the ground -- roughly 50 kb/d, with a dated one-year compliance deadline. No other country
     in this book has a referendum that closes an oil field.
  2. THE PIPELINES ARE CUT BY A RIVER, ON DATES. The San Rafael waterfall collapsed on 2 February
     2020 and the Coca river has been eating its bed backwards ever since. SOTE and OCP have been
     ruptured or pre-emptively shut repeatedly, each time with a published force-majeure
     declaration -- a physical, dated, lawful supply interruption of a liquid crude.
  3. A PUBLISHED NATIONAL POWER-RATIONING SCHEDULE. Drought at Coca Codo Sinclair and Mazar forced
     CENACE-published rationing tables in 2023 and again through late 2024, up to fourteen hours a
     day. A quantified, dated, scheduled loss of industrial load on a dollarised economy.
  4. FULL DOLLARISATION WITH NO MONETARY CHANNEL. The pack says this plainly: THERE IS NO
     CURRENCY TO ROUTE. The transmission is entirely fiscal and real -- the subsidy bill, the
     sovereign spread, the import cover, the deposit base -- and that is the thing being tested.

WHAT IS ABSENT. There is no Ecuadorian currency, no policy rate, no domestic FX market, no retail
leverage ecology and no sovereign CDS this broker quotes. Each is named in `TRANSMISSION_TARGETS`
or in `LAYER_ABSENCES` with the reason and the carrier, so an absence is a measurement and never a
cell that can never be filled (L1.49).

THE TWO-LANE ORDER (2026-09-06) IS ENFORCED HERE. Petroecuador, OCP, CELEC, Banco Pichincha,
Favorita, Lundin and EcuaCorriente are ACTORS in this pack and never instruments. No share CFD
appears in any instrument tuple.

NATIVE GROUND: Spanish, KICHWA and SHUAR. The last two are official for intercultural use under
article 2 of the 2008 constitution. The Amazonian bloc consultations, the CONAIE paro calendars
that shut the wellheads and the community assemblies that decide them are conducted and reported
in them. A Spanish-only crawl of Ecuador reads Quito and misses the Oriente.

Data only; the mechanisms, tables and miners are in `pack.py`.
"""
#: The submodule that carries everything. Left as a SUBMODULE rather than re-exported as a name,
#: because `from .pack import pack` would shadow the module `countries.ec.pack` with the function
#: `pack()` and break every importer that reads the pack as a module.
__all__ = ["pack"]
