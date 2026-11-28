"""spec_index is incremental over the append-only ledger and always equals a full re-parse."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.research import preregistration as pr  # noqa: E402


def _row(sid: str, at: str, h: str) -> str:
    return json.dumps({"spec_id": sid, "registered_utc": at, "prereg_hash": h}) + "\n"


def _batch(sids: list[str], at: str, h: str) -> str:
    return json.dumps({"kind": pr.BATCH_KIND, "specs": sids, "registered_utc": at,
                       "prereg_hash": h}) + "\n"


def _full(p: Path) -> dict:
    out: dict = {}
    for ln in p.read_text("utf-8").splitlines():
        pr._fold_line(out, ln)
    return out


def _fresh(monkeypatch) -> None:
    monkeypatch.setattr(pr, "_INDEX_MEMO", {})


def test_appends_are_folded_and_equal_a_full_parse(tmp_path, monkeypatch) -> None:
    _fresh(monkeypatch)
    p = tmp_path / "preregistrations.jsonl"
    p.write_text(_row("a", "2026-01-02", "h1") + _batch(["b", "c"], "2026-01-03", "h2"), "utf-8")
    assert pr.spec_index(p) == {"a": ("2026-01-02", "h1"), "b": ("2026-01-03", "h2"),
                                "c": ("2026-01-03", "h2")}
    with p.open("a", encoding="utf-8") as fh:
        fh.write(_row("a", "2026-01-01", "h0") + _row("d", "2026-01-05", "h3"))
    assert pr.spec_index(p) == _full(p)
    assert pr.spec_index(p)["a"] == ("2026-01-01", "h0"), "earliest card wins"


def test_the_sidecar_carries_the_index_across_processes(tmp_path, monkeypatch) -> None:
    _fresh(monkeypatch)
    p = tmp_path / "preregistrations.jsonl"
    p.write_text(_row("a", "2026-01-02", "h1"), "utf-8")
    pr.spec_index(p)
    assert pr._sidecar(p).exists()
    monkeypatch.setattr(pr, "_INDEX_MEMO", {})          # a new process
    folded: list[str] = []
    real = pr._fold_line
    monkeypatch.setattr(pr, "_fold_line", lambda out, ln: (folded.append(ln), real(out, ln)))
    with p.open("a", encoding="utf-8") as fh:
        fh.write(_row("b", "2026-01-03", "h2"))
    assert pr.spec_index(p) == {"a": ("2026-01-02", "h1"), "b": ("2026-01-03", "h2")}
    assert [json.loads(x)["spec_id"] for x in folded if x.strip()] == ["b"], "only new bytes"


def test_a_rewritten_ledger_is_rebuilt_from_zero(tmp_path, monkeypatch) -> None:
    _fresh(monkeypatch)
    p = tmp_path / "preregistrations.jsonl"
    p.write_text(_row("a", "2026-01-02", "h1") + _row("b", "2026-01-03", "h2"), "utf-8")
    pr.spec_index(p)
    p.write_text(_row("z", "2026-02-02", "hz") + _row("y", "2026-02-03", "hy") + _row(
        "x", "2026-02-04", "hx"), "utf-8")                # same-or-larger size, new content
    assert pr.spec_index(p) == _full(p)
    p.write_text(_row("q", "2026-03-01", "hq"), "utf-8")  # truncated
    assert pr.spec_index(p) == {"q": ("2026-03-01", "hq")}


def test_a_torn_last_line_waits_for_its_newline(tmp_path, monkeypatch) -> None:
    _fresh(monkeypatch)
    p = tmp_path / "preregistrations.jsonl"
    line = _row("b", "2026-01-03", "h2")
    p.write_text(_row("a", "2026-01-02", "h1") + line[:20], "utf-8")
    assert pr.spec_index(p) == {"a": ("2026-01-02", "h1")}
    with p.open("a", encoding="utf-8") as fh:
        fh.write(line[20:])
    assert pr.spec_index(p) == {"a": ("2026-01-02", "h1"), "b": ("2026-01-03", "h2")}


def test_the_caller_gets_its_own_copy(tmp_path, monkeypatch) -> None:
    _fresh(monkeypatch)
    p = tmp_path / "preregistrations.jsonl"
    p.write_text(_row("a", "2026-01-02", "h1"), "utf-8")
    idx = pr.spec_index(p)
    idx["zzz"] = ("x", "y")
    assert "zzz" not in pr.spec_index(p)


def test_an_unreadable_sidecar_rebuilds(tmp_path, monkeypatch) -> None:
    _fresh(monkeypatch)
    p = tmp_path / "preregistrations.jsonl"
    p.write_text(_row("a", "2026-01-02", "h1"), "utf-8")
    pr._sidecar(p).write_text("not json", "utf-8")
    assert pr.spec_index(p) == {"a": ("2026-01-02", "h1")}


def test_an_absent_ledger_is_empty(tmp_path, monkeypatch) -> None:
    _fresh(monkeypatch)
    assert pr.spec_index(tmp_path / "nope.jsonl") == {}


def test_a_sidecar_with_wrong_types_is_ignored(tmp_path, monkeypatch) -> None:
    import json as _j
    _fresh(monkeypatch)
    p = tmp_path / "preregistrations.jsonl"
    p.write_text(_row("a", "2026-01-02", "h1"), "utf-8")
    pr.spec_index(p)
    doc = _j.loads(pr._sidecar(p).read_text("utf-8"))
    doc["index"]["evil"] = {"__reduce__": 1}
    pr._sidecar(p).write_text(_j.dumps(doc), "utf-8")
    monkeypatch.setattr(pr, "_INDEX_MEMO", {})
    assert pr.spec_index(p) == {"a": ("2026-01-02", "h1")}
