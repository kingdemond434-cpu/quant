"""K6: the noon lane's exits reach origin as parsed fields, and no free text does (2026-11-18)."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import publish_cro_lane_state as pub  # noqa: E402


def _run(tmp_path: Path, state: dict | None, log: list[str] | None, events: int = 20) -> dict:
    sp, lp = tmp_path / "cycle_state_noon.json", tmp_path / "cycle_noon.log"
    out = tmp_path / "o.json"
    if state is not None:
        # The launcher writes with PowerShell 5.1's BOM.
        sp.write_bytes(b"\xef\xbb\xbf" + json.dumps(state).encode())
    if log is not None:
        lp.write_text("\r\n".join(log) + "\r\n", "utf-8")
    assert pub.main(["--state", str(sp), "--log", str(lp), "--out", str(out),
                     "--events", str(events)]) == 0
    return json.loads(out.read_text("utf-8"))


def test_an_early_exit_is_read_from_the_log(tmp_path: Path) -> None:
    doc = _run(tmp_path, {"lane": "noon", "status": "DONE", "date": "2026-11-16", "pid": 4242},
               ["2026-11-17T12:00:01.0+00:00 [noon] cycle start (Dublin 2026-11-17 12:00)",
                "2026-11-17T12:00:04.0+00:00 [noon] lease NOT acquired (HELD) -- refusing",
                "2026-11-17T12:00:04.1234567+00:00 [noon] launcher exit rc=5"])
    assert doc["verdict"] == "FAILED" and doc["last_rc"] == 5 and doc["last_rc_from"] == "log"
    assert doc["last_rc_at"] == "2026-11-17T12:00:04.123456+00:00"
    assert "pid" not in doc["state"] and doc["state"]["status"] == "DONE"
    assert doc["exit_events"] == [{"at": "2026-11-17T12:00:04.123456+00:00",
                                   "event": "launcher_exit", "rc": 5}]
    assert doc["log_lines_read"] == 3 and "log_tail" not in doc


def test_the_state_is_the_fallback_and_absence_is_unmeasured(tmp_path: Path) -> None:
    doc = _run(tmp_path, {"lane": "noon", "status": "RUNNING", "last_exit": 1}, None)
    assert doc["verdict"] == "FAILED" and doc["last_rc"] == 1 and doc["log_status"] == "ABSENT"
    empty = tmp_path / "empty"
    empty.mkdir()
    doc = _run(empty, None, None)
    assert doc["verdict"] == "UNMEASURED" and doc["state_status"] == "ABSENT"


#: Every string an artifact may carry: fixed vocabulary, a re-formatted timestamp or date, the
#: two fixed source paths, and the fixed-format verdict sentences.
_TS = re.compile(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}(\.\d{1,6})?\+00:00)?$")
_FIXED = {"noon", "midnight", "DONE", "RUNNING", "PRESENT", "ABSENT", "UNREADABLE", "OK",
          "FAILED", "UNMEASURED", "log", "state.last_exit", "state.status", "none",
          "launcher_exit", "cycle_end", "desks/mt5/data/cycle_state_noon.json",
          "desks/mt5/logs/cycle_noon.log",
          "parsed fields only: no log line, message or checkpoint text is copied",
          "no launcher exit line in the log and no exit in the checkpoint"}
_WHY = re.compile(r"^last (noon|midnight) launch exited (0|rc=-?\d+) \([a-z_.]+\)$")
_KEYS = {"started_at", "finished_at", "last_exit", "minutes", "resumed", "lease_epoch",
         "completed", "work_items", "lane", "status", "date"}


def _strings(node: Any, path: str = "") -> list[tuple[str, str]]:
    if isinstance(node, str):
        return [(path, node)]
    if isinstance(node, list):
        return [s for i, v in enumerate(node) for s in _strings(v, f"{path}[{i}]")]
    if isinstance(node, dict):
        return [s for k, v in node.items() for s in _strings(v, f"{path}.{k}")]
    return []


def test_no_free_text_from_the_log_or_checkpoint_reaches_the_artifact(tmp_path: Path) -> None:
    """MF1: the log and checkpoint are full of prose, secrets, paths, hosts and money; the
    artifact's every string value is a fixed token, a re-formatted timestamp or a fixed-format
    sentence, so NOTHING the box wrote as text is published -- scrubbed or otherwise."""
    poison = ("PROSE-CANARY equity 12,345.67 Broker-Live C:\\opt\\quant sk-ant-abcdefghijklmnop "
              "vmi3571445 data/secrets/keys.env 10.1.2.3 Exception: boom")
    doc = _run(tmp_path, {"lane": "noon", "status": "RUNNING", "report": poison,
                          "server": "Broker-Live", "binding_constraint": poison, "why": poison,
                          "controller": poison, "research_supervisor": {"note": poison},
                          "work_items": [poison, poison], "completed": [poison],
                          "started_at": poison, "minutes": poison, "date": poison,
                          "last_exit": 4},
               [r"2026-11-17T12:00:01+00:00 [noon] agent C:\Users\Administrator\bin\x.exe",
                f"2026-11-17T12:00:02+00:00 [noon] FATAL: agent invocation raised: {poison}",
                f"2026-11-17T12:00:03+00:00 [noon] {poison}",
                f"2026-11-17T12:00:03+00:00 [noon] launcher exit rc=4 {poison}",
                f"{poison} launcher exit rc=9",
                "2026-11-17T12:30:00+00:00 [noon] cycle end rc=0 after 30 min"])
    blob = json.dumps(doc)
    for leak in ("CANARY", "12,345", "Broker-Live", "opt", "Administrator", "sk-ant",
                 "vmi3571445", "keys.env", "10.1.2.3", "Exception", "boom"):
        assert leak not in blob, leak
    for where, s in _strings(doc):
        if where == ".at":
            continue  # the build's own clock
        assert s in _FIXED or s in _KEYS or _TS.match(s) or _WHY.match(s), (where, s)
    # Only the two exact launcher lines parse; a poisoned trailer or prefix is not an exit line.
    assert doc["exit_events"] == [{"at": "2026-11-17T12:30:00+00:00", "event": "cycle_end",
                                   "rc": 0, "minutes": 30}]
    assert doc["verdict"] == "OK" and doc["last_rc"] == 0
    st = doc["state"]
    assert set(st) <= _KEYS | {"completed_count", "work_items_count"}
    assert st["work_items_count"] == 2 and st["completed_count"] == 1 and st["last_exit"] == 4
    assert st["started_at"] is None and st["minutes"] is None and st["date"] is None
    assert {"started_at", "minutes", "date"} <= set(doc["state_rejected"])
    assert doc["state_keys_withheld"] == 6  # report server binding why controller supervisor


def test_only_the_last_n_exits_are_published(tmp_path: Path) -> None:
    lines = [f"2026-11-17T12:00:{i:02d}+00:00 [noon] launcher exit rc={i}" for i in range(50)]
    doc = _run(tmp_path, None, lines, events=10)
    assert len(doc["exit_events"]) == 10 and doc["exit_events"][-1]["rc"] == 49
    assert doc["exit_events_found"] == 50 and doc["last_rc"] == 49
