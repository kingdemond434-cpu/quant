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


def _live(tmp: Path, action: str, dd_pct: float, *, fut_leg: float | None = None,
          n_carries: int = 0, gross: float = 0.0) -> None:
    """The live feed.

    `fut_leg_net` IS THE LOAD-BEARING FIELD NOW, and `dd_from_peak_pct` no longer is. The check
    used to trust the published drawdown; R0364 showed that number is measured against a
    different inception than `start_futures_equity`, so the monitor believed $13,472.67 while the
    book's own published equity was $8,682.22 -- and the error runs in the direction that makes
    an absorbing book look healthy. It now recomputes through `risk_controls.evaluate`, so these
    fixtures supply what that path actually reads. `action`/`dd_pct` are still written because the
    feed carries them and a fixture that omitted them would not resemble the real artifact.
    """
    (tmp / "web").mkdir(parents=True, exist_ok=True)
    body: dict = {"risk": {"action": action, "dd_from_peak_pct": dd_pct},
                  "n_carries": n_carries, "deployed_notional": gross}
    if fut_leg is not None:
        body["fut_leg_net"] = fut_leg
    (tmp / "web/cashcarry_live.json").write_text(json.dumps(body), "utf-8")


def _positions(tmp: Path, n: int, *, start: float = 10547.78, peak: float = 8690.92) -> None:
    (tmp / "data").mkdir(parents=True, exist_ok=True)
    pos = {f"SYM{i}USDT": {"spot_qty": 1.0, "spot_cost": 10.0} for i in range(n)}
    (tmp / "data/cashcarry_positions.json").write_text(json.dumps(
        {"start_futures_equity": start, "peak_combined_equity": peak, "positions": pos}), "utf-8")


class TestBookAbsorbingState:
    def test_flags_the_real_2026_08_05_lock(self, tmp_path: Path, monkeypatch) -> None:
        """The measured instance: a flat book held down by pause_opens.

        THE PAUSE HALF IS THE POINT. A later rewrite narrowed this check to `flatten` alone,
        which is the rarer branch -- `pause_opens` bars new opens, and on a book already holding
        nothing that is the same trap by a gentler name: no carries, no funding, so equity cannot
        rise, so the drawdown never shrinks and the pause never lifts.
        """
        from libs.risk import risk_controls
        start, peak = 10000.0, 10000.0
        eq = 0.80 * start                                  # -20%: past DD_PAUSE, short of ruin
        _live(tmp_path, "pause_opens", -20.0, fut_leg=eq - start)
        _positions(tmp_path, 0, start=start, peak=peak)
        monkeypatch.setattr(m, "ROOT", tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_book_absorbing_state(defects)

        assert defects and defects[0][0] == "book-absorbing-state"
        msg = defects[0][1]
        assert "PAUSE_OPENS" in msg
        # Assert the ARITHMETIC, parsed -- the gap decides whether this is recoverable at all, so
        # a brittle substring would let a wrong figure through unnoticed.
        gap = float(re.search(r"rise the \$([\d,]+\.\d\d)", msg).group(1).replace(",", ""))
        assert gap == pytest.approx((1 - risk_controls.DD_PAUSE) * peak - eq, abs=0.02)
        assert "re-arm does NOT touch it" in msg
        assert "principal" in msg.lower()          # must NOT read as authorisation to move a rail

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
        """Different bars AND different denominators; either one wrong misprices the decision.

        The ruin rail measures equity against INCEPTION (`risk_controls.evaluate`, dd_start =
        eq/start - 1); the pause rail measures against PEAK. Reporting the pause gap for a
        flattened book would understate what recovery costs.
        """
        from libs.risk import risk_controls
        start, peak = 10000.0, 12000.0                     # peak above start: the two bases differ
        eq = 0.55 * start                                  # -45%: past the ruin rail
        _live(tmp_path, "flatten", -45.0, fut_leg=eq - start)
        _positions(tmp_path, 0, start=start, peak=peak)
        monkeypatch.setattr(m, "ROOT", tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_book_absorbing_state(defects)

        assert defects and "35%" in defects[0][1]
        raw = re.search(r"rise the \$([\d,]+\.\d\d)", defects[0][1]).group(1)
        gap = float(raw.replace(",", ""))
        assert gap == pytest.approx((1 - risk_controls.DRAWDOWN_RUIN) * start - eq, abs=0.02), (
            "the ruin gap must be measured off inception, not off peak")


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
