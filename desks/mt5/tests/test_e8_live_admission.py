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
                  "stopLossId": 7}]
    orders = [{"id": 7, "tradableInstrumentId": 6102, "stopPrice": 4050.0},
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
