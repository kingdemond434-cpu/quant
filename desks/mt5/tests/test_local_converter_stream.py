"""local_converter streams the mined corpus instead of listing it (box memory, 2026-11-04).

The converter held every mined row (limit 10,000,000) as a Python dict before reading the first:
18.5 GB of commit on the trading box. These tests pin that `_iter_rows` is lazy and yields
exactly the rows, order and limit the listed version did, so the conversion output is unchanged.
"""
from __future__ import annotations

import contextlib
import inspect
import json
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for p in (DESK, DESK.parents[1]):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from research import local_converter as lc  # noqa: E402


def _corpus(root: Path) -> None:
    (root / "minerA").mkdir(parents=True)
    (root / "minerB").mkdir(parents=True)
    (root / "minerA" / "a.jsonl").write_text(
        '{"family": "session_range_breakout", "symbols": ["XAUUSD"], "title": "london"}\n'
        '\nnot json\n{"title": "two"}\n', "utf-8")
    (root / "minerB" / "b.json").write_text(json.dumps(
        {"discoveries": [{"title": "three"}, "skip-me", {"title": "four"}]}), "utf-8")
    (root / "minerB" / "c.json").write_text(json.dumps({"rows": {"k": {"title": "five"}}}), "utf-8")


def _listed(limit: int) -> list[tuple[str, dict]]:
    """The pre-2026-11-04 list semantics, kept here as the reference."""
    out: list[tuple[str, dict]] = []
    for root in lc.SOURCES:
        for p in sorted(root.rglob("*.json")) + sorted(root.rglob("*.jsonl")):
            if len(out) >= limit:
                return out
            if p.suffix == ".jsonl":
                for ln in p.read_text("utf-8").splitlines():
                    if ln.strip():
                        with contextlib.suppress(ValueError):
                            out.append((p.parent.name, json.loads(ln)))
                        if len(out) >= limit:
                            return out
            else:
                doc = json.loads(p.read_text("utf-8"))
                got = doc if isinstance(doc, list) else (
                    doc.get("rows") or doc.get("discoveries") or doc.get("items") or [])
                if isinstance(got, dict):
                    got = list(got.values())
                for r in got:
                    if isinstance(r, dict):
                        out.append((p.parent.name, r))
                    if len(out) >= limit:
                        return out
    return out


def test_iter_rows_is_a_generator_not_a_list(tmp_path, monkeypatch) -> None:
    _corpus(tmp_path)
    monkeypatch.setattr(lc, "SOURCES", [tmp_path, tmp_path / "absent"])
    it = lc._iter_rows(10)
    assert inspect.isgenerator(it)
    assert next(it)[0] == "minerB"           # *.json files sort first, as before


def test_streamed_rows_equal_the_listed_rows_at_every_limit(tmp_path, monkeypatch) -> None:
    _corpus(tmp_path)
    monkeypatch.setattr(lc, "SOURCES", [tmp_path])
    for limit in (0, 1, 2, 3, 4, 5, 10_000_000):
        assert list(lc._iter_rows(limit)) == _listed(limit), limit


def test_convert_output_is_unchanged_by_streaming(tmp_path, monkeypatch) -> None:
    _corpus(tmp_path)
    monkeypatch.setattr(lc, "SOURCES", [tmp_path])
    monkeypatch.setattr(lc, "_known_symbols", lambda: {"XAUUSD"})
    monkeypatch.setattr(lc, "_known_families", lambda: {"session_range_breakout"})
    monkeypatch.setattr(lc, "_iter_rows", lambda limit: iter(_listed(limit)))
    ref, ref_stats = lc.convert(100)
    monkeypatch.undo()
    monkeypatch.setattr(lc, "SOURCES", [tmp_path])
    monkeypatch.setattr(lc, "_known_symbols", lambda: {"XAUUSD"})
    monkeypatch.setattr(lc, "_known_families", lambda: {"session_range_breakout"})
    got, got_stats = lc.convert(100)
    strip = [{k: v for k, v in c.items() if k != "converted_at"} for c in got]
    assert strip == [{k: v for k, v in c.items() if k != "converted_at"} for c in ref]
    assert got_stats == ref_stats and got_stats["converted"] == 1
