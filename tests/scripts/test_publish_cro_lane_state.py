"""K6: the noon lane's checkpoint and log tail reach origin, scrubbed (2026-11-17)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import publish_cro_lane_state as pub  # noqa: E402


def _run(tmp_path: Path, state: dict | None, log: list[str] | None, tail: int = 80) -> dict:
    sp, lp, out = tmp_path / "cycle_state_noon.json", tmp_path / "cycle_noon.log", tmp_path / "o.json"
    if state is not None:
        # The launcher writes with PowerShell 5.1's BOM.
        sp.write_bytes(b"\xef\xbb\xbf" + json.dumps(state).encode())
    if log is not None:
        lp.write_text("\r\n".join(log) + "\r\n", "utf-8")
    assert pub.main(["--state", str(sp), "--log", str(lp), "--out", str(out),
                     "--tail", str(tail)]) == 0
    return json.loads(out.read_text("utf-8"))


def test_an_early_exit_is_read_from_the_log(tmp_path: Path) -> None:
    doc = _run(tmp_path, {"lane": "noon", "status": "DONE", "date": "2026-11-16", "pid": 4242},
               ["2026-11-17T12:00:01.0+00:00 [noon] cycle start (Dublin 2026-11-17 12:00)",
                "2026-11-17T12:00:04.0+00:00 [noon] lease NOT acquired (HELD) -- refusing",
                "2026-11-17T12:00:04.1+00:00 [noon] launcher exit rc=5"])
    assert doc["verdict"] == "FAILED" and doc["last_rc"] == 5 and doc["last_rc_from"] == "log"
    assert "pid" not in doc["state"] and doc["state"]["status"] == "DONE"
    assert len(doc["log_tail"]) == 3


def test_the_state_is_the_fallback_and_absence_is_unmeasured(tmp_path: Path) -> None:
    doc = _run(tmp_path, {"lane": "noon", "status": "RUNNING", "last_exit": 1}, None)
    assert doc["verdict"] == "FAILED" and doc["last_rc"] == 1 and doc["log_status"] == "ABSENT"
    empty = tmp_path / "empty"
    empty.mkdir()
    doc = _run(empty, None, None)
    assert doc["verdict"] == "UNMEASURED" and doc["state_status"] == "ABSENT"


def test_secrets_paths_hosts_and_money_are_scrubbed(tmp_path: Path) -> None:
    doc = _run(tmp_path, {"lane": "noon", "status": "RUNNING", "report": "equity 12,345.67",
                          "server": "Broker-Live", "binding_constraint": r"C:\opt\quant\x.py"},
               [r"2026-11-17T12:00:01+00:00 [noon] agent C:\Users\Administrator\.local\bin\claude.exe",
                "2026-11-17T12:00:02+00:00 [noon] api_key=sk-ant-abcdefghijklmnop on vmi3571445",
                "2026-11-17T12:00:03+00:00 [noon] read data/secrets/keys.env from 10.1.2.3",
                "2026-11-17T12:30:00+00:00 [noon] cycle end rc=0 after 30 min"])
    blob = json.dumps(doc)
    for leak in ("12,345", "Broker-Live", r"C:\\opt", "Administrator", "sk-ant-abc",
                 "vmi3571445", "keys.env", "10.1.2.3"):
        assert leak not in blob, leak
    assert doc["verdict"] == "OK" and doc["last_rc"] == 0


def test_only_the_last_n_lines_are_published(tmp_path: Path) -> None:
    lines = [f"2026-11-17T12:00:{i:02d}+00:00 [noon] line {i}" for i in range(50)]
    doc = _run(tmp_path, None, lines, tail=10)
    assert len(doc["log_tail"]) == 10 and doc["log_tail"][-1].endswith("line 49")
