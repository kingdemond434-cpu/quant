"""Feed schema watch: lake schema drift, parser drift behind a 200, tickets, LLM proposes only."""
from __future__ import annotations

import inspect
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import feed_schema_watch as fw  # noqa: E402
import hourly_cycle  # noqa: E402

NOW = datetime(2026, 11, 11, 12, tzinfo=UTC)


def _frame(n: int = 40, **cols) -> pd.DataFrame:
    base = {"available_time": pd.date_range("2025-01-01", periods=n, tz="UTC"),
            "value": [float(i) for i in range(n)]}
    base.update(cols)
    return pd.DataFrame(base)


def _run(tmp_path, **kw):
    return fw.run(now=NOW, series_dir=tmp_path / "series", runs_path=tmp_path / "runs.jsonl",
                  state=tmp_path / "state", report=tmp_path / "r.json", **kw)


def test_first_sight_baselines_then_a_removed_column_is_drift(tmp_path) -> None:
    (tmp_path / "series").mkdir()
    p = tmp_path / "series" / "x.parquet"
    _frame().to_parquet(p, index=False)
    assert _run(tmp_path, llm=False)["lake"]["rows"]["x.parquet"]["status"] == "BASELINED"
    _frame().drop(columns=["value"]).to_parquet(p, index=False)
    doc = _run(tmp_path, llm=False)
    assert doc["status"] == "DRIFT"
    kinds = {c["kind"] for c in doc["lake"]["rows"]["x.parquet"]["changes"]}
    assert "COLUMN_REMOVED" in kinds
    t = json.loads((tmp_path / "state" / "tickets" / "lake_x.parquet.json").read_text("utf-8"))
    assert t["state"] == "OPEN"


def test_added_column_extends_the_baseline_and_stamp_loss_is_breaking(tmp_path) -> None:
    (tmp_path / "series").mkdir()
    p = tmp_path / "series" / "y.parquet"
    _frame().to_parquet(p, index=False)
    _run(tmp_path, llm=False)
    _frame(extra=[1.0] * 40).to_parquet(p, index=False)
    assert _run(tmp_path, llm=False)["status"] == "OK"
    _frame(extra=[1.0] * 40).drop(columns=["available_time"]).to_parquet(p, index=False)
    kinds = {c["kind"] for c in _run(tmp_path, llm=False)["drift"][0]["changes"]}
    assert "STAMP_LOST" in kinds


def test_a_new_schema_held_long_enough_is_accepted_and_the_ticket_resolves(tmp_path,
                                                                            monkeypatch) -> None:
    monkeypatch.setattr(fw, "ACCEPT_AFTER_PASSES", 3)
    (tmp_path / "series").mkdir()
    p = tmp_path / "series" / "z.parquet"
    _frame().to_parquet(p, index=False)
    _run(tmp_path, llm=False)
    _frame().rename(columns={"value": "v2"}).to_parquet(p, index=False)
    assert _run(tmp_path, llm=False)["status"] == "DRIFT"
    assert _run(tmp_path, llm=False)["status"] == "DRIFT"
    doc = _run(tmp_path, llm=False)
    assert doc["lake"]["rows"]["z.parquet"]["status"] == "ACCEPTED_AS_NEW_SCHEMA"
    assert _run(tmp_path, llm=False)["status"] == "OK"


def _runs(tmp_path, rows) -> None:
    with (tmp_path / "runs.jsonl").open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps({"live": True, **r}) + "\n")


def test_parsed_nothing_behind_a_200_after_a_yield_is_parser_drift(tmp_path) -> None:
    _runs(tmp_path, [
        {"at": "a", "source": "app_rank_apple", "status": "OK", "requests": 20, "obs_added": 300},
        {"at": "b", "source": "app_rank_apple", "status": "BLOCKED", "requests": 20,
         "obs_added": 0, "raw_rows": 0, "failures": {}, "detail": "no chart parsed"},
        {"at": "a", "source": "gtrends", "status": "OK", "requests": 3, "obs_added": 5},
        {"at": "b", "source": "gtrends", "status": "BLOCKED", "requests": 3, "obs_added": 0,
         "failures": {"timeout": 3}},
        {"at": "b", "source": "never", "status": "BLOCKED", "requests": 2, "failures": {}},
    ])
    asked: list[str] = []
    doc = _run(tmp_path, propose=lambda prompt: (asked.append(prompt) or "--- a\n+++ b\n", None))
    rows = doc["free_stack"]["rows"]
    assert rows["app_rank_apple"]["status"] == "PARSER_DRIFT"
    assert rows["gtrends"]["status"] == "TRANSPORT"
    assert rows["never"]["status"] == fw.UNMEASURED            # never yielded: not drift
    t = json.loads((tmp_path / "state" / "tickets" / "free_stack_app_rank_apple.json")
                   .read_text("utf-8"))
    assert t["fetcher"].endswith("fetch_app_rank_apple")
    assert t["proposal"]["status"] == "PROPOSED_NOT_APPLIED" and len(asked) == 1
    # a proposal is requested once per ticket, never again on later passes
    _run(tmp_path, propose=lambda prompt: (asked.append(prompt) or "x", None))
    assert len(asked) == 1


def test_no_llm_seat_is_named_on_the_ticket(tmp_path) -> None:
    _runs(tmp_path, [
        {"at": "a", "source": "app_rank_apple", "requests": 1, "obs_added": 3},
        {"at": "b", "source": "app_rank_apple", "requests": 1, "obs_added": 0, "failures": {}}])
    _run(tmp_path, llm=False)
    t = json.loads((tmp_path / "state" / "tickets" / "free_stack_app_rank_apple.json")
                   .read_text("utf-8"))
    assert t["proposal"]["status"] == "NO_LLM_SEAT"


def test_nothing_on_the_host_is_unmeasured(tmp_path) -> None:
    assert _run(tmp_path, llm=False)["status"] == fw.UNMEASURED


def test_the_organ_never_writes_code() -> None:
    src = inspect.getsource(fw)
    assert "write_text(text" not in src and "subprocess" not in src


def test_the_leg_is_wired() -> None:
    src = inspect.getsource(hourly_cycle.main)
    assert '_costed("feed_schema_watch"' in src and '"feed_schema_watch": fsw' in src
    assert hourly_cycle.department_of("feed_schema_watch") == "data"
