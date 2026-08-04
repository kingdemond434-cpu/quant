"""A monitor that cannot read its input must say so, never publish a zero.

`_is_maker` fails CLOSED, which is correct for one unknown ROW and catastrophic for an unknown
SCHEMA. Pointed at the cash-carry tape -- which stores `spot_mode`/`fut_mode` and none of the
field names the reader knows -- every leg scored taker and the monitor was about to publish
`maker_rate: 0.0` with verdict STALLED ("a DEFECT, not a note") on its very first cron fire, to be
persisted by record_desk_metrics and paged. "We could not read it" and "it was 0%" are different
claims and only one of them is evidence.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.fill_quality_monitor import (  # noqa: E402
    _LIQUIDITY_FIELDS,
    _is_maker,
    measure,
    verdict,
)

#: The real shape on disk, copied from data/moat/execution_tape/cashcarry_trades.jsonl.
_CASHCARRY_TAPE = [
    {"symbol": "BNBUSDT", "spot_mode": "taker_fallback", "fut_mode": "maker", "notional": 5.79},
    {"symbol": "FILUSDT", "spot_mode": "taker", "fut_mode": "already-flat", "notional": 10.0},
]


class TestUnreadableSchemaRefuses:
    def test_cashcarry_tape_reports_unmeasured_not_zero(self) -> None:
        m = measure(_CASHCARRY_TAPE)
        assert m["maker_rate"] is None, "an unreadable schema must never publish a rate"
        assert m["unreadable_schema"] is True
        assert m["fills"] == len(_CASHCARRY_TAPE), "it saw the rows; it just cannot judge them"

    def test_the_false_zero_never_reaches_a_verdict(self) -> None:
        v, why = verdict(measure(_CASHCARRY_TAPE), {"maker_rate": 0.242})
        assert v == "NO DATA"
        assert "DEFECT" not in why, "a measurement failure must not page as a performance finding"


class TestReadableSchemaStillMeasured:
    """The refusal must not become a mute -- it may only fire on genuinely unreadable input."""

    def test_known_schema_measures_normally(self) -> None:
        rows = [{"maker": True, "notional": 100.0, "fee": 0.01},
                {"maker": False, "notional": 100.0, "fee": 0.05}]
        assert measure(rows)["maker_rate"] == 0.5

    def test_a_genuine_zero_is_still_reported(self) -> None:
        rows = [{"maker": False, "notional": 100.0, "fee": 0.05}] * 3
        m = measure(rows)
        assert m["maker_rate"] == 0.0 and not m.get("unreadable_schema")

    def test_role_style_schema_is_readable(self) -> None:
        rows = [{"role": "maker", "notional": 100.0}, {"role": "taker", "notional": 100.0}]
        assert measure(rows)["maker_rate"] == 0.5


def test_guard_and_reader_stay_in_lockstep() -> None:
    """Every field the guard calls readable must be one `_is_maker` actually consults.

    A field listed here but unparsed by the reader makes the schema read as UNDERSTOOD while every
    row silently scores taker -- reintroducing the exact false zero. Caught this way once already.
    """
    for field in _LIQUIDITY_FIELDS:
        truthy = {"role": "maker", "liquidity": "maker"}.get(field, True)
        assert _is_maker({field: truthy}) is True, (
            f"_LIQUIDITY_FIELDS claims {field!r} is readable but _is_maker ignores it")
