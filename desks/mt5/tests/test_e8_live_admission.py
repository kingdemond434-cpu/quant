"""The E8 book cannot turn a stale or quarantined certificate into an order candidate."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
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


def _fresh(age_h: float = 0.5) -> dict[str, str]:
    """A FILL_PROVEN header the consumer accepts: the organ's schema, written age_h ago."""
    gen = datetime.now(UTC) - timedelta(hours=age_h)
    return {"schema": e8_book.FILL_PROVEN_SCHEMA, "generated_at": gen.isoformat(timespec="seconds")}


class _Gate:
    alarm = {"blocks": False}

    def replication(self, cert: str, fingerprint: str) -> tuple[str, str]:
        assert fingerprint == "frozen-spec"
        return (("MISMATCH", "independent rebuild disagrees") if cert == "bad" else
                ("REPLICATED", "independent rebuild agrees"))


def test_e8_admission_sizes_replication_doubts_and_drops_lifted_exclusions(
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
    # Principal 2026-11-24 18:34Z, no blockers but exotics: a replication MISMATCH halves the
    # size, and USDJPY's Reddit-lineage exclusion is lifted (SUPERSEDED_EXCLUSIONS).
    assert [r["key"] for r in accepted] == ["good", "bad", "excluded"] and blocked == []
    bad = accepted[1]       # principal-funded: his number sizes it, the doubt is journaled
    assert any("replication MISMATCH" in n for n in bad["evidence_notes"])
    assert "evidence_mult" not in bad


def test_every_certified_sleeve_flows_into_e8_unless_the_principal_zeroes_it(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """zuck 2026-11-19: every profitable (fill-proven) strategy flows into E8. An unnamed key is
    admitted, an explicit zero still stands aside, and the gold-only zeros are lifted."""
    config = tmp_path / "CERT_BOOK_LIVE.json"
    config.write_text(json.dumps({"enabled": True, "e8": {
        "gold_asia": 0.006,
        "EURCHF_formula_asia": 0.0,
        "NZDJPY_clock_transition_asia": 0.0,
        "AUDCHF_overnight_gap_decay_asia": 0.0}, "excluded": {}}), encoding="utf-8")
    proven = tmp_path / "FILL_PROVEN.json"
    proven.write_text(json.dumps({**_fresh(), "sleeves": [
        {"sleeve": s, "n_out": 20, "adjR_out": 0.3} for s in (
            "NAS100_overnight_gap_decay_asia", "EURCHF_formula_asia",
            "NZDJPY_clock_transition_asia", "AUDCHF_overnight_gap_decay_asia")]}),
        encoding="utf-8")
    monkeypatch.setattr(e8_book, "CERT_BOOK", config)
    monkeypatch.setattr(e8_book, "FILL_PROVEN", proven)
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


def test_a_certificate_alone_admits_at_its_prior_size_without_fills(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = tmp_path / "CERT_BOOK_LIVE.json"
    config.write_text(json.dumps({"enabled": True, "e8": {"gold_asia": 0.006},
                                  "excluded": {}}), encoding="utf-8")
    monkeypatch.setattr(e8_book, "CERT_BOOK", config)
    monkeypatch.setattr(e8_book, "FILL_PROVEN", tmp_path / "absent.json")
    monkeypatch.setattr(admission_integrity.IntegrityGate, "load",
                        classmethod(lambda cls: _Gate()))
    monkeypatch.setattr(kelly_survival, "terms_fenced_cells", lambda: (set(), "fixture"))
    rows = [{"key": k, "symbol": "EURUSD", "family": f, "selector": "asia",
             "fingerprint": "frozen-spec"}
            for k, f in (("held", "cross_asset_residual"), ("ok", "formula"))]
    accepted, blocked = e8_book.live_admissible(rows)
    assert blocked == [] and [r["key"] for r in accepted] == ["held", "ok"]
    by = {r["key"]: r for r in accepted}
    prior = e8_book.fill_shrink(e8_book.CERT_PRIOR_N)
    assert by["ok"]["evidence_mult"] == round(prior, 6)
    assert by["held"]["evidence_mult"] == round(prior * e8_book.DOUBT_MULT, 6)
    assert any("cross_asset_residual fails forward" in n for n in by["held"]["evidence_notes"])
    assert 0 < e8_book.sleeve_risk(by["held"]) < e8_book.sleeve_risk(by["ok"]) < e8_book.RISK_FRAC


def test_a_fill_proven_sleeve_outranks_its_familys_forward_hold(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = tmp_path / "CERT_BOOK_LIVE.json"
    config.write_text(json.dumps({"enabled": True, "e8": {"gold_asia": 0.006},
                                  "excluded": {}}), encoding="utf-8")
    proven = tmp_path / "FILL_PROVEN.json"
    proven.write_text(json.dumps({**_fresh(), "sleeves": [
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
    assert [r["key"] for r in accepted] == ["proven", "thin"]
    assert accepted[0]["fill_proven"] == {"n": 15.0, "adjR": 1.402}
    assert accepted[0]["evidence_mult"] > accepted[1]["evidence_mult"] > 0
    # USDSGD is exotic: the one refusal left.
    assert [b["certificate"] for b in blocked] == ["negative"]
    assert "exotic" in blocked[0]["why"]
    assert abs(e8_book.fill_shrink(15) - 15 / 65) < 1e-12 and e8_book.fill_shrink(0) == 0.0


def test_size_scales_with_fill_depth_and_tier_s_multiplies() -> None:
    r = e8_book.RISK_FRAC
    assert e8_book.sleeve_risk({"fill_proven": {"n": 50}}) == round(r * 0.5, 6)
    assert e8_book.sleeve_risk({"fill_proven": {"n": 50}, "tier_s": True}) == round(r * 0.75, 6)
    assert e8_book.sleeve_risk({}) == r


def test_principal_e8_book_lifts_only_the_superseded_zeros() -> None:
    raw = {"gold_asia": 0.006, "USDJPY_session_range_breakout_asia": 0.0,
           "NZDJPY_clock_transition_asia": 0.0, "AUDCHF_overnight_gap_decay_asia": 0.002,
           "flag": True}
    assert e8_book.principal_e8_book(raw) == {
        "gold_asia": 0.006, "AUDCHF_overnight_gap_decay_asia": 0.002}
    assert e8_book.principal_e8_book(None) == {}
    lifted = frozenset({"NZDJPY_clock_transition_asia", "AUDCHF_overnight_gap_decay_asia",
                        "USDJPY_session_range_breakout_asia", "gold_london_am",
                        "gold_afternoon"})
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


def test_rollover_gate_refuses_fill_proven_entries_in_broker_00_to_01() -> None:
    from datetime import UTC, datetime
    proven = {"fill_proven": {"n": 20, "adjR": 0.3}}
    # November: E8 server = UTC+2, so 22:30 UTC is 00:30 broker and 23:59 UTC is 01:59.
    at_0030 = e8_book.rollover_block(proven, datetime(2026, 11, 19, 22, 30, tzinfo=UTC))
    at_0159 = e8_book.rollover_block(proven, datetime(2026, 11, 19, 23, 59, tzinfo=UTC))
    assert at_0030 is not None and "broker hour 00" in at_0030
    assert at_0159 is not None and "broker hour 01" in at_0159
    assert e8_book.rollover_block(proven, datetime(2026, 11, 20, 0, 0, tzinfo=UTC)) is None
    assert e8_book.rollover_block(proven, datetime(2026, 11, 19, 21, 59, tzinfo=UTC)) is None
    # A principal-funded key with no fill record is the principal's, not gated here.
    assert e8_book.rollover_block({}, datetime(2026, 11, 19, 22, 30, tzinfo=UTC)) is None
    # July: server = UTC+3, so 21:15 UTC is 00:15 broker.
    assert e8_book.rollover_block(proven, datetime(2026, 7, 1, 21, 15, tzinfo=UTC)) is not None


_ROW = {"sleeve": "AUDCAD_cross_asset_residual_asia", "n_out": 15, "adjR_out": 1.4}


def test_fill_proven_fresh_file_is_read(tmp_path):
    p = tmp_path / "FILL_PROVEN.json"
    p.write_text(json.dumps({**_fresh(), "sleeves": [_ROW]}), encoding="utf-8")
    assert set(e8_book.load_fill_proven(p)) == {"AUDCAD_cross_asset_residual_asia"}


def test_a_stale_fill_proven_file_fails_closed(tmp_path):
    """Audit HOLD 2026-11-19: if the organ stops, its last verdicts must not keep admitting."""
    p = tmp_path / "FILL_PROVEN.json"
    p.write_text(json.dumps({**_fresh(e8_book.FILL_PROVEN_MAX_AGE_H + 0.1), "sleeves": [_ROW]}),
                 encoding="utf-8")
    assert e8_book.load_fill_proven(p) == {}


@pytest.mark.parametrize("header", [
    {"schema": "fill-proven/0"},
    {"generated_at": "2026-11-19T19:00:00+00:00"},
    {"schema": "fill-proven/1", "generated_at": "not a time"},
    {"schema": "fill-proven/1", "generated_at": "2026-11-19T19:00:00"},
    {"schema": "fill-proven/1"},
])
def test_a_wrong_schema_or_bad_timestamp_fails_closed(tmp_path, header):
    p = tmp_path / "FILL_PROVEN.json"
    p.write_text(json.dumps({**header, "sleeves": [_ROW]}), encoding="utf-8")
    assert e8_book.load_fill_proven(p) == {}


def test_a_future_dated_file_fails_closed(tmp_path):
    p = tmp_path / "FILL_PROVEN.json"
    p.write_text(json.dumps({**_fresh(-1.0), "sleeves": [_ROW]}), encoding="utf-8")
    assert e8_book.load_fill_proven(p) == {}


def test_only_the_bh_filtered_sleeves_list_is_read(tmp_path):
    """The organ writes the BH-filtered rows under "sleeves" only; an unfiltered "rows" list is
    never a substitute."""
    p = tmp_path / "FILL_PROVEN.json"
    p.write_text(json.dumps({**_fresh(), "rows": [_ROW]}), encoding="utf-8")
    assert e8_book.load_fill_proven(p) == {}
