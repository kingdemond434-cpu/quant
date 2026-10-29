"""The backpressure full build reads only the graph lines appended since its last run.

Measured 2026-10-29: hypothesis_graph.jsonl is 3.9 GB, `_read_jsonl(births=True)` scans it twice,
and the full build last published 2026-10-03. The index must return exactly the rows the double
scan returns.
"""
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for p in (DESK, DESK / "research", DESK.parents[1]):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import gauntlet_backpressure as gb  # noqa: E402

NOW = datetime(2026, 10, 29, 12, 0, tzinfo=UTC)
SINCE = NOW - timedelta(days=gb.HORIZON_DAYS)


def _line(ident: str, day: datetime, **kw) -> str:
    return json.dumps({"id": ident, "at": day.isoformat(timespec="seconds"), **kw}) + "\n"


def _graph(path: Path, lines: list[str]) -> None:
    path.write_text("".join(lines), encoding="utf-8")


def _both(path: Path, since: datetime = SINCE, index: Path | None = None):
    a, b = {}, {}
    return (gb._read_jsonl(path, a, since=since, births=True),
            gb._read_graph_indexed(path, b, since=since, index_path=index), a, b)


def _base() -> list[str]:
    out = []
    for i in range(40):
        out.append(_line(f"h{i}", NOW - timedelta(days=30 - i), fate="born"))
    out += [_line("h5", NOW - timedelta(days=2), fate="judged"),     # born long ago: not a birth
            _line("n1", NOW - timedelta(days=3), fate="born"),
            "\n", "not json at all\n", json.dumps({"id": "nodate"}) + "\n"]
    return out


def test_the_index_returns_the_double_scans_rows(tmp_path) -> None:
    g = tmp_path / "graph.jsonl"
    _graph(g, _base())
    old, new, na, nb = _both(g)
    assert new == old and nb == na and old


def test_appended_lines_are_read_and_earlier_births_still_drop_their_ids(tmp_path) -> None:
    g = tmp_path / "graph.jsonl"
    _graph(g, _base())
    gb._read_graph_indexed(g, {}, since=SINCE)
    with g.open("a", encoding="utf-8") as fh:
        fh.write(_line("h1", NOW - timedelta(hours=5), fate="retired"))   # born 29 days ago
        fh.write(_line("n2", NOW - timedelta(hours=1), fate="born"))
    old, new, _, _ = _both(g)
    assert new == old
    assert "n2" in {r["id"] for r in new} and "h1" not in {r["id"] for r in new}


def test_an_unfinished_line_waits_for_its_newline(tmp_path) -> None:
    g = tmp_path / "graph.jsonl"
    whole = _line("n9", NOW - timedelta(hours=2))
    _graph(g, _base() + [whole[:15]])
    gb._read_graph_indexed(g, {}, since=SINCE)
    _graph(g, _base() + [whole])
    old, new, _, _ = _both(g)
    assert new == old and "n9" in {r["id"] for r in new}


def test_a_rewritten_graph_or_an_earlier_horizon_rebuilds(tmp_path) -> None:
    g = tmp_path / "graph.jsonl"
    _graph(g, _base())
    gb._read_graph_indexed(g, {}, since=SINCE)
    _graph(g, [_line("z1", NOW - timedelta(days=1))])
    old, new, _, _ = _both(g)
    assert new == old
    _graph(g, _base())
    gb._read_graph_indexed(g, {}, since=SINCE)
    earlier = SINCE - timedelta(days=10)
    old, new, _, _ = _both(g, since=earlier)
    assert new == old and len(new) > len(gb._read_jsonl(g, {}, since=SINCE, births=True))


def test_the_horizon_sidecar_only_keeps_horizon_lines(tmp_path) -> None:
    g = tmp_path / "graph.jsonl"
    _graph(g, _base())
    gb._read_graph_indexed(g, {}, since=SINCE)
    side = tmp_path / "graph.jsonl.bp_index.json.recent.jsonl"
    cut = (SINCE - timedelta(days=1)).date().isoformat()
    kept = side.read_text(encoding="utf-8").splitlines()
    assert kept and all(json.loads(k)["at"][:10] >= cut for k in kept)
    assert os.path.exists(tmp_path / "graph.jsonl.bp_index.json")
    assert gb.GRAPH_INDEX.parent.name == "data"
