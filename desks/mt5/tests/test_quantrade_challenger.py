from __future__ import annotations

import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.sandboxes import CellContext  # noqa: E402
from research.sandboxes import quantrade_challenger as qt  # noqa: E402

from libs.research import adapters as A  # noqa: E402


def test_quantrade_donates_inversions_not_historical_authority(tmp_path: Path) -> None:
    n = 120
    values = tuple(float(i) for i in range(n))
    frame = A.BarFrame("XAUUSD", "H1", tuple(str(i) for i in range(n)), values, values,
                       values, values, tuple(1.0 for _ in range(n)))
    bundle = A.ResearchBundle("b", "2026-01-01", "q", 10, 1, ("H1",), (frame.symbol,),
                              {frame.key: frame}, {}, {}, {})
    packet = qt.run(bundle, CellContext(tmp_path))
    assert len(packet.candidates) == len(qt.ATOMS)
    assert packet.trials_charged == 0
    assert all(row["evidence"]["arms"] == ["signed", "inverted", "null"]
               for row in packet.candidates)
    assert {row["kind"] for row in packet.research_methods} >= {
        "CAUSAL_INVERSION_MATRIX", "PORTFOLIO_VS_CHAMPION_ABLATION",
        "DEPENDENCE_PRESERVING_NULL_ROUTING",
    }
