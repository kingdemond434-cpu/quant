"""Country pack `maritime_asia` -- BRUNEI, TIMOR-LESTE, THE MALDIVES, BHUTAN, AFGHANISTAN.

THESE FIVE HAVE NOTHING IN COMMON GEOGRAPHICALLY AND THE PACK DOES NOT PRETEND THEY DO. A
sultanate on Borneo, a half-island in the Banda Sea, an atoll chain on the equator, a Himalayan
kingdom and a landlocked state at the Hindu Kush are not a region. What unites them is a
MEASUREMENT PROPERTY: each is a small or closed economy whose SINGLE DOMINANT EXPOSURE IS
PUBLISHED AND UNHEDGED, which makes each one a clean single-factor case -- the rarest thing in
macro research, where almost every economy is a blend nobody can decompose.

  * BRUNEI is LNG and oil with a currency board, and the Brunei dollar is interchangeable AT PAR
    with the Singapore dollar under an agreement running since 1967. USDSGD, which the broker
    quotes, is therefore the EXACT expression of Brunei's external value -- not a proxy.
  * TIMOR-LESTE is the world's most oil-fund-dependent state and it is running out. It is
    DOLLARISED, so its monetary policy is the Fed's; its Petroleum Fund publishes quarterly
    audited reports; and Bayu-Undan, which funded essentially the whole state, ceased production
    in 2023 on a published schedule while the statutory withdrawal rule continued.
  * THE MALDIVES is tourism and debt and nothing else. Arrivals are published DAILY by
    nationality -- one of the highest-frequency public real-activity series on earth -- against a
    pegged rufiyaa with a published parallel premium and dated external maturities.
  * BHUTAN is hydropower exported to India, pegged 1:1 to the Indian rupee, so USDINR is the
    EXACT expression of its external value; generation follows the MONSOON, so it exports in
    summer and imports in winter, every year, on a published schedule.
  * AFGHANISTAN is the pack's LIMIT CASE and is handled as one. Most layers are missing outright
    since 2021; every one of them is named, with the lawful substitute that stands in.

FOUR CALENDAR SYSTEMS run across five jurisdictions -- Islamic (Brunei, Maldives, Afghanistan),
SOLAR HIJRI (Afghanistan, whose fiscal year begins at the March equinox), TIBETAN LUNISOLAR
(Bhutan) and GREGORIAN/CATHOLIC (Timor-Leste). That is this pack's distinguishing calendar fact
and no single rule computes it.

FIVE SCRIPTS: Malay in Jawi and Rumi, Tetum and Portuguese, Dhivehi in right-to-left Thaana,
Dzongkha in Tibetan script, and Dari and Pashto in Arabic script. An English-only crawl reads
none of them.
"""
from __future__ import annotations

#: The submodule this department is. NOT imported here on purpose: `countries.load(...)` imports
#: `countries.maritime_asia.pack` by name, and binding the module's own `pack()` FUNCTION onto
#: this package would shadow the module for every `from countries.maritime_asia import pack`.
__all__ = ["pack"]
