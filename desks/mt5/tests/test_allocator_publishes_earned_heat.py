"""The book publishes the heat it earned inside the band, and every gateway scale-down is priced.

Auditor, 2026-11-05 (Rule 2): when the posterior earns heat above the resolved level and the hold
does not bind, heat.total used to read the resolved figure, so the gateway scaled the book back
and growth the law allowed up to the effective ceiling never deployed.
"""
from __future__ import annotations

import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import missed_growth as MG  # noqa: E402
from research import pf_allocator as pa  # noqa: E402


def test_a_book_inside_the_band_publishes_its_own_total() -> None:
    # resolved 0.20, effective ceiling 0.25: a posterior book at 0.24 publishes 0.24
    assert pa.published_heat_total(0.24, 0.20, 0.25, held=False) == 0.24
    # past the effective ceiling it never licenses its own number
    assert pa.published_heat_total(0.30, 0.20, 0.25, held=False) == 0.20
    # a held book always publishes its own total (bind_verdict already bounded it to the band)
    assert pa.published_heat_total(0.22, 0.20, 0.20, held=True) == 0.22
    # survival resolved below the target: the band is [hi, hi]
    assert pa.published_heat_total(0.05, 0.05, 0.05, held=False) == 0.05


def test_every_gateway_scale_down_is_priced(monkeypatch) -> None:
    from mt5desk import decision_core as dc
    monkeypatch.setattr(dc, "live_heat_ceiling", lambda heat: (0.20, "recorded constant"))
    funded = {"a": 0.15, "b": 0.10}
    sd = pa.gateway_scale_down(funded, {"total": 0.25}, lambda b: sum(b.values()) * 0.1)
    assert sd["status"] == "SCALED" and sd["deployed"] == 0.20
    assert sd["d_elogw_per_day"] < 0
    assert pa.gateway_scale_down(funded, {"total": 0.25},
                                 lambda b: 0.0)["d_elogw_per_day"] == 0.0
    monkeypatch.setattr(dc, "live_heat_ceiling", lambda heat: (0.30, "measured"))
    assert pa.gateway_scale_down(funded, {"total": 0.25}, lambda b: 0.0)["status"] == "NOT_BINDING"
    line = MG.gateway_scale_down_line({"heat": {"gateway_scale_down": sd}})
    assert line["verdict"] == MG.COSTS and line["value_logw_per_day"] < 0
    assert MG.gateway_scale_down_line({})["verdict"] == MG.UNMEASURED
    src = (_DESK / "research" / "missed_growth.py").read_text(encoding="utf-8")
    assert '"gateway_scale_down": gateway_scale_down_line(alloc)' in src


def test_the_fallback_is_clamped_to_the_published_heat() -> None:
    """#748/#751 audit SF: the fallback deployed 0.050008 against a 0.050003 ceiling."""
    fb, meta = pa.ceiling_guard_book({"a": 0.025004, "b": 0.025004}, 0.050003, eps=0.0)
    assert sum(fb.values()) <= 0.050003 + 1e-12 and meta["scaled"] is True
    src = (_DESK / "research" / "pf_allocator.py").read_text(encoding="utf-8")
    assert 'ceiling_guard_book(_fb_doc["book"],' in src
