"""No live family is left with no generator because a producer read a narrower registry.

Measured 2026-11-03 (JUDGE_COVERAGE `unmined_live_families`): seven of the fourteen hunt16
dav_* families had ZERO docket rows. `live_family_names` counts three populations
(FAMILY_REGISTRY, the orthogonal set, hunt16). `breadth_sweep.default_families` enumerated only
the first two, and `gauntlet_buildability._family_table` read `dir(families)`, which never lists
the hunt16 constructors the module's `__getattr__` serves. So the sweep skipped them, and when it
was pointed at them the probe set every cell aside as NO_IMPLEMENTATION while the gauntlet built
them fine. These pins hold the class shut: whatever the gauntlet can resolve, the probe resolves,
and every live family callable on bars alone is swept.
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk import families  # noqa: E402
from mt5desk import families_orthogonal as fo  # noqa: E402
from mt5desk.executables import hunt16_families  # noqa: E402

from research import breadth_sweep as bs  # noqa: E402
from research import gauntlet_buildability as gb  # noqa: E402


def _gauntlet_resolves(name: str) -> bool:
    """The sealed gauntlet's own two lookups (external_gauntlet.build_cell)."""
    return callable(getattr(families, f"family_{name}", None)) or name in fo.ORTHOGONAL_FAMILIES


def test_the_buildability_probe_resolves_whatever_the_gauntlet_resolves() -> None:
    table = gb._family_table()
    missing = [f for f in families.live_family_names()
               if _gauntlet_resolves(f) and f not in table]
    assert missing == []


def test_no_hunt16_family_reads_as_no_implementation() -> None:
    for name in hunt16_families():
        verdict, why = gb.family_verdict(name)
        assert verdict != gb.NO_IMPLEMENTATION, (name, why)


def _bars_alone(fn) -> bool:
    params = list(inspect.signature(fn).parameters.values())[1:]
    return not [p for p in params if p.default is inspect.Parameter.empty and p.name != "side"
                and p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)]


def test_every_live_family_callable_on_bars_alone_is_swept_or_set_aside_by_name() -> None:
    sweepable, blocked = bs.default_families()
    unaccounted = []
    for name in families.live_family_names():
        fn = getattr(families, f"family_{name}", None) or fo.ORTHOGONAL_FAMILIES.get(name)
        if not callable(fn) or name in bs.READY:
            continue
        try:
            alone = _bars_alone(fn)
        except (TypeError, ValueError):
            continue
        if alone and name not in sweepable and name not in blocked:
            unaccounted.append(name)
    assert unaccounted == []


def test_every_hunt16_family_is_swept() -> None:
    sweepable, blocked = bs.default_families()
    for name in hunt16_families():
        assert name in sweepable or name in blocked, name
