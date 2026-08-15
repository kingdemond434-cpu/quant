"""Live mechanism sleeves running under a DECLARED SUSPENSION of the two-stage law.

These sleeves take capital on backtest evidence alone, which L1.6 forbids. The principal suspended
that requirement explicitly and the suspension is on record in docs/research/LIVE_EXCEPTION_LEDGER
.json. Everything here pins the two properties that keep a lawful exception from decaying into a
silent default: it FAILS CLOSED without its ledger row, and its kill terms were fixed before the
first fill rather than after the first month's returns.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import scripts.run_mechanism_sleeves as M

_LEDGER = Path(__file__).resolve().parents[2] / "docs/research/LIVE_EXCEPTION_LEDGER.json"


def _row() -> dict[str, Any]:
    doc = json.loads(_LEDGER.read_text("utf-8"))
    return next(r for r in doc["exceptions"] if r["id"] == "live-mechanism-sleeves")


def test_THE_SUSPENSION_IS_ON_RECORD_WITH_ITS_ATTRIBUTION() -> None:
    """A boolean in a config says a rule is off. It does not say who turned it off, when, for what,
    or on what terms -- and six weeks later it is indistinguishable from a default."""
    r = _row()
    assert r["active"] is True
    assert r["law_suspended"].startswith("L1.6")
    assert r["granted"] and "principal" in r["granted_by"]
    assert r["principals_words"], "the instruction is quoted, not paraphrased into agreement"
    assert "weak evidence" in r["concern_stated_before_granting"], \
        "the cost must be on record as having been stated BEFORE the grant, not discovered after"


def test_IT_FAILS_CLOSED_WITHOUT_THE_LEDGER(monkeypatch: pytest.MonkeyPatch,
                                            tmp_path: Path) -> None:
    """THE PROPERTY THAT MAKES THIS AN EXCEPTION RATHER THAN A REPEAL. This module exists only
    because a standing law was suspended; an unrecorded suspension is indistinguishable from the
    law never having applied, which is how an exception becomes the default with nobody deciding."""
    monkeypatch.setattr(M, "_LEDGER", tmp_path / "absent.json")
    ok, why = M._exception_recorded()
    assert not ok and "SUSPENSION" in why
    rep = M.build()
    assert rep["exception_active"] is False
    assert rep["target_weights"] == {}, "no ledger, no capital"


def test_AN_INACTIVE_ROW_REVOKES_IT(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Revocation must be one field, and must bind on the next cycle without a code change."""
    doc = {"exceptions": [{"id": "live-mechanism-sleeves", "active": False,
                           "granted": "2026-08-15", "granted_by": "principal"}]}
    p = tmp_path / "ledger.json"
    p.write_text(json.dumps(doc), "utf-8")
    monkeypatch.setattr(M, "_LEDGER", p)
    assert not M._exception_recorded()[0]


def test_THE_KILL_RULE_PREDATES_THE_RETURNS_IT_JUDGES() -> None:
    """'If they earn they stay', decided AFTER seeing the returns, is not a rule -- it is a garden
    of forking paths with money in it: whichever sleeve looks best gets kept for a reason invented
    afterwards. A threshold is only a threshold if it predates the number it judges."""
    r = _row()["terms_fixed_before_the_first_fill"]
    assert r["kill_drawdown"] == M.KILL_DRAWDOWN < 0
    assert r["review_days"] == M.REVIEW_DAYS > 0
    assert r["clip_frac"] == M.EQUAL_CLIP_FRAC
    assert "predates" in r["why_fixed_now"]
    assert "not finish it" in r["survival_is_not_validation"], \
        "surviving a month must not be recorded as validation"


def test_THE_BACKTEST_DOES_NOT_GET_TO_ALLOCATE() -> None:
    """The principal suspended the requirement for forward evidence before going live. They did
    NOT suspend the rule against letting a gauntlet decide position SIZE -- so clips are equal and
    fixed, and no sleeve is ever sized up for performing well (III.15)."""
    assert "no sleeve is sized up" in _row()["terms_fixed_before_the_first_fill"]["equal_and_fixed"]
    assert all(s[3] for s in M.SLEEVES), "each sleeve carries declared params"
    # every sleeve gets the SAME clip; nothing in the module varies it
    src = Path(M.__file__).read_text("utf-8")
    assert "EQUAL_CLIP_FRAC" in src and "sharpe" not in src.lower().split("kill_rule")[0][-400:]


def test_THE_RAILS_WERE_NOT_SUSPENDED() -> None:
    """A suspension is scoped or it is a repeal. These are named as still binding, in the record,
    so the scope cannot quietly widen later."""
    kept = " ".join(_row()["what_was_NOT_suspended"]).lower()
    for must in ("ruin rail", "gross cap", "daily loss cap", "deadman", "auto_promotion"):
        assert must in kept, f"{must} must be named as still binding"


def test_A_GENERATOR_WITHOUT_ITS_INPUT_IS_FLAT_AND_SAYS_SO() -> None:
    """funding_stress_reversal returns zeros without funding data; intermarket_difference returns
    zeros without the reference's RANGE. 'No data' and 'no signal' are the same number and must
    never be the same report -- publishing the first as the second is WS-005 with capital behind
    it."""
    from libs.autodiscovery.generators import MarketSeries

    n = 400
    c = 100 + np.cumsum(np.random.default_rng(7).normal(0, 1, n))
    bare = MarketSeries(close=c, high=c * 1.01, low=c * 0.99, volume=np.full(n, 1e6),
                        hour=np.arange(n) % 24, ref_close=None, ref_high=None, ref_low=None,
                        funding=None)
    # SCOPED TO THE SLEEVES THAT HAVE AN EXTERNAL INPUT AT ALL. funding_stress_reversal needs a
    # funding series and intermarket_difference needs the reference's RANGE; both can be starved
    # and both must say so. `hawkes_vol_expansion` reads only OHLCV, which is never absent -- it
    # CANNOT be silently starved, and asserting it goes flat would be asserting a defect.
    needs_external = {"funding_stress_reversal", "intermarket_difference"}
    for _cls, subtype, _why, params in M.SLEEVES:
        pos = M._positions(subtype, bare, params)
        assert pos is not None, f"{subtype} must exist in this repo"
        if subtype in needs_external:
            assert not np.any(pos), f"{subtype} must degrade to FLAT without its input"


def test_A_SLEEVE_NEEDING_ONLY_OHLCV_CANNOT_BE_SILENTLY_STARVED() -> None:
    """The other half of the same property. A sleeve whose every input is always present has no
    FLAT-EVERYWHERE failure mode -- so a flat reading from it is a real market statement rather
    than a missing feed, and the two must not be conflated in either direction."""
    from libs.autodiscovery.generators import MarketSeries

    n = 600
    rng = np.random.default_rng(3)
    vol = np.where(np.arange(n) % 200 < 40, 0.05, 0.008)
    c = 100 * np.cumprod(1 + rng.normal(0.0005, 1, n) * vol)
    bare = MarketSeries(close=c, high=c * 1.01, low=c * 0.99, volume=np.full(n, 1e6),
                        hour=np.arange(n) % 24, ref_close=None, ref_high=None, ref_low=None,
                        funding=None)
    pos = M._positions("hawkes_vol_expansion", bare, {"beta": 0.2, "k": 2.0, "lookback": 20})
    assert pos is not None and np.any(pos), \
        "an OHLCV-only sleeve must produce positions on clustered volatility"
    assert set(np.unique(pos)) <= {-1.0, 0.0, 1.0}, "positions are directional, not sized here"


def test_EVERY_DECLARED_SLEEVE_HAS_A_GENERATOR_IN_THIS_REPO() -> None:
    """The four-strategy plan named `taker_flow`, which does not exist here. Shipping a sleeve
    whose generator is absent would publish an empty weight set as a market view."""
    from libs.autodiscovery.generators import GENERATORS

    have = {g.subtype for g in GENERATORS}
    for _cls, subtype, _why, _p in M.SLEEVES:
        assert subtype in have, f"{subtype} is declared live and has no generator"


def test_THE_CENSUS_CLASS_IS_THE_ONE_THE_CENSUS_ASSIGNS() -> None:
    """`funding_stress_reversal` is filed under the LIQUIDITY search family while testing
    positioning/crowding. Naming sleeves by the search family would report two mechanisms the desk
    is not running and miss the one it is."""
    from libs.research.mechanism_census import CONSTRUCTION_CLASS

    for census_class, subtype, _why, _p in M.SLEEVES:
        declared = CONSTRUCTION_CLASS.get(subtype)
        if declared is not None:
            assert declared == census_class, f"{subtype}: census says {declared}"


def test_A_SLEEVE_ARTIFACT_DECLARES_ITS_SLICE_OF_THE_ACCOUNT() -> None:
    """MEASURED LIVE 2026-08-15. These weights published 5% gross across three symbols and the
    margin executor read them as THE WHOLE BOOK -- an instruction to sell 95% of an account these
    sleeves do not own, liquidating the momentum book to fund a 5% sleeve. Nothing caught it
    except the unrelated rule that SELL legs are not placed by that script: a safety net that
    happened to be in the way, not a design.

    `book_frac` is the fix and it must be present, because its ABSENCE means 1.0 -- whole
    account -- which is correct for the momentum book and catastrophic for a sleeve."""
    rep = M.build()
    assert "book_frac" in rep, "an artifact with no book_frac is read as claiming the account"
    assert rep["book_frac"] == pytest.approx(M.EQUAL_CLIP_FRAC * len(M.SLEEVES))
    assert 0.0 < rep["book_frac"] < 1.0, "these sleeves must never claim the whole book"
    assert "90% liquidation order" in rep["book_frac_why"]


def test_WEIGHTS_ARE_SHARES_OF_THE_SLICE_NOT_OF_THE_ACCOUNT() -> None:
    """Publishing account-shares here would make the meaning of a weight depend on which file
    read it -- the executor scales by book_frac, so a weight that already accounted for the slice
    would be applied twice and the sleeve would run at a fraction of its intended size."""
    from libs.autodiscovery.generators import MarketSeries

    rep = M.build()
    if not rep["target_weights"]:
        pytest.skip("no lake series on this host -- the slice arithmetic needs a live signal")
    assert rep["gross_frac_of_slice"] <= 1.0 + 1e-9, "shares of the slice cannot exceed the slice"
    assert rep["gross_frac_of_account"] == pytest.approx(
        rep["gross_frac_of_slice"] * rep["book_frac"])
    assert rep["gross_frac_of_account"] <= rep["book_frac"] + 1e-9
    assert MarketSeries is not None


# ------------------------------------------------------------------ the kill rule, ENFORCED
def _stub_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sleeves: dict) -> Path:
    p = tmp_path / "state.json"
    p.write_text(json.dumps({"sleeves": sleeves}), "utf-8")
    monkeypatch.setattr(M, "_STATE", p)
    return p


def test_THE_KILL_RULE_IS_ENFORCED_AND_NOT_MERELY_DECLARED(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """UNTIL 2026-08-15 IT WAS A CONSTANT WITH NO READER. KILL_DRAWDOWN, REVIEW_DAYS and _STATE
    had no consumer anywhere in the repo: the ledger promised retirement below -15% and the code
    would have traded the sleeve to zero. That is III.16 on the SAFETY half of an exception to a
    standing law -- the half whose absence is invisible exactly while things are going well."""
    from datetime import UTC, datetime, timedelta

    _stub_state(tmp_path, monkeypatch, {
        "relative_value_convergence": {
            "inception": (datetime.now(tz=UTC) - timedelta(days=3)).isoformat(),
            "marks": {"BTCUSDT": 100.0}, "weights": {"BTCUSDT": 1.0}}})
    rep = {"sleeves": [{"census_class": "relative_value_convergence", "state": "LIVE",
                        "symbols": {"BTCUSDT": 1.0}}], "target_weights": {"BTCUSDT": 1.0}}
    out = M._track(rep, {"BTCUSDC": 80.0})            # -20%, past the -15% kill
    row = out["sleeves"][0]
    assert row["state"] == "RETIRED"
    assert row["return_since_inception"] == pytest.approx(-0.20)
    assert "not renegotiable" in row["why"]
    assert out["target_weights"] == {}, "a retired sleeve must publish no weights"


def test_A_RETIREMENT_IS_PERMANENT(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A sleeve that recovers after breaching does not come back. The threshold judged it once."""
    _stub_state(tmp_path, monkeypatch, {
        "relative_value_convergence": {"retired": True, "retired_why": "killed at -20%"}})
    rep = {"sleeves": [{"census_class": "relative_value_convergence", "state": "LIVE",
                        "symbols": {"BTCUSDT": 1.0}}], "target_weights": {"BTCUSDT": 1.0}}
    out = M._track(rep, {"BTCUSDC": 1e6})             # spectacular recovery, irrelevant
    assert out["sleeves"][0]["state"] == "RETIRED"


def test_THE_REVIEW_TEST_BINDS_ONLY_AFTER_ITS_DAYS(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-negative at REVIEW_DAYS. A small loss on day 3 is noise; the same loss at 30 days is
    the pre-registered answer."""
    from datetime import UTC, datetime, timedelta

    for age, expect in ((3, "LIVE"), (M.REVIEW_DAYS + 1, "RETIRED")):
        _stub_state(tmp_path, monkeypatch, {
            "relative_value_convergence": {
                "inception": (datetime.now(tz=UTC) - timedelta(days=age)).isoformat(),
                "marks": {"BTCUSDT": 100.0}, "weights": {"BTCUSDT": 1.0}}})
        rep = {"sleeves": [{"census_class": "relative_value_convergence", "state": "LIVE",
                            "symbols": {"BTCUSDT": 1.0}}], "target_weights": {"BTCUSDT": 1.0}}
        out = M._track(rep, {"BTCUSDC": 98.0})        # -2%: inside the kill, negative at review
        assert out["sleeves"][0]["state"] == expect, f"age {age}d"


def test_UNREADABLE_PRICES_CANNOT_TRIP_THE_KILL(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty mark set must never present as a flat -- or worse, a catastrophic -- return. A
    venue outage retiring every sleeve at once is the failure mode of a kill rule that treats
    absence as a measurement."""
    from datetime import UTC, datetime, timedelta

    _stub_state(tmp_path, monkeypatch, {
        "relative_value_convergence": {
            "inception": (datetime.now(tz=UTC) - timedelta(days=90)).isoformat(),
            "marks": {"BTCUSDT": 100.0}, "weights": {"BTCUSDT": 1.0}}})
    rep = {"sleeves": [{"census_class": "relative_value_convergence", "state": "LIVE",
                        "symbols": {"BTCUSDT": 1.0}}], "target_weights": {"BTCUSDT": 1.0}}
    out = M._track(rep, {})                            # venue unreadable
    assert out["sleeves"][0]["state"] == "LIVE"
    assert "UNMEASURED" in out["sleeves"][0]["tracking"]
    assert out["target_weights"] == {"BTCUSDT": 1.0}


def test_THE_MEASURE_DECLARES_THAT_IT_FLATTERS(tmp_path: Path,
                                               monkeypatch: pytest.MonkeyPatch) -> None:
    """Marking published weights excludes fees, slippage and borrow, so it is optimistic. The
    direction is the safe one -- a kill it trips is conservative because the realised book did
    worse -- and it must never be read the other way, as evidence for KEEPING a sleeve."""
    p = _stub_state(tmp_path, monkeypatch, {})
    M._track({"sleeves": [], "target_weights": {}}, {})
    doc = json.loads(p.read_text("utf-8"))
    assert "EXCLUDING fees" in doc["measure"]
    assert "Never used to justify KEEPING" in doc["measure"]
    assert doc["kill_drawdown"] == M.KILL_DRAWDOWN
