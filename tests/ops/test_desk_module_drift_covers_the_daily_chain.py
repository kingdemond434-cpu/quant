"""The drift watchlist must follow the import graph, not a memory of it.

WHAT HAPPENED (gap-fixer 2026-08-28). `scripts/check_desk_module_drift.py` keeps a hand-typed
MODULES list of everything the Windows trading box executes, and its own header warns that "a
module missing from here is one that can silently decay back to the box's own stale branch".
`desks/mt5/research/hourly_cycle.py` was on it. `desks/mt5/research/daily_cycle.py` -- the module
hourly_cycle CALLS, and which IS the daily money-path chain -- was not.

MEASURED ON THE BOX THAT DAY (findstr, positive-controlled against "markout" so an empty result
could not be read as absence): its STEPS tuple began at `futures_curves` and held SIX steps
against HEAD's fourteen, and the string "decay" did not occur in the file at all. refresh_bars,
cost_fields, reconcile, qquant_shadow, execution, portfolio, decay and zentech had never run on
the machine that trades. Among them was `decay_monitor`, required by LAWS L1.59 since
2026-08-25: seven live sleeves were carrying no decay clock, so nothing there would fade a sleeve
at t<=0 or retire one at maxDD<=-25R. The fence printed "desk modules: all 32 match HEAD on both
boxes" the whole time -- a clean verdict produced by not looking.

Adding thirteen filenames fixes today. This test is what stops tomorrow: it re-derives the daily
chain's first-party imports FROM `daily_cycle.py` and fails if any of them is unwatched, so a
step added to the chain and forgotten here reddens instead of quietly decaying on the box.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FENCE = ROOT / "scripts" / "check_desk_module_drift.py"
CHAIN = ROOT / "desks" / "mt5" / "research" / "daily_cycle.py"
#: where a bare `import foo` inside a daily_cycle step resolves from, in the box's sys.path order
SEARCH = ("desks/mt5/research", "desks/mt5/mt5desk", "desks/mt5/scripts", "scripts")


def _watched() -> set[str]:
    return set(re.findall(r'^\s+"([^"]+)",', FENCE.read_text("utf-8"), re.M))


def _chain_modules() -> dict[str, str]:
    """Module name -> repo-relative path, for every first-party import in the chain."""
    src = CHAIN.read_text("utf-8")
    names: set[str] = set()
    names |= set(re.findall(r"^\s+import (\w+)", src, re.M))
    names |= set(re.findall(r"^\s+from (\w+) import", src, re.M))
    names |= set(re.findall(r"^\s+from mt5desk import (\w+)", src, re.M))
    names |= set(re.findall(r"^\s+from mt5desk\.(\w+) import", src, re.M))
    found: dict[str, str] = {}
    for n in names:
        for d in SEARCH:
            if (ROOT / d / f"{n}.py").exists():
                found[n] = f"{d}/{n}.py"
                break
    return found


def test_the_chain_itself_is_watched() -> None:
    """The module that runs the money path may never be the one nobody named."""
    assert "desks/mt5/research/daily_cycle.py" in _watched()


def test_the_live_decay_monitor_is_watched_because_l1_59_depends_on_it() -> None:
    """L1.59: every live sleeve on a decay clock. A stale copy on the box repeals it silently."""
    assert "desks/mt5/research/decay_monitor.py" in _watched()


def test_every_first_party_import_of_the_daily_chain_is_watched() -> None:
    """Derived from the graph, so a new step cannot be added and forgotten here."""
    watched, chain = _watched(), _chain_modules()
    missing = sorted(p for p in chain.values() if p not in watched)
    assert not missing, (
        "these modules run inside the daily money-path chain but no drift fence watches them, "
        "so they can decay to the trading box's own branch while the fence reports all-match: "
        f"{missing}"
    )


def test_the_derivation_actually_finds_the_chain_and_is_not_vacuously_green() -> None:
    """A positive control: an empty derived set would make the test above pass by finding nothing.

    This is the same failure the fence had -- absence read as a clean verdict -- and a test that
    can only pass is worth exactly as much as the fence that could only print all-match.
    """
    chain = _chain_modules()
    assert len(chain) >= 10, f"only resolved {len(chain)} chain modules: {sorted(chain)}"
    assert "decay_monitor" in chain
    assert "promoter" in chain
