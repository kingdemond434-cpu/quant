"""The control room's regime weights may not reach money unbilled (growth governance, Rule 1).

`libs.regime.control_room.sleeve_weights` reshapes how much each day of a sleeve's history
counts. Today it feeds research contracts only. The day a money-path module (order path,
sizing, allocator, promoter) reads it, the weights become a capital modifier, and
GROWTH_GOVERNANCE requires every capital modifier to be two-sided
(`libs/portfolio/capital_modifiers.py`) and billed by a missed-growth line (a `Rail` in
`libs/portfolio/rails.py` whose `where` names the consumer, measured by
`research/missed_growth.py`). This fence fails the first commit that wires it without both.
"""
from __future__ import annotations

import re
from pathlib import Path

from libs.portfolio.rails import RAILS

ROOT = Path(__file__).resolve().parents[2]

#: The money path for this purpose: everything that sends, sizes or allocates capital.
MONEY_PATH = (
    "libs/execution", "libs/risk", "libs/portfolio",
    "desks/mt5/mt5desk",
    "desks/mt5/research/pf_allocator.py", "desks/mt5/research/promoter.py",
)

#: Any of these in a module's source means it reaches the control room's weights: the library,
#: the daily organs that publish them, or their reports read off disk.
_REACH = re.compile(
    r"regime\.control_room|regime import control_room|\bsleeve_weights\b"
    r"|research\.control_room|regime_allocation_contract"
    r"|CONTROL_ROOM(_MECHANISMS)?\.json|REGIME_ALLOCATION_CONTRACT\.json")


def _money_path_files() -> list[Path]:
    out: list[Path] = []
    for rel in MONEY_PATH:
        p = ROOT / rel
        out += [p] if p.is_file() else sorted(p.rglob("*.py"))
    return [p for p in out if "__pycache__" not in p.parts]


def violations(files: list[Path], rails=RAILS) -> list[str]:
    """Money-path files that reach the weights without a two-sided modifier and a rail line."""
    bad = []
    for f in files:
        src = f.read_text(encoding="utf-8", errors="replace")
        if not _REACH.search(src):
            continue
        two_sided = "capital_modifiers" in src
        billed = any(f.stem in r.where for r in rails)
        if not (two_sided and billed):
            bad.append(f"{f.relative_to(ROOT) if f.is_relative_to(ROOT) else f}: "
                       f"two_sided={two_sided} missed_growth_line={billed}")
    return bad


def test_no_money_path_module_reads_control_room_weights_unbilled():
    files = _money_path_files()
    assert len(files) > 50, "money-path walk found too little; the paths moved"
    assert violations(files) == []


def test_the_fence_catches_an_unbilled_reader(tmp_path):
    f = tmp_path / "sizer.py"
    f.write_text("from libs.regime.control_room import sleeve_weights\n", encoding="utf-8")
    assert len(violations([f])) == 1
    f.write_text("from libs.regime import control_room\n"
                 "from libs.portfolio import capital_modifiers\n", encoding="utf-8")
    assert len(violations([f])) == 1, "two-sided alone is not enough without a rail line"


def test_the_fence_passes_a_billed_two_sided_reader(tmp_path):
    from libs.portfolio.rails import Rail
    f = tmp_path / "sizer.py"
    f.write_text("from libs.regime.control_room import sleeve_weights\n"
                 "from libs.portfolio import capital_modifiers\n", encoding="utf-8")
    rail = Rail("regime_weights", "shrink", "sizer.regime_tilt <- control_room",
                "measure_shrinkage")
    assert violations([f], rails=(rail,)) == []
