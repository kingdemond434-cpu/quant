"""A dot in the hunt component shifts every field of a survivor key, it does not just mislabel.

Keys are `qquant.<hunt>.<cell>` and every consumer splits on dots. Measured 2026-09-01, one live
certificate was keyed `qquant.hunt16.json.AUDNZD dav_range_filter_adx SHORT afternoon NORMAL_DAY`
because the producer passed a FILE NAME. Split on dots its symbol reads "hunt16" and its family
reads "json" -- which is how a filename reached the symbol column of the currency-exposure
report, and why that row matches no authorized run and can never enrol a forward clock.
"""
from __future__ import annotations

import sys
from pathlib import Path

DESK = Path(__file__).resolve().parent.parent
for p in (str(DESK), str(DESK / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)

from survivor_publication import hunt_name  # noqa: E402


def test_the_filename_that_broke_the_live_key_is_normalised() -> None:
    assert hunt_name("hunt16.json") == "hunt16"


def test_a_path_never_survives_into_a_key() -> None:
    assert hunt_name("reports/hunt16.json") == "hunt16"
    assert hunt_name("C:\\opt\\quant\\hunt16.json") == "hunt16"


def test_no_dot_can_survive_because_consumers_split_on_dots() -> None:
    """The contract is structural: a surviving dot shifts every downstream field by one."""
    for raw in ("a.b.c.json", "hunt.16", "x.y"):
        assert "." not in hunt_name(raw), f"{raw!r} left a dot in the key component"


def test_an_already_clean_name_is_unchanged() -> None:
    assert hunt_name("hunt16") == "hunt16"
    assert hunt_name("  hunt9.json ") == "hunt9"


def test_missing_hunt_is_empty_not_the_string_none() -> None:
    """`str(None)` would put the literal 'None' in a key and match nothing forever."""
    assert hunt_name(None) == ""


def test_a_reconstructed_key_parses_into_the_right_fields() -> None:
    key = f"qquant.{hunt_name('hunt16.json')}.AUDNZD dav_range_filter_adx SHORT afternoon"
    src, hunt, cell = key.split(".", 2)
    assert (src, hunt) == ("qquant", "hunt16")
    assert cell.startswith("AUDNZD"), "the cell must survive intact, symbol first"
