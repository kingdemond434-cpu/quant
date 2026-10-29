"""The missed-growth ledger append (audit v3 SHOULD): one write, torn tails cut, failure named."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import missed_growth as mg  # noqa: E402


def test_a_torn_trailing_fragment_is_cut_before_the_append(tmp_path: Path,
                                                           monkeypatch: pytest.MonkeyPatch) -> None:
    led = tmp_path / "missed_growth.jsonl"
    led.write_text('{"day": "a", "rail": "r", "value": 0.1}\n{"day": "b", "ra', "utf-8")
    monkeypatch.setattr(mg, "LEDGER", led)
    assert mg._append_ledger([{"day": "c", "rail": "r", "value": 0.2}]) is None
    rows = [json.loads(x) for x in led.read_text("utf-8").splitlines()]
    assert [r["day"] for r in rows] == ["a", "c"]


def test_a_failed_append_is_named_and_claims_no_sample(tmp_path: Path,
                                                       monkeypatch: pytest.MonkeyPatch) -> None:
    d = tmp_path / "dir_not_file"
    d.mkdir()
    monkeypatch.setattr(mg, "LEDGER", d)                 # opening a directory raises OSError
    why = mg._append_ledger([{"day": "c"}])
    assert why and "Error" in why
    src = (_DESK / "research" / "missed_growth.py").read_text("utf-8")
    assert '"ledger_append_failed": append_failed' in src and "new = []" in src
