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


def test_the_oos_session_split_reads_the_utc_hour() -> None:
    import expression_factory as ef
    src = Path(ef.__file__).read_text("utf-8")
    assert "hours = world.hours[oos_entries]" not in src
    assert "world.utc_hours if world.utc_hours is not None else world.hours)[oos_entries]" in src


def test_wrong_clock_cells_are_recognised_by_their_unversioned_key() -> None:
    import expression_factory as ef
    old = {"state": "session:london", "key": "EURUSD|4|session:london|x"}
    new = {"state": "session:london", "key": "EURUSD|4|session:london@utc1|x"}
    assert ef._wrong_clock_cell(old) is True
    assert ef._wrong_clock_cell(new) is False
    assert ef._wrong_clock_cell({"state": "regime:high", "key": "E|4|regime:high|x"}) is False


def test_the_retraction_drops_archive_niches_and_re_parks_registry_rows(tmp_path) -> None:
    import json
    import sqlite3

    import expression_factory as ef

    db = sqlite3.connect(tmp_path / "r.sqlite")
    db.execute("CREATE TABLE discoveries (discovery_id TEXT, generator TEXT, source_type TEXT, "
               "sessions_json TEXT, payload_json TEXT, state TEXT, blocked_reason TEXT, "
               "updated_at TEXT)")
    old = {"cell": {"state": "session:ny", "key": "E|4|session:ny|x"}}
    new = {"cell": {"state": "session:ny", "key": "E|4|session:ny@utc1|x"}}
    rows = [("d1", old, "2026-09-20T00:00:00+00:00"), ("d2", new, "2026-09-20T00:00:00+00:00"),
            ("d3", old, "2026-10-02T00:00:00+00:00")]
    for did, payload, at in rows:
        db.execute("INSERT INTO discoveries VALUES (?,?,?,?,?,?,?,?)",
                   (did, ef.SOURCE, "expression_cell", '["session:ny"]', json.dumps(payload),
                    "BLOCKED", "NO_EXECUTOR: state filter", at))
    db.commit()

    class _Reg:
        @staticmethod
        def connect() -> sqlite3.Connection:
            return sqlite3.connect(tmp_path / "r.sqlite")

    fac = ef.Factory.__new__(ef.Factory)
    fac.archive = {"a": {"cell": old["cell"]}, "b": {"cell": new["cell"]}}
    fac.dry_run, fac.registry, fac.log = False, _Reg(), []
    out = fac.retract_wrong_clock()
    assert out == {"archive": 1, "registry": 1} and set(fac.archive) == {"b"}
    got = dict(db.execute("SELECT discovery_id, blocked_reason FROM discoveries").fetchall())
    assert got["d1"].startswith("WRONG_CLOCK") and got["d2"].startswith("NO_EXECUTOR")
    assert got["d3"].startswith("NO_EXECUTOR")          # rewritten after the fix: left alone
    assert fac.retract_wrong_clock()["registry"] == 0   # idempotent
    db.close()
