from __future__ import annotations

import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.sandboxes import CellContext  # noqa: E402
from research.sandboxes import chan_structure_lab as chan  # noqa: E402

from libs.research import adapters as A  # noqa: E402


def _frame(symbol: str = "XAUUSD", timeframe: str = "M5") -> A.BarFrame:
    n = 120
    close = tuple(100.0 + ((i % 6) - 3) for i in range(n))
    return A.BarFrame(symbol, timeframe, tuple(str(i) for i in range(n)), close,
                      tuple(v + 1 for v in close), tuple(v - 1 for v in close), close,
                      tuple(10.0 for _ in range(n)))


def test_fractal_confirmation_never_uses_center_bar_as_decision_time() -> None:
    got = chan.confirmed_fractals((1, 3, 2), (0, 1, 0))
    assert got == [{"kind": "top", "object_index": 1, "first_known_index": 2,
                    "confirmed_index": 2, "revised_index": None}]


def test_chan_docs_become_pit_candidates_without_verdict_authority(tmp_path: Path) -> None:
    frame = _frame()
    bundle = A.ResearchBundle("b", "2026-01-01T00:00:00+00:00", "q", 10, 1, ("M5",),
                              (frame.symbol,), {frame.key: frame}, {}, {}, {})
    packet = chan.run(bundle, CellContext(tmp_path))
    assert len(packet.candidates) == len(chan.ATOMS)
    assert packet.trials_charged == 0
    assert {row["family"] for row in packet.candidates} == {
        "failed_breakout", "trend_ma_cross", "range_reversion", "level_breakout",
        "vol_transition",
    }
    assert all(row["authority"].startswith("none") for row in packet.candidates)
    assert packet.representations[0]["availability_fields"] == [
        "object_time", "first_known", "confirmed", "revised"
    ]
