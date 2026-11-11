"""GARCH dispersion scaling is a SHADOW reading until it wins out of sample (#896 audit MF1).

Standing order: GARCH/HMM and LLM sizing stay shadow-only; an input reaches money the moment it
beats the plain solve OOS, never before. So the fit runs and its per-sleeve scale is published,
and the evidence the book is solved on is untouched while `GARCH_SIZING_LIVE` is False.
"""
from __future__ import annotations

import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import model_roles  # noqa: E402
from research import pf_allocator as pa  # noqa: E402


def test_garch_is_off_the_money_path_and_says_so() -> None:
    assert pa.GARCH_SIZING_LIVE is False
    src = (_DESK / "research" / "pf_allocator.py").read_text(encoding="utf-8")
    block = src[src.index("garch_meta: dict[str, Any] ="):src.index("dd = worst_dd_r(daily)")]
    # the only write into the solved evidence sits behind the switch, and `applied` follows it
    i_gate = block.index("if GARCH_SIZING_LIVE:")
    i_write = block.index("ev[_i] = _gv_replace(_e, daily_r=apply_vol_scale(_e.daily_r, _r))")
    assert i_gate < i_write and block.count("_gv_replace(") == 1
    assert 'garch_meta["applied"] = True' in block[i_gate:]
    assert '"applied": False' in block and 'garch_meta["scale"] =' in block
    assert "SHADOW" in str(model_roles.FAMILIES["garch_vol"])
