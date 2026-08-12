"""The carry-bleed alarm must not be ABSORBING -- a frozen ratio carries zero information (R0352).

`bleed_alert` is computed from CUMULATIVE-LIFETIME totals. A book holding no positions cannot
accrue new funding or new non-funding P&L, so with exposure at zero both terms of
``non_funding_pnl / funding_harvested`` are frozen by construction and the alarm can never clear.
Measured on the live artifact: it fired every cycle for 7+ days while ``funding_harvested`` sat
pinned at the same 113.06 and ``n_carries`` was 0.

WHAT THESE PIN, and the distinction is the whole repair: the bleed THRESHOLD is untouched and a
book with any exposure alarms exactly as it did before. Only the claim made about a book that
cannot move the number changes -- and a flat book with an UNEXPLAINED gap still fails, under a
defect id that is actually satisfiable.
"""

from __future__ import annotations

import json

import pytest

from scripts import max_audit

_VERDICT = "BLEED(inverted): non-funding PnL +2812.68 is 2488% of +113.06 funding harvest"


def _artifact(tmp_path, **over):
    """A live-shaped cashcarry_live.json. Defaults reproduce the 2026-08-12 frozen state."""
    body = {
        "funding_measured": True,
        "bleed_alert": True,
        "bleed_verdict": _VERDICT,
        "n_carries": 0,
        "deployed_notional": 0.0,
        "funding_harvested": 113.06,
        "non_funding_pnl": 2812.68,
        "fut_leg_reconciliation": {"explained": True, "measured": True, "gap": 4795.41,
                                   "rebase_usd": 4790.7},
    }
    body.update(over)
    web = tmp_path / "web"
    web.mkdir(parents=True, exist_ok=True)
    (web / "cashcarry_live.json").write_text(json.dumps(body), "utf-8")
    return body


def _run(monkeypatch, tmp_path) -> dict[str, str]:
    monkeypatch.setattr(max_audit, "ROOT", tmp_path)
    defects: list[tuple[str, str]] = []
    max_audit.check_carry_funding_measured(defects)
    return dict(defects)


def test_flat_book_with_an_attributed_gap_does_not_fire_the_economic_alarm(monkeypatch, tmp_path):
    """THE LIVE STATE. Zero exposure + a reconciliation that explains the gap = a closed episode."""
    _artifact(tmp_path)
    ids = _run(monkeypatch, tmp_path)
    assert "carry-bleed-alarm" not in ids, (
        "a book with 0 carries and 0 notional cannot accrue new funding or new non-funding P&L, "
        "so the cumulative ratio is frozen -- firing on it every cycle is a welded gate")
    assert "carry-bleed-unattributed" not in ids


def test_flat_book_with_an_UNEXPLAINED_gap_still_fails(monkeypatch, tmp_path):
    """Quietening the frozen ratio must not quieten an unexplained one. Different id, still red."""
    _artifact(tmp_path, fut_leg_reconciliation={"explained": False, "measured": True})
    ids = _run(monkeypatch, tmp_path)
    assert "carry-bleed-unattributed" in ids
    assert "UNATTRIBUTED" in ids["carry-bleed-unattributed"]


def test_an_unmeasured_reconciliation_is_not_an_explanation(monkeypatch, tmp_path):
    """explained=True on an UNMEASURED recon is a claim, not a measurement -- it must not clear."""
    _artifact(tmp_path, fut_leg_reconciliation={"explained": True, "measured": False})
    assert "carry-bleed-unattributed" in _run(monkeypatch, tmp_path)


@pytest.mark.parametrize("over", [
    {"n_carries": 3},                      # real exposure
    {"deployed_notional": 4200.0},         # notional without legs -- still exposed
])
def test_a_book_with_exposure_alarms_exactly_as_before(monkeypatch, tmp_path, over):
    """THE THRESHOLD IS UNTOUCHED. Any exposure and the original alarm fires unchanged."""
    _artifact(tmp_path, **over)
    ids = _run(monkeypatch, tmp_path)
    assert "carry-bleed-alarm" in ids
    assert "FIRING and unactioned" in ids["carry-bleed-alarm"]


@pytest.mark.parametrize("missing", ["n_carries", "deployed_notional"])
def test_absent_exposure_keys_are_not_read_as_zero(monkeypatch, tmp_path, missing):
    """ABSENCE IS NOT ZERO (WS-005). An executor predating these keys must keep the live alarm --
    'no exposure' and 'we cannot see the exposure' are opposite states."""
    body = _artifact(tmp_path)
    body.pop(missing)
    (tmp_path / "web/cashcarry_live.json").write_text(json.dumps(body), "utf-8")
    assert "carry-bleed-alarm" in _run(monkeypatch, tmp_path)


def test_a_blind_harvest_still_reports_unmeasured_first(monkeypatch, tmp_path):
    """The pre-existing UNMEASURED branch outranks all of this and is not disturbed."""
    _artifact(tmp_path, funding_measured=False)
    assert "carry-funding-unmeasured" in _run(monkeypatch, tmp_path)
