"""A census that cries wolf is not read, so this one is tested for its FALSE POSITIVES first.

WHY THE CENSUS EXISTS. `family_event_reaction` compared a genuinely-UTC filing time to a bar index
that is BROKER time under a UTC tzinfo, and entered two to three hours before the news. The code
read correctly, the types lined up, the tzinfo said UTC, and the join was three hours out. A
defect that invisible is rarely alone, so the sites get enumerated rather than guessed at.

THE FIRST VERSION REPORTED 75 SITES AND WAS WORSE THAN NOTHING. It matched any join in a module
that mentioned an external word within forty lines, which caught `encode_quantile` and
`realized_variation` -- both purely internal. Nobody reads a list of 75 where 71 are noise, so the
scan now requires the external name to appear in the JOIN'S OWN EXPRESSION. Four sites survive.

THE PRECISION TESTS ARE THEREFORE THE POINT: a function that merely HAS an external parameter in
scope, while joining an ATR to its own bars, must come back INTERNAL.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts import check_time_joins as ctj  # noqa: E402


def _mod(tmp_path: Path, body: str, name: str = "m.py") -> Path:
    p = tmp_path / "desks" / "mt5" / "mt5desk" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p


def _scan(tmp_path: Path, body: str):
    return ctj.scan_module(_mod(tmp_path, body), tmp_path)


def test_an_external_series_joined_to_bars_is_undeclared(tmp_path):
    sites = _scan(tmp_path, '''
def family_macro_conditional(df, macro=None):
    d = _h1(df)
    m = macro.reindex(d.index).ffill()
    return m
''')
    hits = [s for s in sites if s.state == ctj.UNDECLARED]
    assert len(hits) == 1
    assert hits[0].func == "family_macro_conditional" and hits[0].call == "reindex"
    assert "BROKER time" in hits[0].why


def test_an_external_parameter_merely_in_scope_is_not_a_finding(tmp_path):
    """THE FALSE POSITIVE THAT MADE THE FIRST VERSION USELESS. A family that takes `events` and
    separately reindexes an ATR onto its own bars is not joining events to anything."""
    sites = _scan(tmp_path, '''
def family_event_reaction(df, events=None):
    d = _h1(df)
    atr = _atr(d, 20).reindex(d.index).ffill()
    return atr
''')
    assert [s.state for s in sites] == [ctj.INTERNAL]


def test_a_purely_internal_join_in_a_module_that_mentions_macro_is_internal(tmp_path):
    """`realized_variation` and `encode_quantile` were both flagged by the 40-line window."""
    sites = _scan(tmp_path, '''
"""This module discusses macro and events at length in its docstring."""

def realized_variation(df, freq="1h"):
    grid = _grid(df, freq)
    fresh = _fresh(df).reindex(grid.index, fill_value=False)
    return fresh
''')
    assert all(s.state == ctj.INTERNAL for s in sites)


def test_a_declared_site_is_recognised(tmp_path):
    sites = _scan(tmp_path, '''
def place(df, events=None, clock="bars"):
    d = _h1(df)
    if clock == "utc":
        events = [to_bar_time(e) for e in events]
    return d.index.searchsorted(events)
''')
    assert any(s.state == ctj.DECLARED for s in sites)


def test_a_tolerant_join_is_scanned_too(tmp_path):
    """`merge_asof` and `asof` are WORSE than an exact join with a wrong clock: a tolerance
    absorbs the offset and returns a plausible answer instead of an empty one."""
    assert "merge_asof" in ctj.JOINS and "asof" in ctj.JOINS
    sites = _scan(tmp_path, '''
def f(df, calendar=None):
    return df.index.asof(calendar.index[0])
''')
    assert any(s.state == ctj.UNDECLARED for s in sites)


def test_a_module_that_will_not_parse_is_skipped_not_crashed(tmp_path):
    assert _scan(tmp_path, "def broken(:\n") == []


def test_the_census_fixes_nothing(tmp_path):
    """Which frame a source is on is a fact ABOUT THAT SOURCE. Guessing it is the original error
    repeated at scale, so this enumerates and stops."""
    src = (_ROOT / "scripts" / "check_time_joins.py").read_text(encoding="utf-8")
    for forbidden in ("Edit", "replace(", "tz_convert", "subprocess", "def fix"):
        assert forbidden not in src, f"the census reached for {forbidden}"


def test_the_real_repo_census_is_short_enough_to_read():
    """The whole point of the precision work: a list nobody reads changes nothing."""
    doc = ctj.census(_ROOT)
    assert doc["n_sites"] > 100, "the scan found almost nothing, so it is probably broken"
    assert doc["by_state"][ctj.UNDECLARED] <= 20, (
        f"{doc['by_state'][ctj.UNDECLARED]} undeclared sites is a list nobody will read; the "
        "first version reported 75 and was worse than nothing")
    assert doc["by_state"][ctj.INTERNAL] > doc["by_state"][ctj.UNDECLARED]


def test_the_known_cot_gap_is_a_question_and_not_an_answer():
    """data/cot_zcache.parquet is absent from a research checkout, so the ~20 hour claim cannot
    be verified here and must not be asserted."""
    doc = ctj.census(_ROOT)
    gap = doc["known_gap_cot"]
    assert "If the cached series" in gap and "QUESTION" in gap.upper()
    assert "check it where the file lives" in gap
