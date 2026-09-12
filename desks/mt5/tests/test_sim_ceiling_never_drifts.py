"""The money path's simulation ceiling must equal the sweep's, forever.

`decision_core.ABSOLUTE_SIM_MAX` is deliberately RESTATED rather than imported from
`research.pf_allocator.CURVE_SAMPLE_MAX`, because the money path must not depend on the research
package. That restatement is sound and it is also exactly how the two drifted apart.

WHAT HAPPENED (found 2026-09-12 while citing derivations, not by anything watching). The sweep
was widened from 0.45 to 1.00 so the growth curve could find where growth genuinely turns instead
of reporting the edge of its own grid as an economic result. The money-path twin stayed at 0.45
for hours -- while its own comment went on asserting the two were "identical".

The consequence was a LATENT CAP. `cap = min(op, ABSOLUTE_SIM_MAX)` clamped deployable heat at
45% while the allocator could sample and certify to 100%. It bound nothing at the time, because
the operative ceiling was the measured 22.5% growth ceiling and both numbers sat far above it --
which is precisely why nobody would have noticed. It would have bound on the day the growth curve
first earned its way past 45%: the one day the desk would least want an unexamined constant
quietly deciding how much it may deploy, and the day it would look like the curve had simply
stopped paying.

A value restated in two files with no check between them WILL drift again. This is the check.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, DESK / rel)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_the_money_path_ceiling_equals_the_sweep_ceiling() -> None:
    """One number, restated in two places, must stay one number.

    If this fails, decide which way it should move and change BOTH -- never silence it. The whole
    point of the restatement is that the money path carries its own copy; the whole risk of the
    restatement is that the copy stops being a copy.
    """
    dc = _load("_dc_ceiling", "mt5desk/decision_core.py")
    pf = _load("_pf_ceiling", "research/pf_allocator.py")
    assert dc.ABSOLUTE_SIM_MAX == pf.CURVE_SAMPLE_MAX, (
        f"the money path would deploy at most {dc.ABSOLUTE_SIM_MAX} while the sweep certifies to "
        f"{pf.CURVE_SAMPLE_MAX}. That gap is a cap nobody chose: it is invisible until the growth "
        f"curve earns its way past the smaller number, and then it reads as the curve no longer "
        f"paying rather than as a constant refusing.")


def test_the_ceiling_is_never_lowered_by_accident() -> None:
    """A floor under the floor. The sweep was widened to 1.00 deliberately (principal: the
    measurement must not be bounded at all), so a value below that is a REDUCTION in what the desk
    may ever deploy -- which is never made silently, by this desk's standing order."""
    pf = _load("_pf_ceiling2", "research/pf_allocator.py")
    assert pf.CURVE_SAMPLE_MAX >= 1.00, (
        f"CURVE_SAMPLE_MAX is {pf.CURVE_SAMPLE_MAX}, below the 1.00 the principal set. Lowering "
        f"the sweep lowers the ceiling the desk can ever certify, and a bound on the MEASUREMENT "
        f"gets reported as an economic result -- the exact confusion widening it removed.")
