"""THE WALL BEYOND FROZEN CODE, and the isolation of every generator from sealed data (W19).

The evaluator's original fence hashes the files that JUDGE. Two halves of the constitution were
outside it and are pinned here.

THE RECORDS. A ledger cannot be hashed whole -- it grows every hour -- so it is sealed by
PREFIX, and the only property that matters is the one these tests plant a lie against: the
records already written must still be there, unchanged, in the same order. A fence that only
proved "the file is bigger than it was" would pass every rewrite that also appended.

THE GENERATORS. "Sealed data never reaches a generator" is not checkable from an artifact, only
from source, and the precision is the whole point: `expression_factory` imports `LockedHoldout`
to SEAL its own tail and never opens it, which is the correct behaviour and must not be a
finding, while a single `open_lockbox()` in a proposer must be one, with the line number.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import check_immutable_evaluator as M  # noqa: E402


@pytest.fixture
def box(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A fake box: the module's ROOT and MANIFEST repointed into tmp_path, nothing tracked."""
    monkeypatch.setattr(M, "ROOT", tmp_path)
    monkeypatch.setattr(M, "MANIFEST", tmp_path / "manifest.json")
    monkeypatch.setattr(M, "APPEND_ONLY", (
        ("data/live_ledger.jsonl", "lines", "the live ledger"),
        ("reports/shadow/ledger_*.json", "rows", "the forward clocks' ledgers"),
    ))
    monkeypatch.setattr(M, "VINTAGE", (("data/cost_surface.json", "built_at", "the costs"),))
    monkeypatch.setattr(M, "IMMUTABLE", ())
    (tmp_path / "data").mkdir()
    (tmp_path / "reports" / "shadow").mkdir(parents=True)
    return tmp_path


def _seal(box: Path) -> None:
    (box / "manifest.json").write_text(json.dumps({
        "files": {}, "append_only": M.append_only_seal(), "vintage": M.vintage_seal()}), "utf-8")


def _status(path: str) -> dict[str, Any]:
    return next(r for r in M.wall_rows() if r["path"] == path)


def test_an_append_only_ledger_may_grow_and_may_not_be_rewritten(box: Path) -> None:
    led = box / "data" / "live_ledger.jsonl"
    led.write_text("\n".join(f'{{"deal": {i}}}' for i in range(4)), "utf-8")
    _seal(box)
    assert _status("data/live_ledger.jsonl")["status"] == "verified"

    led.write_text(led.read_text("utf-8") + '\n{"deal": 99}', "utf-8")
    grew = _status("data/live_ledger.jsonl")
    assert grew["status"] == "grew" and grew["records"] == 5

    # The lie a "file only got bigger" check would pass: one old record edited, one appended.
    lines = led.read_text("utf-8").split("\n")
    lines[1] = '{"deal": 1, "pl_quote": 999.0}'
    led.write_text("\n".join([*lines, '{"deal": 100}']), "utf-8")
    bad = _status("data/live_ledger.jsonl")
    assert bad["status"] == "breach" and "rewritten" in bad["why"]
    assert any("live_ledger" in f["file"] for f in M.check())


def test_a_shorter_copy_is_behind_but_a_rewritten_prefix_is_still_a_breach(box: Path) -> None:
    led = box / "data" / "live_ledger.jsonl"
    original = [f'{{"deal": {i}}}' for i in range(8)]
    led.write_text("\n".join(original), "utf-8")
    _seal(box)

    # Another host holding an older pull: fewer records, identical as far as it goes.
    led.write_text("\n".join(original[:4]), "utf-8")
    behind = _status("data/live_ledger.jsonl")
    assert behind["status"] == "behind" and behind["records"] == 4
    assert not [f for f in M.check() if "live_ledger" in f["file"]]

    # Shorter AND different where they overlap is the one thing it cannot be.
    led.write_text("\n".join(['{"deal": 0, "pl_quote": -1}', *original[1:4]]), "utf-8")
    assert _status("data/live_ledger.jsonl")["status"] == "breach"


def test_a_forward_clock_ledger_is_read_as_rows_and_its_history_is_sealed(box: Path) -> None:
    led = box / "reports" / "shadow" / "ledger_XAUUSD_asia.json"
    trades = [{"entry_time": f"2026-08-{d:02d}", "r_multiple": 0.1 * d} for d in range(1, 6)]
    led.write_text(json.dumps(trades), "utf-8")
    _seal(box)
    rel = "reports/shadow/ledger_XAUUSD_asia.json"
    assert _status(rel)["status"] == "verified"

    trades[2]["r_multiple"] = 9.9          # a losing forward trade improved after the fact
    trades.append({"entry_time": "2026-08-06", "r_multiple": 0.6})
    led.write_text(json.dumps(trades), "utf-8")
    assert _status(rel)["status"] == "breach"


def test_an_absent_record_file_is_unmeasured_and_never_reads_as_verified(box: Path) -> None:
    _seal(box)                                     # nothing on disk at all
    statuses = {r["path"]: r["status"] for r in M.wall_rows()}
    assert statuses["data/live_ledger.jsonl"] == "absent"
    assert statuses["reports/shadow/ledger_*.json"] == "absent"
    assert "verified" not in set(statuses.values())
    assert all("UNMEASURED" in r["why"] for r in M.wall_rows() if r["status"] == "absent")
    assert not M.check()                           # absence is a verdict, not a breach


def test_the_cost_surface_may_be_rebuilt_and_may_not_be_back_dated(box: Path) -> None:
    surface = box / "data" / "cost_surface.json"
    surface.write_text(json.dumps({"built_at": "2026-09-20T00:00:00+00:00", "symbols": {}}),
                       "utf-8")
    _seal(box)
    assert _status("data/cost_surface.json")["status"] == "verified"

    surface.write_text(json.dumps({"built_at": "2026-09-22T00:00:00+00:00", "symbols": {}}),
                       "utf-8")
    assert _status("data/cost_surface.json")["status"] == "rebuilt"
    assert not M.check()

    surface.write_text(json.dumps({"built_at": "2026-08-01T00:00:00+00:00", "symbols": {}}),
                       "utf-8")
    back = _status("data/cost_surface.json")
    assert back["status"] == "breach" and "BACKWARDS" in back["why"]


# ------------------------------------------------------------------ generator isolation
def _generator(path: Path, body: str, *, doc: str = "") -> None:
    """A file the desk counts as a generator: it imports the donation door."""
    path.parent.mkdir(parents=True, exist_ok=True)
    head = f'"""{doc}"""\n\n' if doc else ""
    path.write_text(head + "from research.proposer_common import donate\n\n" + body, "utf-8")


@pytest.fixture
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(M, "ROOT", tmp_path)
    monkeypatch.setattr(M, "GENERATOR_ROOTS", ("research",))
    monkeypatch.setattr(M, "EXTRA_GENERATORS", ())
    monkeypatch.setattr(M, "JUDGES", frozenset({"research/judge.py"}))
    (tmp_path / "research").mkdir()
    return tmp_path


def test_a_generator_that_opens_a_lockbox_is_caught_with_its_file_and_line(desk: Path) -> None:
    _generator(desk / "research" / "greedy.py",
               "def run(box):\n    held = box.open_lockbox()\n    return donate(held)\n")
    out = M.generator_isolation()
    assert out["scanned"] == ["research/greedy.py"]
    assert len(out["findings"]) == 1
    hit = out["findings"][0]
    assert hit["file"] == "research/greedy.py" and hit["line"] == "4"
    assert "open_lockbox" in hit["what"]


def test_sealing_your_own_tail_is_the_correct_behaviour_and_is_not_a_finding(desk: Path) -> None:
    """`expression_factory`'s real shape: import the holdout, seal with it, read only research."""
    _generator(desk / "research" / "factory.py",
               "from libs.validation.lockbox import LockedHoldout\n\n"
               "def run(bars):\n"
               "    box = LockedHoldout(bars, holdout_fraction=0.3)\n"
               "    return donate(box.research())\n")
    assert M.generator_isolation()["findings"] == []


def test_prose_about_the_holdout_is_not_a_finding_but_a_sealed_path_is(desk: Path) -> None:
    _generator(desk / "research" / "talker.py", "def run():\n    return donate([])\n",
               doc="Never reads desks/mt5/data/lockbox, and never the evidence_vault.json.")
    assert M.generator_isolation()["findings"] == []

    _generator(desk / "research" / "reacher.py",
               "def run():\n"
               '    path = "desks/mt5/data/lockbox/XAUUSD.parquet"\n'
               "    return donate(path)\n")
    hits = M.generator_isolation()["findings"]
    assert [h["file"] for h in hits] == ["research/reacher.py"]
    assert hits[0]["line"] == "4"


def test_a_judge_is_skipped_and_a_non_proposer_is_never_scanned(desk: Path) -> None:
    _generator(desk / "research" / "judge.py", "def run(box):\n    return box.open_lockbox()\n")
    (desk / "research" / "plumbing.py").write_text(
        "def run(box):\n    return box.open_lockbox()\n", "utf-8")
    out = M.generator_isolation()
    assert out["scanned"] == [] and out["findings"] == []
    assert "research/judge.py" in out["judges_skipped"]


def test_the_real_desk_is_scanned_and_is_clean_today() -> None:
    """The enumeration itself is the claim: a wall that scanned nothing would also be green."""
    out = M.generator_isolation()
    assert out["n_scanned"] >= 15, out["n_scanned"]
    assert "libs/research/generators.py" in out["scanned"]
    assert "desks/mt5/research/qd_frontier.py" in out["scanned"]
    assert "desks/mt5/research/expression_factory.py" in out["scanned"]
    assert out["unparsed"] == []
    assert out["findings"] == [], out["findings"]
