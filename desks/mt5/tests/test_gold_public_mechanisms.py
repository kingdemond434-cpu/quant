from __future__ import annotations

import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.sandboxes import CellContext  # noqa: E402
from research.sandboxes import gold_public_mechanisms as gold  # noqa: E402

from libs.research import adapters as A  # noqa: E402


def _frame() -> A.BarFrame:
    n = 320
    return A.BarFrame("XAUUSD", "H1", tuple(f"2026-01-{i % 28 + 1:02d}T00:00:00+00:00"
                                              for i in range(n)),
                      tuple(100.0 for _ in range(n)), tuple(101.0 for _ in range(n)),
                      tuple(99.0 for _ in range(n)), tuple(100.0 for _ in range(n)),
                      tuple(10.0 for _ in range(n)))


def test_gold_source_becomes_registered_candidates_without_source_authority(tmp_path: Path) -> None:
    frame = _frame()
    bundle = A.ResearchBundle("b", "2026-01-01T00:00:00+00:00", "q", 10, 1, ("4h",),
                              ("XAUUSD",), {frame.key: frame}, {}, {}, {})
    pkt = gold.run(bundle, CellContext(tmp_path))
    assert len(pkt.candidates) == len(gold.ATOMS)
    assert {r["family"] for r in pkt.candidates} == {
        "trend_ma_cross", "failed_breakout", "range_reversion"
    }
    assert pkt.trials_charged == 0
    assert all(r["evidence"]["source_claim_is_prior_only"] for r in pkt.candidates)
