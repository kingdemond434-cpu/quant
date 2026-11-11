"""The three forward engines write each shadow ledger whole (Auditor condition 4, 2026-11-11)."""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK / "research"))

from atomic_ledger import write_text_atomic  # noqa: E402

ENGINES = ("shadow_forward.py", "qquant_shadow.py", "scalp_shadow.py")


@pytest.mark.parametrize("name", ENGINES)
def test_no_engine_rewrites_a_ledger_in_place(name: str) -> None:
    src = (DESK / "research" / name).read_text(encoding="utf-8")
    assert not re.search(r"\bledger\.write_text\(", src), f"{name} truncates its ledger in place"
    assert "write_text_atomic(ledger," in src


def test_a_failed_replace_leaves_the_old_ledger_whole(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "ledger_X.json"
    write_text_atomic(target, json.dumps([{"r": 1}]))
    assert json.loads(target.read_text(encoding="utf-8")) == [{"r": 1}]

    def boom(src: object, dst: object) -> None:
        raise OSError("crash mid-publish")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        write_text_atomic(target, json.dumps([{"r": 1}, {"r": 2}]))
    assert json.loads(target.read_text(encoding="utf-8")) == [{"r": 1}]
    assert not list(tmp_path.glob(".*.tmp")), "the temp file is cleaned up"
