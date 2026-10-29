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


def _ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str) -> Path:
    led = tmp_path / "missed_growth.jsonl"
    led.write_text(body, "utf-8")
    monkeypatch.setattr(mg, "LEDGER", led)
    return led


def test_a_single_complete_row_without_a_newline_is_kept(tmp_path: Path,
                                                         monkeypatch: pytest.MonkeyPatch) -> None:
    led = _ledger(tmp_path, monkeypatch, '{"day": "a", "rail": "r", "value": 0.1}')
    assert mg._append_ledger([{"day": "c", "rail": "r", "value": 0.2}]) == (None, 0)
    assert [r["day"] for r in mg._rows()] == ["a", "c"]
    assert led.read_text("utf-8").endswith("\n")


def test_a_complete_last_row_without_a_newline_is_kept(tmp_path: Path,
                                                       monkeypatch: pytest.MonkeyPatch) -> None:
    _ledger(tmp_path, monkeypatch, '{"day": "a"}\n{"day": "b", "rail": "r"}')
    assert mg._append_ledger([{"day": "c"}]) == (None, 0)
    assert [r["day"] for r in mg._rows()] == ["a", "b", "c"]


def test_a_torn_line_longer_than_the_window_is_never_glued(tmp_path: Path,
                                                           monkeypatch: pytest.MonkeyPatch) -> None:
    _ledger(tmp_path, monkeypatch, '{"day": "a"}\n{"day": "b", "pad": "' + "x" * 200_000)
    assert mg._append_ledger([{"day": "c"}]) == (None, 1)
    rows, bad = mg._rows_counted()
    assert [r["day"] for r in rows] == ["a", "c"] and bad == 1


def test_a_torn_file_with_no_newline_at_all_is_counted_not_glued(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _ledger(tmp_path, monkeypatch, '{"day": "b", "pad": "' + "y" * 100_000)
    assert mg._append_ledger([{"day": "c"}]) == (None, 1)
    rows, bad = mg._rows_counted()
    assert [r["day"] for r in rows] == ["c"] and bad == 1


def test_one_bad_line_no_longer_empties_the_ledger(tmp_path: Path,
                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    _ledger(tmp_path, monkeypatch, '{"day": "a"}\nnot json\n[1]\n{"day": "b"}\n')
    rows, bad = mg._rows_counted()
    assert [r["day"] for r in rows] == ["a", "b"] and bad == 2


def test_a_failed_append_is_named_and_claims_no_sample(tmp_path: Path,
                                                       monkeypatch: pytest.MonkeyPatch) -> None:
    d = tmp_path / "dir_not_file"
    d.mkdir()
    monkeypatch.setattr(mg, "LEDGER", d)                 # opening a directory raises OSError
    why, _ = mg._append_ledger([{"day": "c"}])
    assert why and "Error" in why
    src = (_DESK / "research" / "missed_growth.py").read_text("utf-8")
    assert '"ledger_append_failed": append_failed' in src and "new = []" in src
