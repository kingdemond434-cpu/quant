"""The carry pins in the Fusion min-lot book cannot trade, at the EUR 10 stamp line (#771).

Hourly pass precondition before any Fusion re-arm (2026-11-06): the code's min-lot set still names
eurzar_carry_asia_p_8339edce23032d21 and usdnok_carry_asia_p_ff35bb7c8427d66f, both decayed
(the Judge: EURZAR -0.164 against its +0.42 certificate; EURNOK carry -0.218). Two layers stop
them, each pinned here: the active set (data/MINLOT_OVERRIDE.json) is gold_asia alone, so they are
never stamped; and stamped or not, the principal zero (PRINCIPAL_ZERO['fusion'] via
FUSION_FX_OUT_ZERO) is checked before any size, on the row's name and on its book key.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import decision_core as dc  # noqa: E402

CARRY = ("eurzar_carry_asia_p_8339edce23032d21", "usdnok_carry_asia_p_ff35bb7c8427d66f")
_FX = SimpleNamespace(volume_min=0.01, volume_step=0.01, volume_max=100.0,
                      trade_tick_size=0.00001, trade_tick_value=1.0)


def test_the_carry_pins_are_principal_zeros_on_fusion() -> None:
    for name in CARRY:
        assert name in dc.FUSION_FX_OUT_ZERO and dc.principal_zero(name, "fusion")
        assert dc.cert_zero_row({"name": name})


def test_stamped_or_not_a_carry_pin_sends_no_order_at_eur_266() -> None:
    rows = [{"name": n} for n in CARRY]
    dc.stamp_minlot_override(rows, frozenset({"gold_asia"}), 266.0)      # the box's active set
    assert not any(r.get("minlot_override") for r in rows)
    for name, sym in zip(CARRY, ("EURZAR", "USDNOK"), strict=True):
        forced = dc.minlot_override_size({"name": name, "minlot_override": True}, sym, _FX,
                                         266.0, 0.02)
        assert forced is not None and forced[0] == 0.0 and "0.0" in forced[2]


def test_the_book_key_path_is_zeroed_too() -> None:
    # a row that reaches the allocator book under another name still carries the pinned name
    for name in CARRY:
        assert dc.cert_zero_row({"name": name, "book_key": "EURZAR_carry_asia"})
