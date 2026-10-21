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
AT = (NOW - timedelta(minutes=30)).isoformat()      # every owner stamped inside its cadence


@pytest.fixture
def desk(tmp_path: Path, monkeypatch) -> Path:
    def put(name: str, doc: object) -> Path:
        p = tmp_path / name
        p.write_text(json.dumps(doc), "utf-8")
        return p

    monkeypatch.setattr(cm, "CANON", put("canon.json", {"survivors": {
        CID: {"shadow_spec": {"symbol": "EURUSD", "family": "carry"}}}}))
    monkeypatch.setattr(cm, "CERTS", tmp_path / "absent.json")
    monkeypatch.setattr(cm, "NOVELTY", put("nov.json", {"generated_utc": AT, "per_certificate": {
        CID: {"novelty": 0.2}}}))
    monkeypatch.setattr(cm, "COST_SURFACE", put("cost.json", {"built_at": AT, "symbols": {
        "EURUSD": {"hours": {
        "8": {"status": "MEASURED"}, "9": {"status": "UNMEASURED"}}}}}))
    monkeypatch.setattr(cm, "UNIVERSE", put("uni.json", {"EURUSD": {
        "volume_min": 0.01, "volume_step": 0.01, "contract_size": 100000, "tick_value": 1.0,
        "bars": 5000, "updated_at": AT}}))
    monkeypatch.setattr(cm, "CLOCK_LAW", put("law.json", {"at": AT, "certificates": [
        {"certificate": CID, "verdict": "ACCUMULATING", "status": "ACTIVE", "n": 4}]}))
    monkeypatch.setattr(cm, "SLEEVES", put("sleeves.json", {"sleeves": [
        {"name": "eurusd_carry", "status": "LIVE", "certificate": {"cell": CID}},
        {"name": "old", "status": "RETIRED", "certificate": {"cell": CID}}]}))
    monkeypatch.setattr(cm, "CHAIN", put("chain.json", {"at": AT,
                                                      "chain": [{"sleeve": "eurusd_carry"}]}))
    monkeypatch.setattr(cm, "MARKOUT", put("markout.json", {"at": AT, "n_deals": 3,
                                                          "n_unmatched_deals": 0}))
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
    later = NOW + timedelta(hours=1)          # inside every owner's freshness window
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
    (desk / "chain.json").write_text(json.dumps({"at": AT, "chain": []}), "utf-8")
    doc, _ = cm.judge(cm.measure(NOW), {}, NOW)
    att = doc["subjects"]["sleeve:eurusd_carry"]["fields"]["pnl_attribution"]
    assert att["status"] == "MEASURED_ZERO" and doc["verdict"] == "OK"


def test_unmatched_deals_or_a_stale_markout_are_no_deals_never_zero(desk: Path) -> None:
    (desk / "chain.json").write_text(json.dumps({"at": AT, "chain": []}), "utf-8")
    (desk / "markout.json").write_text(json.dumps({"at": AT, "n_deals": 257,
                                                   "n_unmatched_deals": 28}), "utf-8")
    att = cm.measure(NOW)["subjects"]["sleeve:eurusd_carry"]["fields"]["pnl_attribution"]
    assert att["status"] == "UNMEASURED" and att["label"] == "NO_DEALS" and "28" in att["why"]
    (desk / "markout.json").write_text(json.dumps({"at": "2026-09-01T00:00:00+00:00",
                                                   "n_deals": 257, "n_unmatched_deals": 0}),
                                       "utf-8")
    att = cm.measure(NOW)["subjects"]["sleeve:eurusd_carry"]["fields"]["pnl_attribution"]
    assert att["status"] == "UNMEASURED" and att["label"] == "NO_DEALS"


@pytest.mark.parametrize("verdict,status", [("FROZEN_ROWS", "ACTIVE"),
                                            ("BLOCKED", "IDENTITY_BROKEN"),
                                            ("BLOCKED", "BLOCKED_NO_BARS"),
                                            ("UNMEASURED_KEY", "ACTIVE")])
def test_a_frozen_or_blocked_clock_is_not_a_measured_clock(desk: Path, verdict: str,
                                                           status: str) -> None:
    (desk / "law.json").write_text(json.dumps({"at": AT, "certificates": [
        {"certificate": CID, "verdict": verdict, "status": status, "n": 9}]}), "utf-8")
    f = cm.measure(NOW)["subjects"][f"cert:{CID}"]["fields"]["forward_clock"]
    assert f["status"] == "UNMEASURED" and verdict in f["why"]


def test_a_stale_owner_reads_stale_and_goes_red_like_unmeasured(desk: Path) -> None:
    """A 21-day-old cost surface is a memory, not a measurement (audit of #387)."""
    (desk / "cost.json").write_text(json.dumps({"built_at": "2026-09-23T04:25:19+00:00",
                                                "symbols": {"EURUSD": {"hours": {
                                                    "8": {"status": "MEASURED"}}}}}), "utf-8")
    doc, state = cm.judge(cm.measure(NOW), {}, NOW)
    f = doc["subjects"][f"cert:{CID}"]["fields"]["fill_cost"]
    assert f["status"] == "STALE" and "cost_surface" in f["why"] and doc["verdict"] == "UNMEASURED"
    assert "cost_surface" in doc["stale_owners"]
    later = NOW + timedelta(seconds=cm.GRACE_S + 60)
    doc2, _ = cm.judge(cm.measure(later), state, later)
    assert f"cert:{CID}|fill_cost" in doc2["red"]
    (desk / "cost.json").write_text(json.dumps({"symbols": {"EURUSD": {"hours": {
        "8": {"status": "MEASURED"}}}}}), "utf-8")           # no stamp at all: never fresh
    f = cm.measure(NOW)["subjects"][f"cert:{CID}"]["fields"]["fill_cost"]
    assert f["status"] == "STALE"


def test_a_stale_contract_row_reads_stale(desk: Path) -> None:
    (desk / "uni.json").write_text(json.dumps({"EURUSD": {
        "volume_min": 0.01, "volume_step": 0.01, "contract_size": 100000, "tick_value": 1.0,
        "bars": 5000, "updated_at": "2026-09-03T04:40:20+00:00"}}), "utf-8")
    f = cm.measure(NOW)["subjects"][f"cert:{CID}"]["fields"]["tradability"]
    assert f["status"] == "STALE"


def test_the_repricers_unmeasured_prefix_and_out_of_scope(desk: Path, monkeypatch) -> None:
    rep = desk / "reprice.json"
    monkeypatch.setattr(cm, "FILL_REPRICE", rep)
    rep.write_text(json.dumps({"generated_utc": AT, "certificates": {
        CID: {"verdict": "UNMEASURED: no fills at its hour"}}}), "utf-8")
    fc = cm.measure(NOW)["subjects"][f"cert:{CID}"]["fields"]["fill_cost"]
    assert fc["status"] == "UNMEASURED" and fc["source"] == "fill_hour_reprice"
    rep.write_text(json.dumps({"generated_utc": AT, "certificates": {
        CID: {"verdict": "OUT_OF_SCOPE"}}}), "utf-8")
    fc = cm.measure(NOW)["subjects"][f"cert:{CID}"]["fields"]["fill_cost"]
    assert fc["status"] == "MEASURED" and "OUT_OF_SCOPE" in fc["source"]


def test_a_shared_symbol_family_selector_key_never_matches(desk: Path, monkeypatch) -> None:
    """Up to 8 certs share SYM.family.selector, so only exact identities key a repricing."""
    rep = desk / "reprice.json"
    monkeypatch.setattr(cm, "FILL_REPRICE", rep)
    rep.write_text(json.dumps({"generated_utc": AT, "certificates": {
        "EURUSD.carry": {"verdict": "UNMEASURED: another cert's row"}}}), "utf-8")
    fc = cm.measure(NOW)["subjects"][f"cert:{CID}"]["fields"]["fill_cost"]
    assert fc["source"] == "cost_surface (fallback)" and fc["status"] == "MEASURED"


def test_a_cert_with_no_usable_signal_names_the_bars_not_a_rerun(desk: Path) -> None:
    (desk / "nov.json").write_text(json.dumps({"generated_utc": AT, "per_certificate": {
        CID: {"novelty": None, "why": "0 usable signals on these bars"}}}), "utf-8")
    doc, _ = cm.judge(cm.measure(NOW), {}, NOW)
    f = doc["subjects"][f"cert:{CID}"]["fields"]["novelty"]
    assert f["status"] == "UNMEASURED" and "bars" in f["converter"]
    assert "style_novelty.py on the host" not in f["converter"]


def test_a_naive_now_is_utc_and_the_state_is_written_atomically(desk: Path,
                                                                monkeypatch) -> None:
    monkeypatch.setattr(cm, "REPORT", desk / "out" / "MEASURABILITY.json")
    monkeypatch.setattr(cm, "STATE", desk / "out" / "state.json")
    assert cm.main(["--now", "2026-10-13T12:00:00"]) == 0
    assert json.loads((desk / "out" / "state.json").read_text("utf-8"))["updated_utc"].endswith(
        "+00:00")
    assert not list((desk / "out").glob("*.tmp"))


def test_formula_and_exit_operated_carry_no_novel_lift() -> None:
    sys.path[:0] = [str(ROOT / "desks" / "mt5"), str(ROOT / "desks" / "mt5" / "research")]
    from research.alpha_genome import MECHANISM_CLASS
    assert MECHANISM_CLASS["formula"] == "residual"           # published library: adjacent
    assert MECHANISM_CLASS["exit_operated"] == "trend"        # its base's textbook cause


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
    rep.write_text(json.dumps({"generated_utc": AT, "cost_never_charged": {CID: {"ev": -0.1}},
                               "certificates": {}}), "utf-8")
    trad = desk / "trad.json"
    trad.write_text(json.dumps({"generated_utc": AT,
                                "sleeves": [{"name": "eurusd_carry", "status": "FAIL"}]}),
                    "utf-8")
    monkeypatch.setattr(cm, "FILL_REPRICE", rep)
    monkeypatch.setattr(cm, "LIVE_TRADABILITY", trad)
    doc, _ = cm.judge(cm.measure(NOW), {}, NOW)
    f = doc["subjects"]["sleeve:eurusd_carry"]["fields"]
    assert f["fill_cost"]["status"] == "UNMEASURED" and "never" in f["fill_cost"]["why"]
    assert f["tradability"] == {"status": "MEASURED", "why": "live_tradability FAIL",
                                "value": "FAIL", "source": "LIVE_TRADABILITY.json"}
    rep.write_text(json.dumps({"generated_utc": AT,
                               "cost_never_charged": "UNMEASURED: no survivors file on this host",
                               "certificates": {CID: {"verdict": "SURVIVES_FILL_HOUR"}}}),
                   "utf-8")
    doc, _ = cm.judge(cm.measure(NOW), {}, NOW)
    fc = doc["subjects"][f"cert:{CID}"]["fields"]["fill_cost"]
    assert fc["status"] == "MEASURED" and fc["source"] == "fill_hour_reprice"


def test_markout_slip_is_never_a_measurability_input(desk: Path) -> None:
    """markout's slip_r mixes price and money units until Max-growth's fix lands, so no field
    here may read it: only n_deals / n_unmatched_deals (counts) are taken from markout."""
    base = cm.measure(NOW)["subjects"]
    (desk / "markout.json").write_text(json.dumps({
        "at": AT, "n_deals": 3, "n_unmatched_deals": 0, "mean_slip_r": 99.0,
        "mean_slip_quote": -5.0, "edge_share": -1.27}), "utf-8")
    assert cm.measure(NOW)["subjects"] == base
