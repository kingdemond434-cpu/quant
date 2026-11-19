"""The E8 book cannot turn a stale or quarantined certificate into an order candidate."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for path in (str(DESK), str(DESK / "research"), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from prop import e8_book  # noqa: E402
from prop import e8_executor  # noqa: E402
import admission_integrity  # noqa: E402
import kelly_survival  # noqa: E402


class _Gate:
    alarm = {"blocks": False}

    def replication(self, cert: str, fingerprint: str) -> tuple[str, str]:
        assert fingerprint == "frozen-spec"
        return (("MISMATCH", "independent rebuild disagrees") if cert == "bad" else
                ("REPLICATED", "independent rebuild agrees"))


def test_e8_admission_requires_replication_and_honours_principal_exclusions(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = tmp_path / "CERT_BOOK_LIVE.json"
    config.write_text(json.dumps({"enabled": True, "e8": {
        "AUDCHF_overnight_gap_decay_asia": 0.01,
        "EURCHF_formula_asia": 0.01,
        "USDJPY_session_range_breakout_asia": 0.01}, "excluded": {
        "USDJPY_session_range_breakout_asia": "Reddit-only lineage"}}), encoding="utf-8")
    monkeypatch.setattr(e8_book, "CERT_BOOK", config)
    monkeypatch.setattr(admission_integrity.IntegrityGate, "load",
                        classmethod(lambda cls: _Gate()))
    monkeypatch.setattr(kelly_survival, "terms_fenced_cells", lambda: (set(), "fixture"))
    rows = [
        {"key": "good", "symbol": "AUDCHF", "family": "overnight_gap_decay",
         "selector": "asia", "fingerprint": "frozen-spec"},
        {"key": "bad", "symbol": "EURCHF", "family": "formula",
         "selector": "asia", "fingerprint": "frozen-spec"},
        {"key": "excluded", "symbol": "USDJPY", "family": "session_range_breakout",
         "selector": "asia", "fingerprint": "frozen-spec"},
    ]
    accepted, blocked = e8_book.live_admissible(rows)
    assert [r["key"] for r in accepted] == ["good"]
    assert {r["certificate"]: r["why"] for r in blocked} == {
        "bad": "replication MISMATCH: independent rebuild disagrees",
        "excluded": "principal exclusion: Reddit-only lineage"}


def test_every_certified_sleeve_flows_into_e8_unless_the_principal_zeroes_it(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """zuck 2026-11-19: all certified strategies flow into E8. An unnamed key is admitted (sized
    by RISK_FRAC), an explicit zero still stands aside, and the gold-only zeros are lifted."""
    config = tmp_path / "CERT_BOOK_LIVE.json"
    config.write_text(json.dumps({"enabled": True, "e8": {
        "gold_asia": 0.006,
        "EURCHF_formula_asia": 0.0,
        "NZDJPY_clock_transition_asia": 0.0,
        "AUDCHF_overnight_gap_decay_asia": 0.0}, "excluded": {}}), encoding="utf-8")
    monkeypatch.setattr(e8_book, "CERT_BOOK", config)
    monkeypatch.setattr(admission_integrity.IntegrityGate, "load",
                        classmethod(lambda cls: _Gate()))
    monkeypatch.setattr(kelly_survival, "terms_fenced_cells", lambda: (set(), "fixture"))
    rows = [
        {"key": "unnamed", "symbol": "NAS100", "family": "overnight_gap_decay",
         "selector": "asia", "fingerprint": "frozen-spec"},
        {"key": "paused", "symbol": "EURCHF", "family": "formula",
         "selector": "asia", "fingerprint": "frozen-spec"},
        {"key": "lifted_nzd", "symbol": "NZDJPY", "family": "clock_transition",
         "selector": "asia", "fingerprint": "frozen-spec"},
        {"key": "lifted_aud", "symbol": "AUDCHF", "family": "overnight_gap_decay",
         "selector": "asia", "fingerprint": "frozen-spec"},
    ]
    accepted, blocked = e8_book.live_admissible(rows)
    assert [r["key"] for r in accepted] == ["unnamed", "lifted_nzd", "lifted_aud"]
    assert blocked == [{"certificate": "paused",
                        "why": "principal zero in the E8 principal book"}]


def test_families_failing_forward_are_held_at_zero(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = tmp_path / "CERT_BOOK_LIVE.json"
    config.write_text(json.dumps({"enabled": True, "e8": {"gold_asia": 0.006},
                                  "excluded": {}}), encoding="utf-8")
    monkeypatch.setattr(e8_book, "CERT_BOOK", config)
    monkeypatch.setattr(admission_integrity.IntegrityGate, "load",
                        classmethod(lambda cls: _Gate()))
    monkeypatch.setattr(kelly_survival, "terms_fenced_cells", lambda: (set(), "fixture"))
    rows = [{"key": k, "symbol": "EURUSD", "family": f, "selector": "asia",
             "fingerprint": "frozen-spec"}
            for k, f in (("held", "cross_asset_residual"), ("ok", "formula"))]
    accepted, blocked = e8_book.live_admissible(rows)
    assert [r["key"] for r in accepted] == ["ok"]
    assert blocked[0]["certificate"] == "held"
    assert blocked[0]["why"].startswith("forward evidence: cross_asset_residual")


def test_a_fill_proven_sleeve_outranks_its_familys_forward_hold(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = tmp_path / "CERT_BOOK_LIVE.json"
    config.write_text(json.dumps({"enabled": True, "e8": {"gold_asia": 0.006},
                                  "excluded": {}}), encoding="utf-8")
    proven = tmp_path / "FILL_PROVEN.json"
    proven.write_text(json.dumps({"rows": [
        {"sleeve": "AUDCAD_cross_asset_residual_asia", "n_out": 15, "adjR_out": 1.402},
        {"sleeve": "GBPAUD_cross_asset_residual_asia", "n_out": 9, "adjR_out": 0.5},
        {"sleeve": "USDSGD_carry_asia", "n_out": 25, "adjR_out": -0.5}]}), encoding="utf-8")
    monkeypatch.setattr(e8_book, "CERT_BOOK", config)
    monkeypatch.setattr(e8_book, "FILL_PROVEN", proven)
    monkeypatch.setattr(admission_integrity.IntegrityGate, "load",
                        classmethod(lambda cls: _Gate()))
    monkeypatch.setattr(kelly_survival, "terms_fenced_cells", lambda: (set(), "fixture"))
    rows = [{"key": k, "symbol": sym, "family": fam, "selector": "asia",
             "fingerprint": "frozen-spec"}
            for k, sym, fam in (("proven", "AUDCAD", "cross_asset_residual"),
                                ("thin", "GBPAUD", "cross_asset_residual"),
                                ("negative", "USDSGD", "carry"))]
    accepted, blocked = e8_book.live_admissible(rows)
    assert [r["key"] for r in accepted] == ["proven"]
    assert accepted[0]["fill_proven"] == {"n": 15.0, "adjR": 1.402}
    assert {b["certificate"] for b in blocked} == {"thin", "negative"}
    assert abs(e8_book.fill_shrink(15) - 15 / 65) < 1e-12 and e8_book.fill_shrink(0) == 0.0


def test_principal_e8_book_lifts_only_the_superseded_zeros() -> None:
    raw = {"gold_asia": 0.006, "USDJPY_session_range_breakout_asia": 0.0,
           "NZDJPY_clock_transition_asia": 0.0, "AUDCHF_overnight_gap_decay_asia": 0.002,
           "flag": True}
    assert e8_book.principal_e8_book(raw) == {
        "gold_asia": 0.006, "USDJPY_session_range_breakout_asia": 0.0,
        "AUDCHF_overnight_gap_decay_asia": 0.002}
    assert e8_book.principal_e8_book(None) == {}
    lifted = frozenset({"NZDJPY_clock_transition_asia", "AUDCHF_overnight_gap_decay_asia"})
    assert lifted == e8_book.SUPERSEDED_E8_ZEROS


def test_missing_exclusion_authority_refuses_to_build(tmp_path: Path,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(e8_book, "CERT_BOOK", tmp_path / "missing.json")
    with pytest.raises(OSError):
        e8_book.live_admissible([])


class _RiskVenue:
    _by_key = {"XAUUSD": 6102, "AUDCHF": 6103}

    def details(self, symbol: str) -> dict:
        return {"contractSize": 100 if symbol == "XAUUSD" else 100_000,
                "currency": "USD" if symbol == "XAUUSD" else "CHF"}

    def quote(self, symbol: str) -> tuple[float, float]:
        return (4100.0, 4101.0) if symbol == "XAUUSD" else (0.7000, 0.7001)


def test_broker_risk_reserves_open_stop_and_both_resting_gold_legs() -> None:
    venue = _RiskVenue()
    positions = [{"tradableInstrumentId": 6102, "side": "buy", "qty": 0.1,
                  "stopLossId": 7, "stopLoss": 0}]
    orders = [{"id": 7, "tradableInstrumentId": 6102, "stopPrice": 4050.0},
              {"id": 10, "tradableInstrumentId": 6102, "stopPrice": 4200.0,
               "stopLoss": 0, "qty": 0.1},
              {"id": 8, "tradableInstrumentId": 6102, "qty": 0.08,
               "stopPrice": 4120.0, "stopLoss": 4070.0},
              {"id": 9, "tradableInstrumentId": 6102, "qty": 0.08,
               "stopPrice": 4070.0, "stopLoss": 4120.0}]
    risk, why = e8_executor.outstanding_stop_risk(venue, positions, orders)
    assert risk == pytest.approx(1300.0)  # 500 live downside + 400 per pending leg
    assert "priced" in why


def test_missing_protective_stop_refuses_new_risk() -> None:
    risk, why = e8_executor.outstanding_stop_risk(
        _RiskVenue(), [{"tradableInstrumentId": 6102, "side": "buy", "qty": 0.1}], [])
    assert risk is None
    assert "no measurable protective stop" in why
