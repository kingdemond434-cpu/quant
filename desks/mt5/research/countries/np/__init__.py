"""Country pack `np` -- NEPAL, held as data; see pack.py.

Nepal earns a pack for one reason that no other South Asian economy can offer: the NEPALESE
RUPEE IS PEGGED TO THE INDIAN RUPEE AT EXACTLY 1.60 NPR = 1 INR AND HAS BEEN SINCE 1993. That is
a hard, published, unbroken cross-rate, which means every USDINR move passes through to the NPR
ONE FOR ONE and Nepal's entire external position is an amplified function of India's. The broker
quotes USDINR. So Nepal's own published external data -- import cover, the NRB's reserve
position, and monthly remittance inflows by source country -- is a LAWFUL, PUBLISHED, THIRD-PARTY
READ on Indian external conditions that nobody triangulates. That is the pack's primary
transmission edge and the reason it exists.

Around it: remittances at roughly a quarter of GDP, published monthly by source country, which
read directly on Gulf, Malaysian and Korean labour demand; the dated 2022 luxury-import ban that
was a real, published capital control with a measurable effect; hydropower exports to India under
the 2024 long-term power trade agreement and their monsoon seasonality; the fortnightly
IOC-to-NOC petroleum price revision that turns XBRUSD into an administered domestic price on a
published clock; and cardamom, tea and the trans-Himalayan trade.

NPR is absent from the broker and is carried in `TRANSMISSION_TARGETS` with the 1.6 peg and its
route through USDINR.

Nepal's calendar is BIKRAM SAMBAT, about 56.7 years ahead of the Gregorian, and its fiscal year
runs 1 Shrawan to the end of Ashad -- mid-July to mid-July. Dashain and Tihar are lunar, move by
weeks, and shut the whole economy for up to a fortnight in September or October; they cannot be
computed from a weekday rule and are typed with the Nepal Calendar Determination Committee named
as the authority. THE WEEKEND IS SATURDAY ONLY -- a one-day national weekend, with NEPSE trading
Sunday to Thursday -- which is a real and distinctive market-calendar fact and is in the rule.
"""
from __future__ import annotations

#: The submodule this department is. NOT imported here on purpose: `countries.load("np")`
#: imports `countries.np.pack` by name, and binding the module's own `pack()` FUNCTION onto this
#: package would shadow the module for every `from countries.np import pack` in the tests.
__all__ = ["pack"]
