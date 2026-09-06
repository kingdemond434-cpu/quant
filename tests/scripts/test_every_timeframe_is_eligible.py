"""THE DESK WAS HOURLY-ONLY AND NOTHING SAID SO -- IT LOOKED LIKE A CHOICE.

MEASURED 2026-09-06. The bar store held 82 symbols at H1 and exactly six non-H1 files in total:
XAUUSD at M1/M5/M15 and three FX crosses at M15, all placed by hand. Two hardcodes produced that
and kept it that way:

  download_all_symbols  `existing` was keyed by SYMBOL, computed from `*_H1.parquet`. Once a
                        symbol had an H1 file the downloader considered it finished and would
                        never fetch a second timeframe for it -- not once, ever.
  refresh_tail          globbed `*_H1.parquet` and passed `mt5.TIMEFRAME_H1`. So the six non-H1
                        files were refreshed by NOTHING, and simply froze.

WHAT THE SECOND ONE COST. XAUUSD_M5, _M15 and _M1 held no bar after 2026-08-21 23:55. The three
gold scalp sleeves went on their forward clock on 2026-08-22. They had therefore had ZERO bars for
the entire life of that clock, which is why all three sat at forward n=0 with 39/65/69 observations
tagged historical, and why "are the two gold sleeves ready for live capital" kept being answered
from selection-era rows. Not a quiet market. Not a state file failing to persist. The instruments
they trade had not been updated since the day before they started.

A bar gap and an absence of trades are indistinguishable downstream -- both are "no fill" -- which
is why the refresher must now say GAP out loud when it cannot bridge one.
"""
from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
_DL = _ROOT / "desks" / "mt5" / "scripts" / "download_all_symbols.py"
_REFRESH = _ROOT / "desks" / "mt5" / "scripts" / "refresh_tail.py"

#: Every timeframe MT5 exposes that this desk stores. If a downloader or refresher cannot reach
#: one of these, that timeframe is unhuntable however many miners propose mechanisms on it.
EXPECTED = ("M1", "M5", "M15", "M30", "H1", "H4", "D1")


def _code(path: Path) -> str:
    """Source with comment lines stripped.

    Both files now DISCUSS the H1 hardcode at length in their comments. A fence grepping raw text
    for `_H1` would match the explanation of why `_H1` is gone -- the same trap that fired three
    times on the sync script's "never rebase, never stash" header.
    """
    return "\n".join(ln for ln in path.read_text("utf-8").splitlines()
                     if not ln.lstrip().startswith("#"))


def test_both_files_exist() -> None:
    """Otherwise every assertion below is vacuous on an empty string (L1.63)."""
    assert _DL.is_file() and _REFRESH.is_file()


def test_the_refresher_no_longer_globs_one_timeframe() -> None:
    """THE DEFECT THAT FROZE THE GOLD SCALP BARS."""
    code = _code(_REFRESH)
    assert '"*_H1.parquet"' not in code and "'*_H1.parquet'" not in code, (
        "refresh_tail globs H1 only again -- every sub-hourly series in the store stops being "
        "refreshed by anything, and the sleeves trading them go to forward n=0 in silence")
    assert '"*.parquet"' in code, "the refresher must walk the whole store"


def test_the_refresher_asks_for_the_timeframe_the_file_names() -> None:
    """Walking every file is useless if it still requests H1 bars for an M5 parquet."""
    code = _code(_REFRESH)
    assert "mt5.TIMEFRAME_H1" not in code, (
        "the fetch is pinned to H1 again -- it would walk every file and write hourly bars into "
        "all of them, which is worse than not refreshing: it CORRUPTS the sub-hourly series")
    assert "TIMEFRAME_{tf}" in code, "the timeframe must be derived from the file's own name"


def test_the_refresher_sizes_its_fetch_to_the_gap() -> None:
    """200 bars is eight days at H1 and sixteen HOURS at M5.

    On a file sixteen days stale a fixed fetch cannot reach back to where the history ends, and
    the concat then writes a parquet with a hole in it -- worse than the stale file, because a
    hole is invisible to every reader and silently becomes a hole in a forward record.
    """
    code = _code(_REFRESH)
    assert "MAX_FETCH" in code and "gap //" in code, (
        "the fetch is a fixed size again; on any stale sub-hourly series it will write a hole")
    assert "GAP" in code, (
        "an unbridgeable gap no longer names itself -- nothing downstream can then tell 'no trade "
        "fired' from 'no bar existed to fire on', which is the confusion that cost the gold "
        "sleeves sixteen days")


def test_the_downloader_tracks_what_it_has_per_symbol_and_timeframe() -> None:
    """THE DEFECT THAT MADE THE STORE H1-ONLY IN THE FIRST PLACE."""
    code = _code(_DL)
    assert 'f.stem.replace("_H1", "")' not in code, (
        "`existing` is keyed by symbol again -- any symbol holding an H1 file is treated as "
        "complete and will never receive a second timeframe")
    assert "rpartition" in code and "existing" in code, (
        "`existing` must be a (symbol, timeframe) set, or the downloader cannot tell a symbol "
        "missing M5 from one that is fully downloaded")


def test_every_timeframe_this_desk_stores_is_reachable() -> None:
    """Both ends must know the whole ladder, not the two someone needed that week."""
    dl, refresh = _code(_DL), _code(_REFRESH)
    # Anchored on the ASSIGNMENT, not the name. Both files also mention these tables in prose, and
    # a loose `NAME[^{]*\{` happily matched a docstring and then ran on to the first brace it
    # found -- an f-string -- so the fence was reading `info.name` and calling it the table.
    depth = re.search(r"^TIMEFRAME_DEPTH:\s*dict\[str, int\] = \{(.*?)^\}", dl, re.S | re.M)
    frames = re.search(r"^TIMEFRAMES:\s*dict\[str, int\] = \{(.*?)^\}", refresh, re.S | re.M)
    assert depth and frames, "the timeframe tables moved; this fence cannot see what is eligible"
    for tf in EXPECTED:
        assert f'"{tf}"' in depth.group(1), f"{tf} is not downloadable -- no bars will ever exist"
        assert f'"{tf}"' in frames.group(1), (
            f"{tf} is downloadable but not refreshable, which is the exact shape of the bug: the "
            "series gets created once and then freezes forever")


def test_the_downloader_writes_the_timeframe_into_the_filename() -> None:
    """The suffix is how the refresher knows what to request. A file without one cannot be kept
    current, so writing `<SYM>.parquet` would recreate the freeze one level down."""
    assert 'f"{name}_{tf}.parquet"' in _code(_DL), (
        "the downloader no longer stamps the timeframe into the filename; refresh_tail parses it "
        "from there, so such a file would never be refreshed again")


def test_an_empty_timeframe_selection_refuses_rather_than_downloading_nothing() -> None:
    """A typo in MT5_TIMEFRAMES must not read as a successful no-op.

    "Downloaded 0 series" and "nothing needed downloading" print almost the same and mean opposite
    things. Absence is never a pass (L1.28a).
    """
    code = _code(_DL)
    assert "refusing to download nothing quietly" in code, (
        "an unrecognised MT5_TIMEFRAMES value silently downloads nothing and exits 0")
