"""A COUNTING GATE ON THE COST TRAP, because two prose sweeps did not close it.

`mt5desk/engine.py` carries the most expensive docstring on this desk: `spread_per_lot` wants
DOLLARS PER LOT, every gold call site passed a hardcoded 0.48, and the engine charged gold
0.0048/oz -- three percent of its real spread. Every gold backtest ran very nearly spread-free,
and the 3x cost-stress gate that existed to catch exactly this was stressing 3% up to 9%.

It was fixed on 2026-08-18 (a21a3bb) and swept again on 2026-09-08 (8240a0f4, "Every remaining
hand-rolled cost site goes through the engine's own constructor"). On 2026-09-11 an external
review counted THIRTY-FOUR surviving literal sites, and `mt5desk/financing.py:43` concedes one of
them in prose -- a comment naming a defect is not a gate, and the desk has a law about that
(L1.49: a gate that never ran is a claim the desk cannot cash).

WHY A RATCHET AND NOT A BAN. Most of the survivors are dead one-off research scripts
(`run_hunt*`, `test_bt*`, `debug_bt`) that produce no artifact anything reads. Failing the suite
until all 34 are rewritten would mean either a day of edits to dead code before anything else can
land, or -- far more likely -- the gate being deleted. So the bar is the count, it may only ever
fall (L1.50, coverage floors ratchet UP only; this is the same rule pointed downward), and a NEW
site fails immediately. That makes the number go one direction without blocking the work.

THE FIX AT A SITE IS `Costs.from_symbol(meta, mult=...)`, which derives the spread from the
symbol's own registry metadata (`median_spread_pts * tick_size * contract_size`) and carries
`quote_per_account` so the commission is not charged 184x wrong on a JPY cross. A literal is only
ever right by coincidence, and only for one symbol.
"""
from __future__ import annotations

import re
from pathlib import Path

DESK = Path(__file__).resolve().parent.parent

#: Every literal `spread_per_lot=<number>` passed to a Costs construction, measured 2026-09-11.
#: THIS NUMBER MAY ONLY GO DOWN. Lower it in the same commit that removes a site; never raise it.
#:
#: 51, not the 34 the external review reported, and the difference is the point: the review
#: grepped the single literal `spread_per_lot=0.48` (the gold value), while ANY literal spread is
#: the same defect -- right only by coincidence and only for one symbol. Composition at the bar:
#: 31 outside test files (the research scripts and side channels), 20 inside files named test_*,
#: most of the latter being `scripts/test_bt*.py`, which are scratch backtests rather than tests.
MAX_LITERAL_SITES = 51

#: A literal spread in a keyword argument. `spread_per_lot=self.spread_per_lot * mult` (the
#: `stressed()` method) and `spread_per_lot=max(spread * mult, 0.05)` (the constructor itself)
#: are DERIVED, not literal, and must not be counted -- they are the two implementations the
#: rest of the desk is supposed to route through.
_LITERAL = re.compile(r"spread_per_lot\s*=\s*[0-9]")


def _sites() -> list[str]:
    out: list[str] = []
    for p in sorted(DESK.rglob("*.py")):
        if p.name == Path(__file__).name:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            # A comment ABOUT the defect is not the defect. `financing.py` and
            # `portfolio_projection.py` both discuss it in prose and must not be charged for it.
            if line.lstrip().startswith("#"):
                continue
            if _LITERAL.search(line):
                out.append(f"{p.relative_to(DESK)}:{i}")
    return out


def test_the_literal_cost_sites_only_ever_decrease() -> None:
    sites = _sites()
    assert len(sites) <= MAX_LITERAL_SITES, (
        f"{len(sites)} literal `spread_per_lot=` sites, up from {MAX_LITERAL_SITES}. A literal "
        f"spread is right only by coincidence and only for one symbol: use "
        f"`Costs.from_symbol(meta, mult=...)`, which derives it from the registry and carries "
        f"`quote_per_account`. New sites:\n  " + "\n  ".join(sites[MAX_LITERAL_SITES:]))


def test_the_ratchet_is_tight_so_progress_is_recorded() -> None:
    """When sites are removed, the bar comes down in the same commit -- or this says so.

    A ratchet nobody tightens is a ratchet at its starting value forever, which is how a gate
    stops measuring anything. This fails once the real count drops, and the fix is one line.
    """
    n = len(_sites())
    assert n == MAX_LITERAL_SITES, (
        f"{n} literal sites but MAX_LITERAL_SITES is {MAX_LITERAL_SITES}. Sites were removed and "
        f"the bar was not lowered to match: set MAX_LITERAL_SITES = {n}.")


def test_the_engines_own_derivations_are_not_counted_as_literals() -> None:
    """The regex must not charge `from_symbol` and `stressed` for being the fix."""
    engine = (DESK / "mt5desk" / "engine.py").read_text(encoding="utf-8")
    assert "spread_per_lot=max(spread * mult, 0.05)" in engine
    assert not _LITERAL.search("spread_per_lot=max(spread * mult, 0.05)")
    assert not _LITERAL.search("spread_per_lot=self.spread_per_lot * float(spread_mult)")
