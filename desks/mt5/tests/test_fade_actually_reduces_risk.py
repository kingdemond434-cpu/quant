"""L1.59's FADE rung was decorative: a faded sleeve sized EXACTLY like a healthy one.

WHAT HAPPENED (gap-fixer 2026-08-29). `decay_monitor` implements the law's ladder correctly --
at trailing t <= 0 over n >= 20 it flags FADE and halves the sleeve's `risk_frac` in
`data/sleeves.json`, the file the gateway trades from. But `mt5desk.sizing.clamp_risk_frac`
floors every fraction at `BASE_RISK_FRAC` (3%, the principal's 2026-08-25 anti-timidity
minimum), so the write 0.03 -> 0.015 was read straight back up to 0.03.

MEASURED end to end on the real functions, identical inputs:

    risk_frac=0.03  (HEALTHY) -> 3.0 lots
    risk_frac=0.015 (FADED)   -> 3.0 lots

The monitor ran, the flag was set, the ledger recorded `FADE risk_frac [0.03, 0.015]`, and the
trade risked exactly what it had before. LAWS L1.59 states in its own text that *"a decay flag
nothing consumes is an opinion, not a monitor"* -- and the flag WAS consumed, by a floor one
layer below where the law was looking. That is the desk's recurring class: a producer computes
a distinction and the consumer collapses it.

THE FLOOR IS NOT THE BUG and is deliberately untouched here. A 3% minimum for a PROVEN sleeve is
the principal's order. A faded sleeve is one whose edge has been measured ABSENT at the same n
the desk trusts for promotion, so the premise of that minimum no longer holds -- and the sealed
core is explicit that sizing beyond demonstrated edge is not aggression but ruin. The fade is
therefore applied as a MULTIPLIER outside the clamp, exactly like `authority_ramp`, so both
rules keep their meaning.

These tests exercise the REAL `promoted_lot` from `mt5desk.decision_core` -- the module the
gateway's sizing has lived in since the 2026-09-05 split, importable on Linux -- so they pin
behaviour on the shipped money path rather than on a copy of it.
"""

from __future__ import annotations

import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from mt5desk import decision_core as _dc  # noqa: E402
from mt5desk import sizing  # noqa: E402

_SRC = (_DESK / "mt5desk" / "gateway.py").read_text(encoding="utf-8")


def _gateway_ns() -> dict:
    """The sizing laws by name, from the decision core that holds them."""
    return dict(vars(_dc))


class _Info:
    """Broker-truth fields the sizer reads, duck-typed as MT5 returns them."""

    trade_tick_value = 1.0
    trade_tick_size = 0.01
    volume_min = 0.01
    volume_step = 0.01
    volume_max = 100.0
    trade_contract_size = 100.0
    digits = 2


def test_the_gateway_actually_halves_a_faded_sleeve() -> None:
    """THE DEFECT. Both sides measured through the shipped `promoted_lot`."""
    ns = _gateway_ns()
    healthy = ns["promoted_lot"](10_000.0, 500, 1.0, "EURUSD", _Info(), 0.03, None)
    faded = ns["promoted_lot"](10_000.0, 500, 1.0, "EURUSD", _Info(), 0.03, "2026-08-29T00:00")
    assert healthy > 0, "the control sized nothing -- the harness is not exercising the path"
    assert faded == round(healthy * sizing.FADE_FACTOR, 2), (
        f"a FADED sleeve sized {faded} against a healthy {healthy}: L1.59's fade is not "
        "reaching the lot. This is the state the desk shipped -- the monitor halved risk_frac "
        "and clamp_risk_frac floored it straight back to the 3% base."
    )


def test_the_three_percent_floor_still_governs_a_healthy_sleeve() -> None:
    """The other direction, and it matters: this must not become a timidity regression.

    The principal's base minimum is untouched for anything that has NOT been faded.
    """
    assert sizing.clamp_risk_frac(0.001) == sizing.BASE_RISK_FRAC
    assert sizing.clamp_risk_frac(None) == sizing.BASE_RISK_FRAC
    assert sizing.clamp_risk_frac(0.99) == sizing.MAX_RISK_FRAC
    assert sizing.decay_factor(None) == 1.0, "an unfaded sleeve must be scaled by exactly 1"
    assert sizing.decay_factor(False) == 1.0
    assert sizing.decay_factor("") == 1.0


def test_the_fade_is_reduce_only_and_can_never_raise_a_fraction() -> None:
    """A sizing multiplier that can exceed 1.0 is an over-size path wearing a risk name."""
    for flag in (None, False, "", "2026-08-29", True, 1):
        assert 0.0 < sizing.decay_factor(flag) <= 1.0


def test_a_dynamic_up_sleeve_is_halved_not_quartered() -> None:
    """Why the FLAG is the single source of truth rather than the stored fraction.

    The old monitor wrote `risk_frac = old * 0.5`. With a multiplier ALSO applied, a sleeve at
    the 6% dynamic-up level would be written to 0.03, floored to 0.03, then halved to 0.015 --
    a 4x cut where L1.59 orders 2x. Two mechanisms for one halving is one too many.
    """
    ns = _gateway_ns()
    # Equity chosen so NEITHER leg touches promoted_lot's hard 5.0-lot ceiling: at 10k the
    # healthy 6% leg saturates at 5.0 and the ratio would read 0.6, hiding the property.
    healthy = ns["promoted_lot"](4_000.0, 500, 1.0, "EURUSD", _Info(), 0.06, None)
    faded = ns["promoted_lot"](4_000.0, 500, 1.0, "EURUSD", _Info(), 0.06, "2026-08-29T00:00")
    assert 0 < healthy < 5.0, f"the control clipped at the lot ceiling ({healthy}); fixture bug"
    assert faded == round(healthy * 0.5, 2), f"{faded} vs half of {healthy}"


def test_the_fade_constant_cannot_drift_between_its_two_homes() -> None:
    """`sizing.FADE_FACTOR` and `decay_monitor.FADE_FACTOR` are the same risk decision."""
    from research import decay_monitor  # noqa: PLC0415

    assert sizing.FADE_FACTOR == decay_monitor.FADE_FACTOR, (
        "the fade constant disagrees between the organ that decides it and the code that "
        "applies it -- one of them is silently wrong on the money path"
    )


def test_the_monitor_no_longer_mutates_risk_frac() -> None:
    """Single source of truth, asserted on the shipped source rather than on a copy."""
    src = (_DESK / "research" / "decay_monitor.py").read_text(encoding="utf-8")
    assert 'row["risk_frac"] = round(old * FADE_FACTOR' not in src, (
        "the monitor is halving the stored fraction again -- clamp_risk_frac floors it back "
        "to 3% and the fade is inert once more"
    )
    assert 'row["decay_faded"] = now' in src, "the flag that carries the fade is gone"


def test_the_gateway_bills_heat_for_what_it_actually_risks() -> None:
    """`q_charge` reserves portfolio heat. Billing a faded sleeve at full charge would
    over-reserve -- safe, but it makes the heat budget describe a book nobody is running."""
    assert "decay_factor(_s.get(\"decay_faded\"))" in _SRC, (
        "q_charge no longer reflects the fade; the heat ledger and the order path disagree "
        "about how much risk this sleeve carries"
    )
