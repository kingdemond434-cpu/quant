"""Tokens per accepted row, per box LLM job: the hourly cycle's token-waste measure."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

_DESK = Path(__file__).resolve().parent.parent
for _p in (str(_DESK), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import llm_tokens_per_accepted as m  # noqa: E402

NOW = datetime(2026, 11, 11, 1, 0, tzinfo=UTC)


def _ledger(path: Path, rows: list[dict]) -> Path:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\nnot json\n", "utf-8")
    return path


def _spend(organ: str, tokens: int, *, days_ago: float = 0.1, **kw: object) -> dict:
    return {"utc": (NOW - timedelta(days=days_ago)).isoformat(), "organ": organ,
            "model": "x/y:free", "tokens": tokens, "free": True, **kw}


def _docket(path: Path, per_source: dict, compiled: datetime = NOW) -> Path:
    # per_source sits AFTER a large hypotheses list, as on the box
    path.write_text(json.dumps({"compiled_at": compiled.isoformat(),
                                "hypotheses": [{"source": "x"}] * 50,
                                "per_source": per_source, "seats": {}}), "utf-8")
    return path


def test_ratio_waste_and_statuses(tmp_path: Path) -> None:
    led = _ledger(tmp_path / "spend.jsonl", [
        _spend("kimi_hunter", 1000, completion_tokens=400, finish_reason="stop"),
        _spend("kimi_hunter", 600, empty_content=True),
        _spend("world_lab", 500, finish_reason="length"),
        _spend("mystery_organ", 300),
        _spend("deepening_worker", 800),
        _spend("kimi_hunter", 99999, days_ago=m.WINDOW_DAYS + 1),     # outside the window
    ])
    dock = _docket(tmp_path / "mc.json", {
        "kimi": {"rows": 10, "candidates": 4}, "world_lab:oil": {"rows": 2, "candidates": 0}})
    deep = tmp_path / "deep.jsonl"
    deep.write_text(json.dumps({"at": NOW.isoformat(), "n_candidates": 2}) + "\n", "utf-8")
    doc = m.measure(NOW, ledger=led, candidates=dock, deepened=deep, root=tmp_path)
    jobs = doc["jobs"]
    k = jobs["kimi_hunter"]
    assert (k["calls"], k["tokens"], k["accepted"], k["status"]) == (2, 1600, 4, "MEASURED")
    assert k["tokens_per_accepted"] == 400.0 and k["wasted_tokens"] == 600
    assert k["accepted_from"] == ["kimi"]
    w = jobs["world_lab"]
    assert w["status"] == "NO_ACCEPTED" and w["tokens_per_accepted"] is None
    assert w["waste_share"] == 1.0
    assert jobs["mystery_organ"]["status"] == "UNMAPPED"
    assert jobs["mystery_organ"]["tokens_per_accepted"] is None, "unmapped is never a zero"
    assert jobs["deepening_worker"]["tokens_per_accepted"] == 400.0
    assert doc["no_accepted_jobs"] == ["world_lab"]
    assert doc["sources"]["unreadable_spend_lines"] == 1
    assert doc["totals"]["tokens"] == 3200


def test_no_spend_and_stale_docket_are_unmeasured(tmp_path: Path) -> None:
    doc = m.measure(NOW, ledger=tmp_path / "absent.jsonl",
                    candidates=tmp_path / "absent.json", deepened=tmp_path / "x", root=tmp_path)
    assert doc["status"] == "UNMEASURED" and doc["why"]
    led = _ledger(tmp_path / "s.jsonl", [_spend("kimi_hunter", 10)])
    dock = _docket(tmp_path / "mc.json", {"kimi": {"candidates": 3}},
                   compiled=NOW - timedelta(days=m.STALE_DOCKET_DAYS + 1))
    doc = m.measure(NOW, ledger=led, candidates=dock, deepened=tmp_path / "x", root=tmp_path)
    assert doc["jobs"]["kimi_hunter"]["status"] == "UNMEASURED"
    assert "stale" in doc["sources"]["docket"]


def test_callers_that_bypass_the_seat_are_named(tmp_path: Path) -> None:
    s = tmp_path / "scripts"
    s.mkdir()
    (s / "raw.py").write_text('URL = "https://x/api/v1/chat/completions"\nurlopen(URL)\n')
    (s / "seated.py").write_text('# chat/completions via llm_seat\nurlopen(1)\n')
    (s / "quiet.py").write_text("print(1)\n")
    assert m.unledgered_callers(tmp_path) == ["scripts/raw.py"]


def test_main_writes_the_report(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(m, "REPORT", tmp_path / "r" / "LLM_TOKENS_PER_ACCEPTED.json")
    monkeypatch.setattr(m, "measure", lambda: {"status": "UNMEASURED", "no_accepted_jobs": [],
                                               "unledgered_callers": [],
                                               "totals": {"tokens": 0, "calls": 0}})
    assert m.main() == 0
    assert json.loads(m.REPORT.read_text())["status"] == "UNMEASURED"


def test_the_issue_board_runs_it_hourly() -> None:
    from research import issue_board
    src = Path(issue_board.__file__).read_text("utf-8")
    assert '"research/llm_tokens_per_accepted.py"' in src
