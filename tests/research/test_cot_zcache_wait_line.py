"""The cot_positioning BLOCKED_DATA wait carries a missed_growth line and its adoption commands.

Audit COT_AXIS_DEEPENING_31eb89f3d should-fix: until a v2-stamped zcache exists on the box the
family is held, and every hold is billed -- delta_elogw UNMEASURED with its cause (never a zero)
and the box commands that clear it. No network: fixtures only.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

_ROOT = Path(__file__).resolve().parents[2]
for _p in (_ROOT, _ROOT / "desks" / "mt5", _ROOT / "desks" / "mt5" / "research"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from libs.data import cot_source  # noqa: E402


def _frame() -> pd.DataFrame:
    idx = pd.date_range("2024-01-02", periods=5, freq="7D", tz="UTC")
    return pd.DataFrame({"EURUSD": [0.1, 0.2, -0.3, 0.4, 0.0]}, index=idx)


def test_an_unstamped_cache_is_a_billed_unmeasured_hold_with_its_adoption(tmp_path) -> None:
    path = tmp_path / "cot_zcache.parquet"
    pq.write_table(pa.Table.from_pandas(_frame()), str(path))   # v1: no stamp
    line = cot_source.zcache_wait_line(path, at="2026-10-14T08:00:00+00:00")
    assert line["held"] is True and line["family"] == "cot_positioning"
    assert line["verdict"] == "UNMEASURED" and line["delta_elogw"] == "UNMEASURED"
    assert line["value"] is None                                # never a zero (L1.28a)
    assert str(line["cause"]).startswith("BLOCKED_DATA")
    assert line["adoption_steps"] == ["python scripts/refresh_cot_zcache.py",
                                      "cd desks/mt5 && python -m mt5desk.fetch_tff"]
    assert "refresh_cot_zcache.py" in str(line["adoption"])
    assert "mt5desk.fetch_tff" in str(line["adoption"])


def test_a_v2_cache_or_no_cache_holds_nothing(tmp_path) -> None:
    path = tmp_path / "cot_zcache.parquet"
    assert cot_source.zcache_wait_line(path)["verdict"] == "NOT_BINDING"     # absent
    cot_source.write_zcache(_frame(), path)
    line = cot_source.zcache_wait_line(path)
    assert line["verdict"] == "NOT_BINDING" and line["held"] is False
    assert line["value"] == 0.0 and line["delta_elogw"] == 0.0


def test_the_daily_missed_growth_run_publishes_the_wait(tmp_path, monkeypatch) -> None:
    import missed_growth as mg

    path = tmp_path / "cot_zcache.parquet"
    pq.write_table(pa.Table.from_pandas(_frame()), str(path))
    monkeypatch.setattr(cot_source, "ZCACHE", path)
    monkeypatch.setattr(mg, "STOP_GEOMETRY", tmp_path / "absent.json")
    doc = mg.run(write=False)
    line = doc["published_gate_lines"]["cot_zcache_definition_wait"]
    assert line["verdict"] == mg.UNMEASURED and line["held"] is True
    assert "refresh_cot_zcache.py" in line["adoption"]
