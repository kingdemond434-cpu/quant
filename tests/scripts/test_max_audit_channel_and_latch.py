"""Regression guards for the two L1.23 checks added 2026-08-05, both of which mechanise a defect
that was found BY HAND after sitting live for days.

`check_book_absorbing_state` was already mapped to L1.23 in build_enforcement_matrix.py and had
never been written -- the matrix reported the law as fenced, so nobody looked. `check_principal_
page_unanswerable` mechanises self-interrogation angle 11 (RETURN-PATH CHECK), added the day the
desk discovered its pager had been strictly one-way for three days while four decisions gating the
book sat "awaiting principal".

Both share a shape worth locking: they must be SILENT in the healthy state. A survival-class check
that cries wolf gets acked into permanent silence, which is how the real instance gets missed.
"""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import scripts.max_audit as m


def _live(tmp: Path, action: str, dd_pct: float) -> None:
    (tmp / "web").mkdir(parents=True, exist_ok=True)
    (tmp / "web/cashcarry_live.json").write_text(json.dumps(
        {"risk": {"action": action, "dd_from_peak_pct": dd_pct}}), "utf-8")


def _positions(tmp: Path, n: int, *, start: float = 10547.78, peak: float = 8690.92) -> None:
    (tmp / "data").mkdir(parents=True, exist_ok=True)
    pos = {f"SYM{i}USDT": {"spot_qty": 1.0, "spot_cost": 10.0} for i in range(n)}
    (tmp / "data/cashcarry_positions.json").write_text(json.dumps(
        {"start_futures_equity": start, "peak_combined_equity": peak, "positions": pos}), "utf-8")


class TestBookAbsorbingState:
    def test_flags_the_real_2026_08_05_lock(self, tmp_path: Path, monkeypatch) -> None:
        """The measured instance: pause_opens at -17.65% with zero positions."""
        _live(tmp_path, "pause_opens", -17.65)
        _positions(tmp_path, 0)
        monkeypatch.setattr(m, "ROOT", tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_book_absorbing_state(defects)
        assert defects and defects[0][0] == "book-absorbing-state"
        msg = defects[0][1]
        assert "ZERO positions" in msg
        # Assert the ARITHMETIC, parsed -- the gap is the number that decides whether this is
        # recoverable, so a brittle substring would let a wrong figure through unnoticed.
        gap = float(re.search(r"\$([\d,]+\.\d\d)", msg).group(1).replace(",", ""))
        peak = 10547.78                                   # max(start, peak_stored)
        assert gap == pytest.approx(0.85 * peak - (1 - 0.1765) * peak, abs=0.02)
        assert "re-arm does NOT touch it" in msg
        # must NOT read as authorisation to move a rail
        assert "principal" in msg.lower()

    def test_silent_while_the_book_holds_inventory(self, tmp_path: Path, monkeypatch) -> None:
        """A paused book that still HOLDS carries keeps harvesting funding, so equity can move and
        the rail can release itself. That is a rail working, not a latch -- and it must not page."""
        _live(tmp_path, "pause_opens", -17.65)
        _positions(tmp_path, 3)
        monkeypatch.setattr(m, "ROOT", tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_book_absorbing_state(defects)
        assert defects == []

    def test_silent_when_no_rail_is_holding_the_book(self, tmp_path: Path, monkeypatch) -> None:
        _live(tmp_path, "ok", -2.0)
        _positions(tmp_path, 0)
        monkeypatch.setattr(m, "ROOT", tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_book_absorbing_state(defects)
        assert defects == []

    def test_flatten_uses_the_ruin_bar_not_the_pause_bar(self, tmp_path: Path, monkeypatch) -> None:
        """Different bars; reporting the wrong gap would misprice the decision."""
        _live(tmp_path, "flatten", -40.0)
        _positions(tmp_path, 0)
        monkeypatch.setattr(m, "ROOT", tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_book_absorbing_state(defects)
        assert defects and "35%" in defects[0][1]


class TestPrincipalPageUnanswerable:
    def _ask(self, tmp: Path, text: str = "decisions only you can make") -> None:
        (tmp / "data").mkdir(parents=True, exist_ok=True)
        (tmp / "data/PRINCIPAL_ACTION.md").write_text(text, "utf-8")

    def _poll(self, tmp: Path, age_h: float) -> None:
        ts = (datetime.now(tz=UTC) - timedelta(hours=age_h)).isoformat()
        (tmp / "data/.reply_poll_state.json").write_text(json.dumps({"polled": ts}), "utf-8")

    def test_flags_a_dead_poller_while_an_ask_is_open(self, tmp_path: Path, monkeypatch) -> None:
        self._ask(tmp_path)
        self._poll(tmp_path, 64.9)                 # the real 2026-08-02 -> 08-05 gap
        monkeypatch.setattr(m, "ROOT", tmp_path)
        monkeypatch.setattr(m, "NOW", datetime.now(tz=UTC).timestamp())
        defects: list[tuple[str, str]] = []
        m.check_principal_page_unanswerable(defects)
        assert defects and defects[0][0] == "principal-page-unanswerable"
        assert "_poll_replies" in defects[0][1]

    def test_flags_a_missing_poll_state_entirely(self, tmp_path: Path, monkeypatch) -> None:
        self._ask(tmp_path)
        monkeypatch.setattr(m, "ROOT", tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_principal_page_unanswerable(defects)
        assert defects
        assert "DOES NOT EXIST" in defects[0][1].upper()

    def test_silent_when_the_poller_is_live(self, tmp_path: Path, monkeypatch) -> None:
        self._ask(tmp_path)
        self._poll(tmp_path, 0.05)
        monkeypatch.setattr(m, "ROOT", tmp_path)
        monkeypatch.setattr(m, "NOW", datetime.now(tz=UTC).timestamp())
        defects: list[tuple[str, str]] = []
        m.check_principal_page_unanswerable(defects)
        assert defects == []

    def test_silent_when_nothing_is_blocked_on_him(self, tmp_path: Path, monkeypatch) -> None:
        """NO ASK => NO DEFECT, even with a stone-dead poller. The check exists to stop the desk
        WAITING down a severed pipe; an idle pipe with nothing in it is not that."""
        (tmp_path / "data").mkdir(parents=True, exist_ok=True)
        (tmp_path / "data/PRINCIPAL_ACTION.md").write_text("   \n", "utf-8")
        self._poll(tmp_path, 999.0)
        monkeypatch.setattr(m, "ROOT", tmp_path)
        monkeypatch.setattr(m, "NOW", datetime.now(tz=UTC).timestamp())
        defects: list[tuple[str, str]] = []
        m.check_principal_page_unanswerable(defects)
        assert defects == []
