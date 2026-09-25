"""Country pack `jp` -- JAPAN, held as data; see pack.py.

WHY THIS DIRECTORY EXISTS AT ALL, AND WHY IT DID NOT BEFORE. The desk already runs a Japan
DEPARTMENT (`desks/mt5/research/japan/`): a mandate, an actor map, calendars and four miners,
all of them naming USDJPY, the JPY carry crosses and JPN225 in their own declarations. What it
never had was a COUNTRY PACK, and a pack is what `pack_cells.country_pack` reads when it asks a
crawled ground which MT5 instrument its documents are about. So two grounds the crawler had
already paid to fetch -- `asia:boj_timeseries` and `asia:estat_jp_customs`, seven documents on
disk -- resolved to UNMAPPED and converted into nothing, for want of one declaration that the
rest of the desk had already made in four other files.

That is the whole reason, and it is the honest one: this pack is a DOOR, not a new thesis. It
re-declares nothing. Its instrument list is DERIVED at import from the broker's own universe
registry and the Japan department's own actor map, so it cannot drift from either.
"""
