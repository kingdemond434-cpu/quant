"""research_pnl streams the hypothesis graph and runs on its own clock (2026-11-11).

Box read HP2: the organ died with MemoryError on 2026-09-21 reading the whole ~5.7M-line graph
into dicts, and the daily chain never reached it after 09-24, so the bandit's per-source worth
prior (data/research_marginal.json) went 44 days stale. These pin the streamed read (same answer
as the full read), the tail read of the forecast log, the 6 h self-skip and the hourly wiring.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
REPO = BASE.parent.parent
for p in (str(BASE), str(REPO)):
    if p not in sys.path:
        sys.path.insert(0, p)

from research import research_pnl as rp  # noqa: E402


def _write(path: Path, rows: list[object]) -> None:
    path.write_text("".join((r if isinstance(r, str) else json.dumps(r)) + "\n" for r in rows),
                    "utf-8")


def test_streamed_read_keeps_last_row_per_id_and_matches_census(tmp_path: Path) -> None:
    g = tmp_path / "graph.jsonl"
    full = [
        {"id": "a", "source": "external", "fate": "BORN", "params": {"x": 1}},
        {"id": "b", "source": "hunt16.json", "fate": "FAILED"},
        {"id": "a", "source": "external", "fate": "CERTIFIED", "gates": {"g": 1}},
        {"id": "c", "source": "external", "fate": "BURIED"},
    ]
    _write(g, [*full, "", "{torn", "null", {"no": "id"}])
    rows, gap = rp._graph_rows(g)
    assert gap is None
    assert rp.LAST_GRAPH_LINES == 4
    assert sorted(r["id"] for r in rows) == ["a", "b", "c"]
    assert all(set(r) == {"id", "source", "fate"} for r in rows)
    assert rp.census(rows) == rp.census(full)
    assert rp.census(rows)["external"] == {"trials": 2, "failed": 1, "certified": 1,
                                           "arm": rp.arm_of("external")}


def test_absent_graph_is_a_named_gap(tmp_path: Path) -> None:
    rows, gap = rp._graph_rows(tmp_path / "absent.jsonl")
    assert rows == [] and "unreadable" in gap


def test_forecast_log_last_line_read_from_the_end(tmp_path: Path) -> None:
    f = tmp_path / "f.jsonl"
    big = json.dumps({"pad": "x" * 5000})
    _write(f, [big] * 50 + [json.dumps({"book": {"s": 1.0}, "t": "last"}), ""])
    assert json.loads(rp._last_line(f, block=1024))["t"] == "last"
    one = tmp_path / "one.jsonl"
    _write(one, [json.dumps({"t": "only"})])
    assert json.loads(rp._last_line(one))["t"] == "only"


def test_skips_itself_when_fresh(tmp_path: Path, monkeypatch, capsys) -> None:
    rep = tmp_path / "R.json"
    rep.write_text(json.dumps({"generated_utc": datetime.now(UTC).isoformat()}), "utf-8")
    monkeypatch.setattr(rp, "REPORT", rep)

    def boom() -> dict:
        raise AssertionError("ran although the report was fresh")

    monkeypatch.setattr(rp, "run", boom)
    assert rp.main(["--min-age-h", "6"]) == 0
    assert "skipped" in capsys.readouterr().out


def test_age_reads_the_stamp(tmp_path: Path) -> None:
    rep = tmp_path / "R.json"
    now = datetime(2026, 11, 11, 12, tzinfo=UTC)
    rep.write_text(json.dumps({"generated_utc": (now - timedelta(hours=7)).isoformat()}), "utf-8")
    assert abs(rp.report_age_h(now, rep) - 7.0) < 1e-9
    rep.write_text("{}", "utf-8")
    assert rp.report_age_h(now, rep) is None


def test_wired_as_core_hourly_leg() -> None:
    from libs.research.layers import LEG_LAYER
    from research import hourly_cycle as hc

    assert "research_pnl" in hc.CORE_LEGS
    assert LEG_LAYER["research_pnl"] == "meta"
    contracts = json.loads((REPO / "docs/research/experiment_contracts.json").read_text("utf-8"))
    assert "research_pnl" in contracts["legs"]
    src = (BASE / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_producer("research_pnl", "research/research_pnl.py", "--min-age-h", "6")' in src
