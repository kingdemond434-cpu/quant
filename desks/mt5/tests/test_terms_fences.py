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


def test_the_shipped_registry_fences_bis_and_congress_and_nothing_is_open() -> None:
    fences = tf.load()
    assert [f["id"] for f in fences] == ["bis_speeches", "congress_trades"]
    assert "noncommercial" in fences[0]["reason"] and "noncommercial" in fences[0]["clause"]
    assert tf.fence_for("bis_speeches/discoveries_20260901_0022.json", fences)
    assert tf.fence_for(Path("central_banks") / "bis_speech_tone.jsonl", fences)
    for free in ("central_banks/official_speech_tone.jsonl", "central_banks/cb_documents.jsonl",
                 "central_banks/discoveries_20260901_0002.json", "world/bis_speeches.json"):
        assert tf.fence_for(free, fences) is None, free
    assert not any(tf.is_open(f) for f in fences)


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


def test_one_predicate_answers_for_paths_and_seats() -> None:
    desk_intel = DESK / "data" / "intelligence"
    assert tf.path_fenced(desk_intel / "central_banks" / "bis_speech_tone.jsonl")
    assert tf.path_fenced(desk_intel / "central_banks" / "cb_tone_series.jsonl")   # built from BIS
    assert tf.path_fenced(ROOT / "data" / "intelligence" / "bis_speeches" / "d.json")
    assert tf.path_fenced(desk_intel / "central_banks" / "official_speech_tone.jsonl") is None
    assert tf.path_fenced(Path("somewhere") / "bis_speech_tone.jsonl") is None   # not a tree
    assert tf.seat_fenced("bis_speeches") and tf.seat_fenced("central_banks") is None


def test_every_reader_calls_the_shared_predicate_and_keeps_no_copy() -> None:
    sites = {"research/miner_candidate_compiler.py": "terms_fences.fence_for(",
             "research/deepening_worker.py": "terms_fences.fence_for(",
             "research/nlp_event_factors.py": "terms_fences.path_fenced(",
             "research/cb_tone_screen.py": "terms_fences.path_fenced(",
             "research/news_event_stream.py": "terms_fences.seat_fenced(",
             "research/evidence_router.py": "_terms_fences.seat_fenced(",
             "side_channels/bis_speech_tone.py": "terms_fences.seat_fenced(",
             "side_channels/seed_miners.py": "terms_fences.seat_fenced("}
    for rel, call in sites.items():
        src = (DESK / rel).read_text("utf-8")
        assert call in src, rel
        assert "noncommercial purposes" not in src or rel.endswith("bis_speech_tone.py"), rel


def test_the_bis_miner_does_not_fetch_and_says_why(tmp_path, monkeypatch) -> None:
    from side_channels import seed_miners as sm

    called: list[str] = []
    monkeypatch.setattr(sm, "MINERS", {"bis_speeches": lambda: called.append("bis") or [],
                                       "other": lambda: [sm.row("other", "x", "t")]})
    monkeypatch.setattr(sm, "SOURCE_WALLS", {})
    monkeypatch.setattr(sm, "INTEL", tmp_path)
    monkeypatch.setattr(sm, "STATE", tmp_path / "seed_miners_state.json")
    written: dict[str, list[dict]] = {}
    monkeypatch.setattr(sm, "_write_rows",
                        lambda name, rows, *a, **k: written.__setitem__(name, rows))
    sm.run_and_save()
    assert called == [] and "other" in written
    row = written["bis_speeches"][0]
    assert row["verdict"] == "TERMS_FENCED" and "noncommercial" in row["title"]


def test_the_deepening_replay_skips_fenced_files(tmp_path, monkeypatch) -> None:
    from research import deepening_worker as dw

    a = tmp_path / "intelligence"
    _write(a, "bis_speeches/discoveries_1.json", [{"title": "bis"}])
    keep = _write(a, "world/discoveries_1.json", [{"title": "other"}])
    monkeypatch.setattr(dw, "INTEL_ROOTS", (a,))
    assert dw._replay_paths() == [keep]


def test_a_registry_row_cannot_narrow_a_built_in_fence(tmp_path: Path) -> None:
    reg = tmp_path / "r.json"
    for row in ({"id": "bis_speeches", "match": []},
                {"id": "bis_speeches", "match": ["bis_speeches/only_this.json"], "seats": []},
                {"id": "bis_speeches", "match": "nonsense", "open": False},
                {"id": "bis_speeches"}):
        reg.write_text(json.dumps({"fences": [row]}), "utf-8")
        fences = tf.load(reg)
        assert tf.fence_for("bis_speeches/discoveries_1.json", fences), row
        assert tf.fence_for("central_banks/bis_speech_tone.jsonl", fences), row
        assert tf.fence_for("central_banks/cb_tone_series.jsonl", fences), row
        assert tf.seat_fenced("bis_speeches", fences), row
    reg.write_text(json.dumps({"fences": [{"id": "bis_speeches", "match": ["extra/*"]}]}),
                   "utf-8")
    assert tf.fence_for("extra/x.json", tf.load(reg))          # adding is allowed


def _congress_roster(tmp_path: Path) -> Path:
    from research import free_stack_hunter as fh
    doc = json.loads(fh.ROSTER.read_text("utf-8"))
    rows = [r for r in doc["sources"] if r.get("id") == "congress_trades"]
    assert rows, "the congress_trades roster row is still there, only fenced"
    path = tmp_path / "roster.json"
    path.write_text(json.dumps({**doc, "sources": rows}), "utf-8")
    return path


def test_congress_trades_is_fenced_by_default() -> None:
    fence = tf.seat_fenced("congress_trades")
    assert fence is not None and "13107" in fence["reason"]
    assert any(f["id"] == "congress_trades" for f in tf.BUILT_IN)


def test_the_free_stack_hunter_does_not_fetch_a_fenced_source(tmp_path, monkeypatch) -> None:
    from research import free_stack_hunter as fh

    def no_fetch(*_a, **_k):  # pragma: no cover - reaching it is the failure
        raise AssertionError("a fenced source was fetched")

    monkeypatch.setattr(fh, "run_source", no_fetch)
    store = fh.Store(tmp_path)
    fh.run(store=store, roster=_congress_roster(tmp_path), fetch=no_fetch,
           only=["congress_trades"], live=False)
    cursor = json.loads(store.cursor.read_text("utf-8"))
    assert cursor["congress_trades"]["last_status"] == "REFUSED_TERMS"
    assert cursor["congress_trades"]["missed_growth"]


def test_the_free_stack_proposer_mints_nothing_from_a_fenced_source(monkeypatch) -> None:
    from research import free_stack_proposer as fp
    monkeypatch.setattr(fp, "series_exists", lambda sid: True)
    columns = {"congress_trades": {"net_all": {"hypothesis": ["US500"]}},
               "other_src": {"x": {"hypothesis": ["US500"]}}}
    roster = {"congress_trades": {"id": "congress_trades"}, "other_src": {"id": "other_src"}}
    grid, skipped = fp.build_grid(columns, roster)
    assert "terms fence congress_trades" in skipped["congress_trades"]
    assert grid and all(r.get("evidence", {}).get("source_row") != "congress_trades"
                        for r in grid)
