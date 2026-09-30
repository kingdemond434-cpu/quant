"""Research session states are judged in UTC, not on the broker's EET stamp hour (2026-09-30)."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.regime import session_clock  # noqa: E402

_IDX = pd.DatetimeIndex(["2026-07-15 07:00", "2026-07-15 10:00", "2026-07-15 16:00"], tz="UTC")


def test_the_formula_factory_session_state_reads_utc_hours() -> None:
    import expression_factory as ef
    world = SimpleNamespace(hours=np.asarray(_IDX.hour, dtype=np.int16),
                            utc_hours=session_clock.utc_hours(_IDX), vol_regime=None)
    # "london" is 07-13 UTC: stamp 07:00 (04:00 UTC) is out, 10:00 (07:00 UTC) is in.
    assert ef._state_mask(world, "session:london").tolist() == [False, True, False]
    # 16:00 stamp is 13:00 UTC: New York.
    assert ef._state_mask(world, "session:newyork").tolist() == [False, False, True]


def test_the_residual_study_labels_sessions_in_utc() -> None:
    import factor_model_coevolution as fmc
    df = pd.DataFrame({"close": [1.0, 1.01, 1.02], "tick_volume": [1.0, 2.0, 3.0]}, index=_IDX)
    labels = fmc._labels(df, np.arange(3), "EURUSD", 8)
    assert labels["session"] == ["asia", "london", "ny"]


def test_a_corrected_session_cell_is_not_skipped_as_already_tested(monkeypatch) -> None:
    import expression_factory as ef
    monkeypatch.setattr(ef.dsl, "canonical_key", lambda _e: "E")
    key = ef.Cell.key.fget
    sess = SimpleNamespace(symbol="EURUSD", hold=8, state="session:london", expr=None)
    plain = SimpleNamespace(symbol="EURUSD", hold=8, state="none", expr=None)
    assert key(sess) == "EURUSD|8|session:london@utc1|E"
    assert key(plain) == "EURUSD|8|none|E"      # unchanged: nothing else is re-tested
