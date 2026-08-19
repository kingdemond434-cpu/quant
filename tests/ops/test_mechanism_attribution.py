"""The mechanism-attribution fence must not be ABSORBING on a flat book (R0493).

The UNATTRIBUTED ratio is built from cumulative-lifetime totals (deployed net_pnl vs the funding
mechanism term). A book holding no positions cannot move either term, so with exposure at zero the
verdict is arithmetically incapable of ever clearing -- the same frozen-ratio defect R0352 fixed in
max_audit's carry-bleed alarm, sitting unfixed in the sibling fence, in the LAW GATE.

WHAT THESE PIN, and the distinction is the whole repair: UNATTRIBUTED_FRAC is untouched and a book
with any exposure is judged exactly as before. Only the claim made about a FLAT book whose lifetime
gap the futures-leg reconciliation ATTRIBUTES (explained=True AND measured=True, structured fields,
never the verdict string) changes -- and a flat book with an UNEXPLAINED gap still fails.
"""

from __future__ import annotations

import json

import pytest
from scripts.check_mechanism_attribution import build_report

_RECON = {"explained": True, "measured": True, "gap": 4795.41, "rebase_usd": 4790.7}


def _root(tmp_path, *, live_over=None, drop=(), no_live=False):
    """A deployed-state + live-book pair. Defaults reproduce the 2026-08-12 frozen state."""
    deployed = {"net_pnl": 3093.16, "funding": 113.06, "funding_measured": True,
                "n_carries": 0, "sleeves": ["cash_and_carry (real)"]}
    (tmp_path / "research_state.json").write_text(json.dumps({"deployed": deployed}), "utf-8")
    if no_live:
        return tmp_path
    live = {"funding_measured": True, "bleed_alert": True, "n_carries": 0,
            "deployed_notional": 0.0, "funding_harvested": 113.06,
            "fut_leg_reconciliation": dict(_RECON)}
    live.update(live_over or {})
    for key in drop:
        live.pop(key, None)
    web = tmp_path / "web"
    web.mkdir(parents=True, exist_ok=True)
    (web / "cashcarry_live.json").write_text(json.dumps(live), "utf-8")
    return tmp_path


def test_flat_book_with_an_attributed_gap_reads_ATTRIBUTED(tmp_path):
    """THE LIVE STATE. Zero exposure + a reconciliation that explains the gap = closed episode."""
    rep = build_report(_root(tmp_path))
    assert rep["status"] == "ATTRIBUTED", (
        "a book with 0 carries and 0 notional cannot move either term of the cumulative ratio -- "
        "an UNATTRIBUTED verdict here is frozen by construction and can never clear (L1.43)")
    (row,) = rep["sleeves"]
    assert row["closed_episode"] is True
    assert "re-base" in row["why"]


def test_flat_book_with_an_UNEXPLAINED_gap_still_fails(tmp_path):
    """Quietening the frozen ratio must not quieten an unexplained one."""
    over = {"fut_leg_reconciliation": {"explained": False, "measured": True}}
    rep = build_report(_root(tmp_path, live_over=over))
    assert rep["status"] == "UNATTRIBUTED"
    assert "unexplained" in rep["sleeves"][0]["closed_episode_check"]


def test_an_unmeasured_reconciliation_is_not_an_explanation(tmp_path):
    """explained=True on an UNMEASURED recon is a claim, not a measurement -- it must not clear."""
    over = {"fut_leg_reconciliation": {"explained": True, "measured": False}}
    assert build_report(_root(tmp_path, live_over=over))["status"] == "UNATTRIBUTED"


@pytest.mark.parametrize("over", [
    {"n_carries": 3},                      # real exposure
    {"deployed_notional": 4200.0},         # notional without legs -- still exposed
])
def test_a_book_with_exposure_is_judged_exactly_as_before(tmp_path, over):
    """THE THRESHOLD IS UNTOUCHED. Any exposure and the original verdict stands unchanged."""
    rep = build_report(_root(tmp_path, live_over=over))
    assert rep["status"] == "UNATTRIBUTED"
    assert "exposure" in rep["sleeves"][0]["closed_episode_check"]


@pytest.mark.parametrize("missing", ["n_carries", "deployed_notional"])
def test_absent_exposure_keys_are_not_read_as_zero(tmp_path, missing):
    """ABSENCE IS NOT ZERO (WS-005). An executor predating these keys keeps the live verdict."""
    assert build_report(_root(tmp_path, drop=(missing,)))["status"] == "UNATTRIBUTED"


def test_an_absent_live_book_never_quiets_the_verdict(tmp_path):
    """No live-book artifact at all -- 'we cannot see the exposure' is not 'no exposure'."""
    rep = build_report(_root(tmp_path, no_live=True))
    assert rep["status"] == "UNATTRIBUTED"
    assert "unreadable" in rep["sleeves"][0]["closed_episode_check"]
