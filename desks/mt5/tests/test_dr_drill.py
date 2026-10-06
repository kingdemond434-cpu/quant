"""The daily disaster-recovery drill (`scripts/dr_drill.py`, run by ops/run_frontier_audit.cmd).

Every fixture is built in a tmp dir: a bare "origin" repo standing in for the off-box copy and a
work tree laid out like the box (`desks/mt5/data/...`). The drill must replay the journal, restore
every store from the ORIGIN REF's objects (never from the local file), count duplicate accepted
intents, and do all of it without ever touching a live terminal.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import types
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for p in (str(DESK / "scripts"), str(DESK / "research"), str(DESK), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import dr_drill  # noqa: E402
import ops_redundancy as ops  # noqa: E402

REL = "desks/mt5/data"
STORES = {f"{REL}/order_intents.jsonl": "jsonl", f"{REL}/live_ledger.jsonl": "jsonl",
          f"{REL}/decision_ledger.jsonl": "jsonl", f"{REL}/gateway_state.json": "json"}


def _jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), "utf-8")


def _intent(i: int, intended: float, minute: str, ticket: int) -> dict:
    return {"intent_id": f"i{i}", "sleeve": "gold_asia", "side": "buy", "ticket": ticket,
            "retcode": 10009, "intended": intended, "time": f"2026-09-29T{minute}:00+00:00"}


def _git(work: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(work), *args], check=True, capture_output=True)


def _box(tmp: Path) -> Path:
    """A box-shaped work tree whose stores are committed and pushed to a tmp bare origin."""
    origin, work = tmp / "origin.git", tmp / "box"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(work)], check=True)
    for k, v in (("user.email", "t@t"), ("user.name", "t"), ("commit.gpgsign", "false")):
        _git(work, "config", k, v)
    data = work / REL
    data.mkdir(parents=True)
    _jsonl(data / "order_intents.jsonl", [_intent(1, 1.0, "10:00", 11),
                                          _intent(2, 1.1, "11:00", 12)])
    _jsonl(data / "live_ledger.jsonl", [{"deal": 1, "position_id": 11, "entry_order": 11,
                                         "time": "2026-09-29T12:00:00+00:00"}])
    _jsonl(data / "decision_ledger.jsonl", [{"at": "2026-09-29T10:00:00+00:00"}])
    (data / "gateway_state.json").write_text(json.dumps({"position": [{"ticket": 12}]}), "utf-8")
    _git(work, "add", REL)
    _git(work, "commit", "-q", "-m", "box state")
    _git(work, "remote", "add", "origin", str(origin))
    _git(work, "push", "-q", "-u", "origin", "main")
    return work


@pytest.fixture
def box(tmp_path: Path) -> Path:
    return _box(tmp_path)


def _drill(work: Path, stores: dict[str, str] | None = None) -> dict:
    return dr_drill.run(data=work / REL, cwd=work, stores=stores or STORES)


def test_a_clean_box_passes_all_three_components(box):
    doc = _drill(box)
    assert doc["components"] == {"offbox_restore": "PASS", "journal_replay": "PASS",
                                 "duplicate_guard": "PASS"}
    assert doc["verdict"] == "PASS"


def test_journal_replay_rebuilds_the_open_book_and_fails_on_a_torn_line(box):
    j = _drill(box)["journal_replay"]
    assert j["intents"] == 2 and j["accepted"] == 2 and j["closing_deals"] == 1
    assert j["open_tickets_by_replay"] == ["12"] and j["open_by_gateway_state"] == 1
    with (box / REL / "order_intents.jsonl").open("a", encoding="utf-8") as fh:
        fh.write("{torn\n")
    doc = _drill(box)
    assert doc["components"]["journal_replay"] == "FAIL" and doc["verdict"] == "FAIL"


def test_the_restore_reads_the_offbox_object_not_the_local_file(box):
    # The local gateway_state is corrupted AFTER the push: the drill restores the origin's copy,
    # which still parses, so the restore passes and reports that the live file differs.
    (box / REL / "gateway_state.json").write_text("{not json", "utf-8")
    d = _drill(box)["offbox_restore"]
    assert d["ref"] == "origin/main"
    gs = d["stores"][f"{REL}/gateway_state.json"]
    assert gs["status"] == "PASS" and gs["parses"] and not gs["identical_to_live"]
    # Appended-since-push journal rows are lag, not failure: the restore is a prefix of live.
    with (box / REL / "live_ledger.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"deal": 2, "position_id": 12}) + "\n")
    ll = _drill(box)["offbox_restore"]["stores"][f"{REL}/live_ledger.jsonl"]
    assert ll["status"] == "PASS" and ll["lag_rows"] == 1 and ll["prefix_of_live"]


def test_a_rewritten_journal_or_a_store_never_pushed_is_caught(box):
    _jsonl(box / REL / "decision_ledger.jsonl", [{"at": "2026-09-29T09:00:00+00:00"}])
    doc = _drill(box)
    assert doc["components"]["offbox_restore"] == "FAIL" and doc["verdict"] == "FAIL"
    _git(box, "checkout", "--", f"{REL}/decision_ledger.jsonl")
    extra = dict(STORES, **{f"{REL}/sleeves.json": "json"})
    doc = _drill(box, extra)
    assert doc["offbox_restore"]["not_off_box"] == [f"{REL}/sleeves.json"]
    assert doc["components"]["offbox_restore"] == "DEGRADED" and doc["verdict"] == "PARTIAL"


def test_no_offbox_ref_is_unmeasured_never_a_pass(tmp_path):
    work = tmp_path / "lonely"
    subprocess.run(["git", "init", "-q", "-b", "main", str(work)], check=True)
    (work / REL).mkdir(parents=True)
    doc = _drill(work)
    assert doc["components"]["offbox_restore"] == "UNMEASURED"
    assert doc["components"]["journal_replay"] == "UNMEASURED"
    assert doc["verdict"] == "PARTIAL"


def test_the_duplicate_position_guard_fails_the_drill_and_the_exit_code(box, monkeypatch,
                                                                         tmp_path):
    rows = [_intent(1, 1.0, "10:00", 11), _intent(2, 1.1, "11:00", 12),
            _intent(3, 1.1, "11:00", 13)]                  # same sleeve/side/minute/price
    _jsonl(box / REL / "order_intents.jsonl", rows)
    _git(box, "commit", "-q", "-am", "double open")
    _git(box, "push", "-q")
    out = tmp_path / "reports" / "DR_DRILL.json"
    monkeypatch.setattr(dr_drill, "OUT", out)
    # main() runs with its defaults, pointed at the fixture box instead of this repo.
    monkeypatch.setattr(ops, "DATA", box / REL)
    monkeypatch.setattr(ops, "ROOT", box)
    assert dr_drill.main() == 1
    doc = json.loads(out.read_text("utf-8"))
    assert doc["components"]["duplicate_guard"] == "FAIL" and doc["verdict"] == "FAIL"
    assert doc["duplicate_guard"]["n_duplicates"] == 1
    assert doc["duplicate_guard"]["duplicates"][0]["n"] == 2


def test_the_drill_reads_committed_stores_and_never_a_live_terminal(box, monkeypatch):
    # A terminal module that explodes on any use: importing or touching it fails the test.
    boom = types.ModuleType("MetaTrader5")

    def _refuse(name: str):
        raise AssertionError(f"dr_drill reached the live terminal ({name})")

    boom.__getattr__ = _refuse  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "MetaTrader5", boom)
    monkeypatch.setattr(ops, "terminal_health", lambda *a, **k: _refuse("terminal_health"))
    monkeypatch.setattr(ops, "market_data_crosscheck",
                        lambda *a, **k: _refuse("market_data_crosscheck"))
    calls: list[list[str]] = []
    real_run = subprocess.run

    def spy(argv, *a, **k):
        calls.append(list(argv))
        return real_run(argv, *a, **k)

    monkeypatch.setattr(ops.subprocess, "run", spy)
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in (box / REL).iterdir()}
    doc = _drill(box)
    assert doc["verdict"] == "PASS"
    # Every subprocess is a read-only git query against the committed history.
    assert calls and all(c[0] == "git" and c[1] in {"rev-parse", "log", "show"} for c in calls)
    assert any(c[1] == "show" and c[2].startswith("origin/main:") for c in calls)
    after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
             for p in (box / REL).iterdir()}
    assert after == before, "the drill must never write a live store"
    assert set(doc["components"]) == {"offbox_restore", "journal_replay", "duplicate_guard"}


def test_the_daily_frontier_audit_runs_the_drill():
    cmd = (ROOT / "ops" / "run_frontier_audit.cmd").read_text("utf-8", errors="replace")
    assert r"desks\mt5\scripts\dr_drill.py" in cmd
