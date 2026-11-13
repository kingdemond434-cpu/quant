"""A FAILING task's row carries the redacted tail of the log its command writes into.

Hourly-pass idea 629 (2026-11-11): MergeDocket returned 1 for hours while a hung earlier run
held its log open, and the board said only "generic failure". These pin where the tail comes
from, that it is bounded and redacted (process_health.json is published), and that only FAILING
rows carry it.
"""

from __future__ import annotations

import importlib.util
import json
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "process_health_tail_under_test", ROOT / "ops" / "process_health.py"
)
assert _spec and _spec.loader
ph = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ph)


def test_redirect_targets_cover_the_desk_task_shapes():
    cmd = ('/d /s /c ""C:\\py\\python.exe" -W ignore "x.py" --once '
           '>> "C:\\opt\\quant\\l\\a.log" 2>&1"')
    assert ph.redirect_targets(cmd) == ["C:\\opt\\quant\\l\\a.log"]
    assert ph.redirect_targets("py -3 x.py >> logs\\b.log 2>&1", "C:\\opt\\quant") == [
        "C:\\opt\\quant\\logs\\b.log"]
    assert ph.redirect_targets("x.exe > nul 2>&1") == []
    assert ph.redirect_targets("powershell -File a.ps1 2> e.txt *> o.txt", "D:\\w") == [
        "D:\\w\\e.txt", "D:\\w\\o.txt"]
    ps = "Start-Process y -RedirectStandardError 'C:\\e.log'"
    assert ph.redirect_targets(ps) == ["C:\\e.log"]


def test_redaction_masks_secrets_and_logins_but_keeps_shas_and_dates():
    line = ("token=abcDEF123 password: hunter2 login 52345678 sha 442dfd6a8 on 20261111 "
            "key ghp_AbC123dEf456GhI789jKl012")
    out = ph.redact_line(line)
    for leaked in ("abcDEF123", "hunter2", "52345678", "ghp_AbC123dEf456GhI789jKl012"):
        assert leaked not in out
    assert "442dfd6a8" in out and "20261111" in out
    assert len(ph.redact_line("x" * 5000)) == ph.TAIL_LINE_CHARS


def test_log_tail_is_bounded_and_says_whether_the_last_run_wrote(tmp_path):
    log = tmp_path / "MT5-MergeDocket.log"
    log.write_text("".join(f"line {i} api_key=SEKRET{i}\n" for i in range(5000)), "utf-8")
    old = time.time() - 3600
    os.utime(log, (old, old))
    ran = time.strftime("%d/%m/%Y %H:%M:%S", time.localtime(time.time() - 60))
    doc = ph.log_tail(log, ran)
    assert doc["state"] == "OK" and len(doc["tail"]) == ph.TAIL_LINES
    assert doc["tail"][-1].startswith("line 4999") and "SEKRET" not in " ".join(doc["tail"])
    assert doc["written_by_last_run"] is False
    assert ph.log_tail(log, "N/A")["written_by_last_run"] is None


def test_utf16_powershell_log_is_decoded(tmp_path):
    log = tmp_path / "ps.log"
    log.write_bytes("\ufeffThe process cannot access the file\r\n".encode("utf-16-le"))
    assert ph.log_tail(log)["tail"] == ["The process cannot access the file"]


def test_failure_evidence_reports_no_log_and_reads_redirects(tmp_path):
    none = ph.failure_evidence({"TaskName": "\\Zz-NoSuchTask", "Task To Run": "a.exe"})
    assert none["state"] == "NO_LOG"
    log = tmp_path / "m.log"
    log.write_text("Traceback\nRuntimeError: boom\n", "utf-8")
    ev = ph.failure_evidence({"TaskName": "\\MT5-X", "Task To Run": f"py x.py >> {log} 2>&1",
                              "Last Run Time": "N/A"})
    assert ev["state"] == "READ" and ev["logs"][0]["tail"][-1] == "RuntimeError: boom"


def test_only_failing_rows_carry_evidence(monkeypatch, tmp_path):
    log = tmp_path / "f.log"
    log.write_text("boom\n", "utf-8")
    tasks = [
        {"TaskName": "\\MT5-Bad", "Status": "Ready", "Scheduled Task State": "Enabled",
         "Last Result": "1", "Last Run Time": "N/A", "Next Run Time": "N/A",
         "Task To Run": f"py b.py >> {log} 2>&1"},
        {"TaskName": "\\MT5-Good", "Status": "Ready", "Scheduled Task State": "Enabled",
         "Last Result": "0", "Last Run Time": "N/A", "Next Run Time": "N/A",
         "Task To Run": f"py g.py >> {log} 2>&1"},
    ]
    monkeypatch.setattr(ph, "_tasks", lambda: (tasks, "OK schtasks"))
    monkeypatch.setattr(ph, "_contracts", lambda: {})
    rows = {r["name"]: r for r in ph.build()["processes"]}
    assert rows["MT5-Bad"]["verdict"] == "FAILING"
    assert rows["MT5-Bad"]["failure_evidence"]["logs"][0]["tail"] == ["boom"]
    assert rows["MT5-Good"]["failure_evidence"] is None
    # PUBLIC FILE (Auditor SF on #1032): the log is named by its file name, and no absolute path
    # survives anywhere in the evidence, its `why` text or its tail.
    ev = rows["MT5-Bad"]["failure_evidence"]
    assert ev["logs"][0]["path"] == "f.log"
    assert str(tmp_path) not in json.dumps(ev)


def test_auditor_leak_paths_are_masked():
    fred = "0123456789abcdef0123456789abcdef"
    sha40 = "442dfd6a8" + "0" * 31
    for line, leaked in ((f"GET /series/{fred}/obs", fred),
                         ("x " + "ab" * 32, "ab" * 32),
                         ("equity 98765.43", "98765.43"),
                         ("balance=$12,345.67", "12,345.67"),
                         ("profit 512 today", "512"),
                         ("login 20512345", "20512345"),
                         ("account: 4412", "4412"),
                         ("took 3.14159 s", "3.14159")):
        assert leaked not in ph.redact_line(line), line
    kept = ph.redact_line(f"sha {sha40} short 442dfd6a8 on 20261111")
    assert sha40 in kept and "442dfd6a8" in kept and "20261111" in kept


def test_money_path_tasks_publish_no_tail(tmp_path):
    log = tmp_path / "g.log"
    log.write_text("equity 1\n", "utf-8")
    for name in ("\\MT5-Gateway", "\\MT5-FTMO-Allocator", "\\MT5-E8-OcoWatch"):
        ev = ph.failure_evidence({"TaskName": name, "Task To Run": f"py x.py >> {log} 2>&1"})
        assert ev["state"] == "WITHHELD" and "logs" not in ev
