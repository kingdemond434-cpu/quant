"""A scheduler's inherited start cannot admit yesterday's producer output."""
import ast
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

def test_hourly_start_resets_inherited_boundary(tmp_path, monkeypatch):
    from research.merge_hypotheses import _pipeline_started_at, _fresh_for_run, stamp_fresh_intake
    from libs.data.pit import is_stamped
    source = Path(__file__).resolve().parents[1]/"research/hourly_cycle.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    monkeypatch.setenv("QUANT_PIPELINE_STARTED_AT", "2000-01-01T00:00:00+00:00")
    # Execute the production boundary without launching trading or the full heavy cycle.
    exec(compile(ast.Module(body=[main.body[0]], type_ignores=[]), str(source), "exec"),
         {"os":os, "datetime":datetime, "UTC":UTC})
    start = _pipeline_started_at()
    assert 0 <= (datetime.now(UTC)-start).total_seconds() < 10
    fresh, old = tmp_path/"fresh.json", tmp_path/"old.json"
    fresh.write_text("{}")
    old.write_text("{}")
    old_ts = (start-timedelta(days=3)).timestamp()
    os.utime(old, (old_ts,old_ts))
    assert _fresh_for_run(fresh,start)
    assert not _fresh_for_run(old,start)
    row = {"symbol":"USDJPY", "family":"carry", "params":{},
           "found_at":"2020-01-01T00:00:00+00:00"}
    stamped = stamp_fresh_intake(row,"fresh.json",start)
    assert is_stamped(stamped)
    assert stamped["available_time"] == start.isoformat(timespec="seconds")
    assert "available_time" not in row
