"""Country pack `mn` -- MONGOLIA, held as data; see pack.py.

MONGOLIA SELLS ALMOST EVERYTHING IT DIGS TO EXACTLY ONE CUSTOMER, AND THAT IS WHAT MAKES IT
MEASURABLE. Roughly nine tenths of Mongolian exports cross one land border into China, the
Chinese customs administration publishes the MIRROR of that flow by origin every month, and the
two series can be differenced. Almost no other economy on this desk's book can be read twice,
from both sides of its own border, on a public monthly clock.

THREE MECHANISMS EARN THE PACK AND NONE OF THEM IS A COPY OF THE `cn` PACK'S.

  1. OYU TOLGOI'S UNDERGROUND BLOCK CAVE IS A PUBLISHED, DATED, MULTI-YEAR COPPER SUPPLY CURVE.
     Sustainable production began in 2023 and the operator's own guidance is an average of about
     500 kt of copper a year from 2028 to 2036 -- on the order of two per cent of world mine
     supply, arriving on a schedule that is reported QUARTERLY with grade and tonnage. A dated
     supply curve against a liquid contract is rarer than an edge: it is a mechanism whose
     timetable is public years in advance, and `oyu_tolgoi_ramp` holds it as arithmetic.

  2. THE COKING COAL BORDER IS COUNTED IN TRUCKS PER DAY, PUBLICLY, DAILY. Mongolia is China's
     largest supplier of imported coking coal, it arrives by road and rail through
     Gashuunsukhait-Ganqimaodu and Shiveekhuren-Ceke, and the throughput is published as a truck
     count. When that border shut in 2020-2022 Chinese coking coal prices moved measurably. The
     Tavantolgoi-Gashuunsukhait railway (2022 onward) is a DATED capacity step in the same
     series, which is exactly the control a throughput-versus-demand study needs.

  3. THE CALENDAR IS NOT CHINA'S. Tsagaan Sar follows the MONGOLIAN lunar calendar, which can
     differ from the Chinese one by a whole month -- 2024 fell on the same day and 2025 fell
     thirty-one days later. A desk that reuses a Chinese holiday table for Mongolia mislabels the
     largest closure of the Mongolian year, and `tsagaan_sar_gap` measures the offset rather
     than assuming it. Naadam (11-15 July) is fixed by statute and shuts the country for a week.

THE TUGRIK IS ABSENT from the broker registry and is carried in `TRANSMISSION_TARGETS` with its
managed-float regime, the Bank of Mongolia's FX auctions and swap line, and its routes into
USDCNH, USDRUB and XAUUSD. Coking coal and cashmere are not broker symbols either: both are
routed with their controls named, coal through the Chinese steel complex and the Australian
seaborne substitute (the `au` pack owns that leg), cashmere through the Chinese buyer.

NATIVE GROUND IS MONGOLIAN CYRILLIC, and the pack means it: mongolbank.mn, nso.mn,
customs.gov.mn, mrpam.gov.mn, legalinfo.mn, mse.mn and the Ulaanbaatar press are read in
Cyrillic or not at all. TRADITIONAL MONGOLIAN SCRIPT is a live crawling fact, not a curiosity:
official state documents carry it alongside Cyrillic from 2025, so a crawler that cannot see
U+1800..U+18AF will start missing the gazetted half of new documents.
"""
from __future__ import annotations

#: The submodule this department is. NOT imported here on purpose: `countries.load("mn")`
#: imports `countries.mn.pack` by name, and binding the module's own `pack()` FUNCTION onto this
#: package would shadow the module for every `from countries.mn import pack` in the tests.
__all__ = ["pack"]
