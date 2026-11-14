"""decay_live.json crosses the wire, carrying an exception's type, never its text."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_decay_live_is_on_the_publish_list() -> None:
    src = (ROOT / "desks/mt5/scripts/sync_shadow_to_git.ps1").read_text(encoding="utf-8")
    assert '"desks/mt5/data/decay_live.json"' in src


def test_decay_monitor_never_formats_an_exception_message() -> None:
    src = (ROOT / "desks/mt5/research/decay_monitor.py").read_text(encoding="utf-8")
    assert not re.search(r"\{exc(!r)?\}|str\(exc\)|repr\(exc\)", src)
