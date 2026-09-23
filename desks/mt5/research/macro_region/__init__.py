"""THE MACRO RESEARCH DEPARTMENT -- the principal's Japan mandate applied to global macro.

"FOR MACRO TOO" (principal, 2026-09-17). The Japan package answers one question continuously:
who in that country is FORCED to transact, what public record shows the forcing, and which
Fusion-executable instrument pays for knowing. This package asks the same question of the
global macro estate -- central banks, treasuries and debt management offices, reserve and
sovereign wealth managers, pension funds and insurers, dealers, index funds, producers and
hedgers, and the calendars that bind all of them -- and it is an INSTANCE of the same region
framework (`libs/research/region_mandate.py`), not a second machine.

WHY THE DIRECTORY IS `macro_region` AND THE REGION IS STILL `macro`. `desks/mt5/macro/` already
exists -- the macro INTEL desk (surprise, priced, expression, attribution, ten tracked test
modules). Every desk test puts `desks/mt5/research` on `sys.path`, so a package named `macro`
here would answer `import macro` first and silently hand those tests this department instead:
measured, it broke their collection outright. The directory is therefore `macro_region` and
nothing else changes -- `MANDATE.region` is `"macro"`, every generator is `macro:<miner>`, every
payload carries `region: "macro"`. A region runner that loads `desks/mt5/research/<region>/`
must map the region id `macro` to the package `macro_region`; the id is the department's
identity and the directory is only where the file sits.

THREE MODULES AND NOTHING ELSE.

  `mandate.py`      the region's constitution: the actors with their eleven fields, the domains
                    with their measures AND their controls, the miner specs, the twenty loop
                    steps, the immutable boundaries, and `capital_authority = False`. It is data
                    plus a validator; it measures nothing and it may size nothing.
  `miners.py`       the measurement lane: one `mine_<name>(ctx) -> dict` per domain, every one
                    with matched-day controls, era/regime stability, a permutation or bootstrap
                    null, and everything it could NOT measure named in `unmeasured`.
  `intelligence.py` the acquisition lane: the terminology dictionaries in eight languages, the
                    institutional source roots, the macro dataset catalogue, the PIT stamp, and
                    the four scouts that widen the source graph.

WHAT THIS PACKAGE MAY AND MAY NOT DO. It mints DISCOVERIES into the canonical registry
(`libs/moat/registry.py`), stamped `generator = "macro:<miner>"` with `payload.region = "macro"`,
and they take the same road as every other discovery: the conversion ladder, the compiler, the
canonical gauntlet. It never sizes, never promotes, never writes a sleeve, and never touches the
allocator -- the mandate says so in one field and the tests pin it.

THE UNIVERSE MANDATE IS NOT RELAXED HERE. No crypto-exchange ground is hunted (2026-08-18); no
single-name equity is hunted for a statistical hypothesis (2026-09-06) -- routing is by asset
class from MetaTrader's own registry, and an unclassified symbol is hunted by nothing. Macro
reference data (FRED, ECB, BIS, CFTC, EIA) informs an MT5 instrument; it is never a universe of
its own. Sources are public or licensed, and no key is ever printed.
"""
from __future__ import annotations

__all__ = ["intelligence", "mandate", "miners"]
