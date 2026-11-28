"""A writer killed mid-append leaves a torn last line in preregistrations.jsonl. The next card
must land on a line of its own, every reader must skip the fragment, and the ledger only grows."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from libs.research import preregistration as pr

TORN = '{"prereg_hash": "abc", "registered_utc": "2026-11-11T00:00:00+00:00", "kind": "ba'


def _torn(tmp_path: Path) -> Path:
    p = tmp_path / "preregistrations.jsonl"
    good = {"prereg_hash": "h0", "registered_utc": "2026-11-10T00:00:00+00:00", "spec_id": "s0"}
    p.write_text(json.dumps(good) + "\n" + TORN, encoding="utf-8")
    return p


def test_line_start_only_when_the_tail_is_torn(tmp_path: Path) -> None:
    p = tmp_path / "l.jsonl"
    assert pr._line_start(p) == ""  # absent
    p.write_text("", encoding="utf-8")
    assert pr._line_start(p) == ""  # empty
    p.write_text("{}\n", encoding="utf-8")
    assert pr._line_start(p) == ""
    p.write_text("{}\n{", encoding="utf-8")
    assert pr._line_start(p) == "\n"


def test_a_docket_card_after_a_torn_tail_is_readable_and_the_ledger_only_grew(
    tmp_path: Path,
) -> None:
    p = _torn(tmp_path)
    before = p.read_bytes()
    rows = [{"symbol": "XAUUSD", "family": "f_demo", "params": {"a": 1}}]
    out = pr.register_docket(rows, path=p, index={}, now=datetime(2026, 11, 11, tzinfo=UTC))
    assert out["error"] is None and out["new_specs"] == 1
    after = p.read_bytes()
    assert after.startswith(before)  # grow-only: the fragment is kept, never truncated
    idx = pr.spec_index(p)
    sid = rows[0]["spec_id"]
    assert idx[sid][1] == rows[0]["prereg_hash"]  # the new card is readable
    assert "s0" in idx


def test_a_single_card_after_a_torn_tail_is_readable(tmp_path: Path) -> None:
    p = _torn(tmp_path)
    card = {k: f"v-{k}" for k in pr.REQUIRED}
    h = pr.register(card, source="t", path=p)
    got = pr.cards(p)
    assert h in got and "h0" in got


def test_cards_skips_a_torn_line_and_keeps_reading(tmp_path: Path) -> None:
    p = tmp_path / "l.jsonl"
    p.write_text(
        json.dumps({"prereg_hash": "a"})
        + "\n"
        + TORN
        + "\n"
        + json.dumps({"prereg_hash": "b"})
        + "\n",
        encoding="utf-8",
    )
    assert set(pr.cards(p)) == {"a", "b"}


def test_cards_survives_a_torn_multibyte_character(tmp_path: Path) -> None:
    p = tmp_path / "l.jsonl"
    p.write_bytes(json.dumps({"prereg_hash": "a"}).encode() + b"\n" + '{"x": "é'.encode()[:-1])
    assert set(pr.cards(p)) == {"a"}
