"""The box publish list carries no absolute money, account label, host or path (Auditor HOLD on
#639, 2026-11-13), and the daily chain's published mirror carries verdicts, never free text."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SYNC = ROOT / "desks" / "mt5" / "scripts" / "sync_shadow_to_git.ps1"
sys.path.insert(0, str(ROOT / "desks" / "mt5" / "research"))
sys.path.insert(0, str(ROOT / "desks" / "mt5"))

#: Reports that carry equity, balances, account labels, hosts or paths: never on the wire.
NEVER = ("E8_GOLD.json", "E8_EXEC.json", "FTMO_ACCOUNT_STATE.json", "pf_allocation.json",
         "DISK_CENSUS.json", "MATH_LAB.json", "PRODUCTIVITY_CENSUS.json",
         "weak_signal_compiler.json", "data/daily_cycle_state.json",
         "data/decay_live.json")


def _report_paths() -> list[str]:
    src = SYNC.read_text("utf-8", errors="ignore")
    start = src.index("$reportPaths = @(")
    block = src[start:src.index("\n)", start)]
    return re.findall(r'^\s*"([^"]+)"', block, flags=re.M)


def test_the_list_parses() -> None:
    assert len(_report_paths()) >= 20


@pytest.mark.parametrize("name", NEVER)
def test_money_host_and_path_reports_are_not_published(name: str) -> None:
    assert not any(p.endswith(name) for p in _report_paths()), name


def test_the_redacted_mirror_is_published() -> None:
    assert "desks/mt5/reports/DAILY_CYCLE_STATE.json" in _report_paths()


def test_stamp_view_keeps_verdicts_and_drops_free_text() -> None:
    import daily_cycle as dc
    doc = {"last_run": "2026-11-13",
           "last_progress": {"at": "2026-11-13T05:00:00+00:00", "pid": 4242},
           "chain_lock": {"state": "held", "pid": 4242,
                          "error": r"PermissionError: C:\Users\someone\lock"},
           "steps": {"refresh": {"ok": True, "rc": 0, "secs": 12.5},
                     "shadow": {"ok": False,
                                "error": r"FileNotFoundError: C:\opt\quant\x on HOST-1"}}}
    v = dc.stamp_view(doc)
    text = repr(v)
    assert "C:\\" not in text and "HOST-1" not in text and "someone" not in text
    assert v["steps"]["refresh"] == {"ok": True, "rc": 0, "secs": 12.5}
    assert v["steps"]["shadow"] == {"ok": False, "error_class": "FileNotFoundError"}
    assert v["chain_lock_error_class"] == "PermissionError"
    assert v["last_run"] == "2026-11-13"
    assert "pid" not in text
