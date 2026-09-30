"""Tier-1 audit #19: journal replay, off-box restore drill, duplicate-position count, market-data
cross-check and terminal health -- each measured, each UNMEASURED when it cannot be."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for p in (str(DESK / "research"), str(DESK), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import ops_redundancy as ops  # noqa: E402


def _jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), "utf-8")


def _journal(tmp: Path, dup: bool = False) -> None:
    intents = [{"intent_id": "i1", "sleeve": "s", "side": "buy", "ticket": 11, "retcode": 10009,
                "intended": 1.0, "time": "2026-09-29T10:00:00+00:00"},
               {"intent_id": "i2", "sleeve": "s", "side": "buy", "ticket": 12, "retcode": 10009,
                "intended": 1.1, "time": "2026-09-29T11:00:00+00:00"}]
    if dup:
        intents.append({"intent_id": "i3", "sleeve": "s", "side": "buy", "ticket": 13,
                        "retcode": 10009, "intended": 1.1, "time": "2026-09-29T11:00:30+00:00"})
    _jsonl(tmp / "order_intents.jsonl", intents)
    _jsonl(tmp / "live_ledger.jsonl", [{"deal": 1, "position_id": 11, "entry_order": 11,
                                        "r_multiple": 1.0, "time": "2026-09-29T12:00:00+00:00"}])
    _jsonl(tmp / "decision_ledger.jsonl", [{"at": "2026-09-29T10:00:00+00:00"}])
    (tmp / "gateway_state.json").write_text(json.dumps({"position": [{"ticket": 12}]}), "utf-8")


def test_journal_replay_reconstructs_the_open_book(tmp_path):
    _journal(tmp_path)
    j = ops.journal_replay(tmp_path)
    assert j["status"] == "PASS" and j["duplicate_intent_ids"] == 0
    assert j["open_by_replay"] == 1 and j["open_by_gateway_state"] == 1


def test_journal_replay_fails_on_a_torn_line(tmp_path):
    _journal(tmp_path)
    with (tmp_path / "order_intents.jsonl").open("a", encoding="utf-8") as fh:
        fh.write("{torn\n")
    assert ops.journal_replay(tmp_path)["status"] == "FAIL"


def test_absent_journal_is_unmeasured(tmp_path):
    assert ops.journal_replay(tmp_path)["status"] == "UNMEASURED"
    assert ops.duplicate_guard(tmp_path)["status"] == "UNMEASURED"


def test_duplicate_guard_counts_a_double_open(tmp_path):
    _journal(tmp_path)
    assert ops.duplicate_guard(tmp_path)["status"] == "PASS"
    _journal(tmp_path, dup=True)
    d = ops.duplicate_guard(tmp_path)
    assert d["status"] == "FAIL" and d["n_duplicates"] == 1


def _repo(tmp: Path) -> Path:
    """A repo with an 'origin' remote-tracking copy one commit behind the live file."""
    origin = tmp / "origin.git"
    work = tmp / "work"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(work)], check=True)
    for k, v in (("user.email", "t@t"), ("user.name", "t"), ("commit.gpgsign", "false")):
        subprocess.run(["git", "-C", str(work), "config", k, v], check=True)
    (work / "j.jsonl").write_text('{"a": 1}\n', "utf-8")
    (work / "s.json").write_text('{"x": 1}', "utf-8")
    subprocess.run(["git", "-C", str(work), "add", "j.jsonl", "s.json"], check=True)
    subprocess.run(["git", "-C", str(work), "commit", "-q", "-m", "c1"], check=True)
    subprocess.run(["git", "-C", str(work), "remote", "add", "origin", str(origin)], check=True)
    subprocess.run(["git", "-C", str(work), "push", "-q", "-u", "origin", "main"], check=True)
    return work


def test_restore_drill_restores_from_the_offbox_copy(tmp_path):
    work = _repo(tmp_path)
    with (work / "j.jsonl").open("a", encoding="utf-8") as fh:
        fh.write('{"a": 2}\n')                         # the live file has grown since the push
    d = ops.restore_drill({"j.jsonl": "jsonl", "s.json": "json", "missing.json": "json"},
                          cwd=work)
    assert d["ref"] == "origin/main"
    assert d["stores"]["j.jsonl"]["status"] == "PASS"
    assert d["stores"]["j.jsonl"]["lag_rows"] == 1 and d["stores"]["j.jsonl"]["prefix_of_live"]
    assert d["stores"]["missing.json"]["status"] == "NOT_OFF_BOX"
    assert d["status"] == "DEGRADED"


def test_restore_drill_fails_when_the_journal_was_rewritten(tmp_path):
    work = _repo(tmp_path)
    (work / "j.jsonl").write_text('{"a": 9}\n', "utf-8")    # history rewritten, not appended
    d = ops.restore_drill({"j.jsonl": "jsonl"}, cwd=work)
    assert d["stores"]["j.jsonl"]["status"] == "FAIL" and d["status"] == "FAIL"


def test_crosscheck_passes_close_prices_and_fails_a_bad_feed(tmp_path, monkeypatch):
    monkeypatch.setattr(ops, "XCHECK_CACHE", tmp_path / "x.json")
    days = [f"2026-09-{d:02d}" for d in range(10, 20)]
    venue = {d: 1.1 for d in days}
    ok = ops.market_data_crosscheck(venue=lambda s: venue,
                                    independent=lambda s: ({d: 1.1005 for d in days}, "t"))
    assert ok["status"] == "PASS"
    (tmp_path / "x.json").unlink()
    bad = ops.market_data_crosscheck(venue=lambda s: venue,
                                     independent=lambda s: ({d: 1.2 for d in days}, "t"))
    assert bad["status"] == "FAIL"
    (tmp_path / "x.json").unlink()
    none = ops.market_data_crosscheck(venue=lambda s: {}, independent=lambda s: ({}, "none"))
    assert none["status"] == "UNMEASURED" and not (tmp_path / "x.json").exists()


def test_terminal_health_is_unmeasured_off_the_box(monkeypatch, tmp_path):
    monkeypatch.setattr(ops, "GATEWAY_STATE", tmp_path / "none.json")
    monkeypatch.setattr(ops, "GATEWAY_LOCK", tmp_path / "none.lock")
    monkeypatch.setattr(ops, "REBOOT_DRILL", tmp_path / "none.json")
    monkeypatch.setattr(ops, "STALL_WATCH", (tmp_path / "none.json",))
    t = ops.terminal_health()
    try:
        import MetaTrader5  # type: ignore[import-not-found]  # noqa: F401
    except ImportError:
        assert t["status"] == "UNMEASURED"
    assert t["reboot_drill"]["verdict"] == "UNMEASURED"
