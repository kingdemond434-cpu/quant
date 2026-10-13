"""Never UNMEASURED past one cycle: every cert and LIVE sleeve field is measured or goes RED."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts import check_measurability as cm  # noqa: E402

NOW = datetime(2026, 10, 13, 12, tzinfo=UTC)
CID = "external.EURUSD.carry.p=1"


@pytest.fixture
def desk(tmp_path: Path, monkeypatch) -> Path:
    def put(name: str, doc: object) -> Path:
        p = tmp_path / name
        p.write_text(json.dumps(doc), "utf-8")
        return p

    monkeypatch.setattr(cm, "CANON", put("canon.json", {"survivors": {
        CID: {"shadow_spec": {"symbol": "EURUSD", "family": "carry"}}}}))
    monkeypatch.setattr(cm, "CERTS", tmp_path / "absent.json")
    monkeypatch.setattr(cm, "NOVELTY", put("nov.json", {"per_certificate": {
        CID: {"novelty": 0.2}}}))
    monkeypatch.setattr(cm, "COST_SURFACE", put("cost.json", {"symbols": {"EURUSD": {"hours": {
        "8": {"status": "MEASURED"}, "9": {"status": "UNMEASURED"}}}}}))
    monkeypatch.setattr(cm, "UNIVERSE", put("uni.json", {"EURUSD": {
        "volume_min": 0.01, "volume_step": 0.01, "contract_size": 100000, "tick_value": 1.0,
        "bars": 5000}}))
    monkeypatch.setattr(cm, "CLOCK_LAW", put("law.json", {"certificates": [
        {"certificate": CID, "verdict": "ACCUMULATING", "status": "ACTIVE", "n": 4}]}))
    monkeypatch.setattr(cm, "SLEEVES", put("sleeves.json", {"sleeves": [
        {"name": "eurusd_carry", "status": "LIVE", "certificate": {"cell": CID}},
        {"name": "old", "status": "RETIRED", "certificate": {"cell": CID}}]}))
    monkeypatch.setattr(cm, "CHAIN", put("chain.json", {"chain": [{"sleeve": "eurusd_carry"}]}))
    monkeypatch.setattr(cm, "MARKOUT", put("markout.json", {"n_deals": 3}))
    monkeypatch.setattr(cm, "FILL_REPRICE", tmp_path / "no_reprice.json")
    monkeypatch.setattr(cm, "LIVE_TRADABILITY", tmp_path / "no_trad.json")
    return tmp_path


def test_a_fully_measured_book_is_ok(desk: Path) -> None:
    doc, _ = cm.judge(cm.measure(NOW), {}, NOW)
    assert doc["verdict"] == "OK", doc["unmeasured_by_field"]
    assert doc["n_live_sleeves"] == 1
    f = doc["subjects"]["sleeve:eurusd_carry"]["fields"]
    assert f["pnl_attribution"]["status"] == "MEASURED" and f["novelty"]["value"] == 0.2


def test_an_unmeasured_field_is_graced_one_cycle_then_red_with_its_converter(
        desk: Path, monkeypatch) -> None:
    monkeypatch.setattr(cm, "NOVELTY", desk / "missing.json")
    doc, state = cm.judge(cm.measure(NOW), {}, NOW)
    assert doc["verdict"] == "UNMEASURED" and not doc["red"]
    later = NOW + timedelta(seconds=cm.GRACE_S + 60)
    doc2, _ = cm.judge(cm.measure(later), state, later)
    assert doc2["verdict"] == "RED"
    key = f"cert:{CID}|novelty"
    assert key in doc2["red"]
    f = doc2["subjects"][f"cert:{CID}"]["fields"]["novelty"]
    assert "style_novelty" in f["converter"] and f["unmeasured_since"] == NOW.isoformat(
        timespec="seconds")


def test_a_field_that_heals_drops_its_clock(desk: Path, monkeypatch) -> None:
    monkeypatch.setattr(cm, "NOVELTY", desk / "missing.json")
    _, state = cm.judge(cm.measure(NOW), {}, NOW)
    monkeypatch.setattr(cm, "NOVELTY", desk / "nov.json")
    later = NOW + timedelta(hours=5)
    doc, state2 = cm.judge(cm.measure(later), state, later)
    assert doc["verdict"] == "OK" and state2["first_unmeasured"] == {}


def test_an_unclassified_family_and_a_missing_clock_are_named(desk: Path, monkeypatch) -> None:
    (desk / "canon.json").write_text(json.dumps({"survivors": {
        CID: {"shadow_spec": {"symbol": "EURUSD", "family": "zz_no_such_family"}}}}), "utf-8")
    (desk / "law.json").write_text(json.dumps({"certificates": [
        {"certificate": CID, "verdict": "NO_CLOCK", "status": "UNMEASURED"}]}), "utf-8")
    doc, _ = cm.judge(cm.measure(NOW), {}, NOW)
    f = doc["subjects"][f"cert:{CID}"]["fields"]
    assert f["mechanism_class"]["status"] == "UNMEASURED"
    assert "MECHANISM_CLASS" in f["mechanism_class"]["converter"]
    assert f["forward_clock"]["status"] == "UNMEASURED"


def test_a_live_sleeve_with_no_deals_is_a_measured_zero(desk: Path) -> None:
    (desk / "chain.json").write_text(json.dumps({"chain": []}), "utf-8")
    doc, _ = cm.judge(cm.measure(NOW), {}, NOW)
    att = doc["subjects"]["sleeve:eurusd_carry"]["fields"]["pnl_attribution"]
    assert att["status"] == "MEASURED_ZERO" and doc["verdict"] == "OK"


def test_no_canon_is_not_applicable_never_ok(desk: Path, monkeypatch) -> None:
    monkeypatch.setattr(cm, "CANON", desk / "none.json")
    doc, _ = cm.judge(cm.measure(NOW), {}, NOW)
    assert doc["verdict"] == "NOT_APPLICABLE"


def test_every_registered_family_has_a_declared_class() -> None:
    """The style library classifies every family the registry can mint."""
    sys.path[:0] = [str(ROOT / "desks" / "mt5"), str(ROOT / "desks" / "mt5" / "research")]
    from research.alpha_genome import MECHANISM_CLASS
    try:
        from mt5desk.families import FAMILY_REGISTRY
    except Exception:
        pytest.skip("family registry not importable here")
    missing = sorted(f for f in map(str, FAMILY_REGISTRY) if f not in MECHANISM_CLASS)
    assert not missing, missing


def test_the_owners_are_read_first_for_cost_and_tradability(desk: Path, monkeypatch) -> None:
    rep = desk / "reprice.json"
    rep.write_text(json.dumps({"cost_never_charged": {CID: {"ev": -0.1}},
                               "certificates": {}}), "utf-8")
    trad = desk / "trad.json"
    trad.write_text(json.dumps({"sleeves": [{"name": "eurusd_carry", "status": "FAIL"}]}),
                    "utf-8")
    monkeypatch.setattr(cm, "FILL_REPRICE", rep)
    monkeypatch.setattr(cm, "LIVE_TRADABILITY", trad)
    doc, _ = cm.judge(cm.measure(NOW), {}, NOW)
    f = doc["subjects"]["sleeve:eurusd_carry"]["fields"]
    assert f["fill_cost"]["status"] == "UNMEASURED" and "never" in f["fill_cost"]["why"]
    assert f["tradability"] == {"status": "MEASURED", "why": "live_tradability FAIL",
                                "value": "FAIL", "source": "LIVE_TRADABILITY.json"}
    rep.write_text(json.dumps({"cost_never_charged": "UNMEASURED: no survivors file on this host",
                               "certificates": {CID: {"verdict": "SURVIVES_FILL_HOUR"}}}),
                   "utf-8")
    doc, _ = cm.judge(cm.measure(NOW), {}, NOW)
    fc = doc["subjects"][f"cert:{CID}"]["fields"]["fill_cost"]
    assert fc["status"] == "MEASURED" and fc["source"] == "fill_hour_reprice"
