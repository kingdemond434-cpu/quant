"""A source whose terms forbid commercial use does not reach the candidate compiler, and can
only be reopened with the permitting clause in hand."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import miner_candidate_compiler as mc  # noqa: E402
from research import terms_fences as tf  # noqa: E402


def _write(root: Path, rel: str, rows: list[dict]) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if rel.endswith(".jsonl"):
        path.write_text("".join(json.dumps(r) + "\n" for r in rows), "utf-8")
    else:
        path.write_text(json.dumps({"discoveries": rows}), "utf-8")
    return path


@pytest.fixture
def roots(tmp_path, monkeypatch):
    a, b = tmp_path / "desk_intel", tmp_path / "repo_intel"
    a.mkdir()
    b.mkdir()
    monkeypatch.setattr(mc, "INTEL_ROOTS", (a, b))
    return a, b


def _titles() -> set[str]:
    return {str(r.get("title")) for _, r in mc.recent_rows(mc.datetime.now(tz=mc.UTC))}


def test_the_shipped_registry_fences_bis_and_nothing_is_open() -> None:
    fences = tf.load()
    assert [f["id"] for f in fences] == ["bis_speeches"]
    assert "noncommercial" in fences[0]["reason"] and "noncommercial" in fences[0]["clause"]
    assert tf.fence_for("bis_speeches/discoveries_20260901_0022.json", fences)
    assert tf.fence_for(Path("central_banks") / "bis_speech_tone.jsonl", fences)
    for free in ("central_banks/official_speech_tone.jsonl", "central_banks/cb_documents.jsonl",
                 "central_banks/discoveries_20260901_0002.json", "world/bis_speeches.json"):
        assert tf.fence_for(free, fences) is None, free


def test_bis_rows_are_parked_counted_and_left_on_disk(roots) -> None:
    a, b = roots
    p1 = _write(a, "bis_speeches/discoveries_1.json", [{"title": "bis one", "symbol": "EURUSD"}])
    p2 = _write(b, "central_banks/bis_speech_tone.jsonl", [{"title": "bis tone"}])
    _write(a, "central_banks/official_speech_tone.jsonl", [{"title": "fed own site"}])
    _write(a, "world/discoveries_1.json", [{"title": "other", "symbol": "XAUUSD"}])
    assert _titles() == {"fed own site", "other"}
    parked = mc._LAST_INTAKE["terms_fenced"]["bis_speeches"]
    assert parked["files_parked"] == 2 and parked["bytes_parked"] > 0
    assert "noncommercial" in parked["reason"] and parked["missed_growth"]
    assert p1.exists() and p2.exists()                      # parked, never deleted


def test_a_missing_or_emptied_registry_still_fences_bis(tmp_path: Path) -> None:
    for body in (None, "not json", json.dumps({"fences": []})):
        reg = tmp_path / "r.json"
        if body is None:
            reg.unlink(missing_ok=True)
        else:
            reg.write_text(body, "utf-8")
        fences = tf.load(reg)
        assert tf.fence_for("bis_speeches/x.json", fences) is not None, body


def test_reopening_needs_the_flag_and_the_pasted_clause(tmp_path: Path) -> None:
    reg = tmp_path / "r.json"
    row = {"id": "bis_speeches", "match": ["bis_speeches/*"], "reason": "x"}
    for extra in ({"open": True}, {"open": True, "permit_clause": "ok"},
                  {"open": "true", "permit_clause": "commercial use is permitted with credit"},
                  {"permit_clause": "commercial use is permitted with credit"}):
        reg.write_text(json.dumps({"fences": [{**row, **extra}]}), "utf-8")
        assert tf.fence_for("bis_speeches/x.json", tf.load(reg)) is not None, extra
    reg.write_text(json.dumps({"fences": [{
        **row, "open": True, "permit_clause": "commercial use is permitted with credit"}]}),
        "utf-8")
    assert tf.fence_for("bis_speeches/x.json", tf.load(reg)) is None
