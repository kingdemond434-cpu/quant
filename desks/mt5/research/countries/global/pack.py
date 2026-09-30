"""GLOBAL: the second spelling of the institutional lane, and ONE derivation for both.

`sources.country` carries two strings for the same region -- `institutional` on 87 grounds and
`global` on 12 -- and `libs/research/attribution.py:162` already crosswalks both to
`Global/institutional`. `pack_cells.country_pack` resolves a pack by importing
`countries.<country>.pack`, so a lane with two spellings needs two directories or half its
grounds keep being refused.

TWO DIRECTORIES, NOT TWO LISTS. This file re-exports the institutional pack's derivation rather
than repeating it. A second typed list would drift from the first the first time the broker
changed a classification, and then the region's cells would depend on which spelling a crawler
happened to file a ground under -- which is exactly the class of split this desk has paid for
before. `REGION_COMMAND` differs only in spelling and crosswalks to the same region.

(`global` is a Python keyword, so this package can never be reached by an `import` STATEMENT. It
does not need to be: `country_pack` uses `__import__(f"countries.{key}.pack", ...)`, which takes
the module path as a string and is unaffected by the keyword. The import below is spelled the
same way for the same reason.)
"""
from __future__ import annotations

import importlib
from typing import Any

_inst = importlib.import_module("countries.institutional.pack")

CODE = "GLOBAL"
NAME = "Global / institutional"
REGION_COMMAND = "global"
REGION_DESK = "GLOBAL_INSTITUTIONAL"
FOREST = "institutional"
CURRENCY = "USD"
JURISDICTIONS: tuple[str, ...] = ("global", "institutional")
NATIVE_LANGUAGES: tuple[str, ...] = ("en",)
COT_CURRENCY = ""
FISCAL_YEAR_END = ""
EXPORT_ECONOMY = "not_an_economy"
RETAIL_LEVERAGE_REGIME = "not_a_jurisdiction"

MISSION = _inst.MISSION

#: THE SAME TUPLE OBJECT the institutional pack derived, not a copy of its values.
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = _inst.EXECUTABLE_INSTRUMENTS

KNOWN_GROUNDS: tuple[dict[str, Any], ...] = _inst.KNOWN_GROUNDS

BOUNDARIES: tuple[str, ...] = (
    *_inst.BOUNDARIES,
    "this file re-exports countries/institutional/pack.py and must never grow a list of its own: "
    "one lane, one derivation, whichever spelling a ground was filed under",
)
