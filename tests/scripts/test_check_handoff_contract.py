"""ARCH-11: units, currencies, vintages, horizons, identities and gross/net hold along the chain."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.research import handoff_contract as HC  # noqa: E402


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


fence = _load("_quant_check_handoff_contract", "scripts/check_handoff_contract.py")
fc = _load("_quant_forecast_contract_arch11", "desks/mt5/research/forecast_contract.py")

NOW = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)


def _ok(**over: Any) -> dict[str, Any]:
    kw: dict[str, Any] = {"unit": "R", "horizon_s": 3600.0, "instrument_id": "XAUUSD",
                          "gross_or_net": "net", "known_at": "2026-10-01T11:00:00+00:00"}
    return HC.block("allocator_input", **(kw | over))


# --------------------------------------------------------------------------- the contract itself
def test_a_complete_block_has_no_defects() -> None:
    assert HC.field_defects(_ok(), now=NOW) == []


@pytest.mark.parametrize(("over", "must"), [
    ({"unit": "percent"}, "declared unit"),
    ({"unit": "price"}, "currency-bearing"),
    ({"unit": "R", "currency": "USD"}, "carries no currency"),
    ({"horizon_s": 0}, "horizon_s"),
    ({"gross_or_net": "both"}, "gross_or_net"),
    ({"known_at": "yesterday"}, "ISO"),
    ({"instrument_id": ""}, "instrument_id"),
    ({"instrument_id": {"rows": "sleeves"}}, "per-row"),
    ({"field_units": {"cost": "price"}}, "names no currency"),
], ids=["unit", "price-no-ccy", "ccy-on-R", "horizon", "gross-net", "vintage", "iid",
        "per-row", "field-units"])
def test_each_defective_declaration_is_refused(over: dict[str, Any], must: str) -> None:
    with pytest.raises(ValueError, match=must.replace("[", r"\[")):
        _ok(**over)


def test_a_missing_field_and_a_future_vintage_are_defects() -> None:
    h = _ok()
    h.pop("currency")
    assert any("missing field currency" in d for d in HC.field_defects(h, now=NOW))
    late = _ok() | {"known_at": "2026-10-01T13:00:00+00:00"}
    assert any("future" in d for d in HC.field_defects(late, now=NOW))


def test_cross_hop_catches_net_to_gross_currency_and_horizon() -> None:
    D = HC.Declaration
    net_up = D("a", "forecast", "XAUUSD", "R", None, 3600.0, "net")
    gross_down = D("b", "allocator_input", "XAUUSD", "R", None, 3600.0, "gross")
    assert any("GROSS" in p for p in HC.cross_hop([net_up, gross_down]))
    # the other direction (gross upstream, net downstream) is costs being charged: allowed
    assert HC.cross_hop([D("a", "forecast", "XAUUSD", "R", None, 3600.0, "gross"),
                         D("b", "allocator_input", "XAUUSD", "R", None, 3600.0, "net")]) == []
    usd = D("a", "allocator_input", "XAUUSD", "price", "USD", 3600.0, "gross")
    eur = D("b", "gateway_intent", "XAUUSD", "price", "EUR", 3600.0, "gross")
    assert any("EUR" in p for p in HC.cross_hop([usd, eur]))
    assert any("profit currency" in p
               for p in HC.cross_hop([eur], {"XAUUSD": {"currency_profit": "USD"}}))
    week = D("b", "allocator_input", "XAUUSD", "R", None, 5 * 86400.0, "net")
    assert any("horizon" in p for p in HC.cross_hop([net_up, week]))


def test_book_level_quantity_meets_every_instrument() -> None:
    D = HC.Declaration
    book_net = D("a", "allocator_input", HC.BOOK, "R", None, 3600.0, "net")
    sym_gross = D("b", "gateway_intent", "EURUSD", "R", None, 3600.0, "gross")
    assert HC.cross_hop([book_net, sym_gross])


# --------------------------------------------------------------------------- forecast producer
def _belief(**over: Any):
    base = {"model_id": "m1", "subject": "XAUUSD/up", "kind": "PROBABILITY", "value": 0.6,
            "horizon_s": 3600, "at": "2026-10-01T10:00:00+00:00", "instrument_id": "XAUUSD",
            "unit": "probability", "gross_or_net": "not_applicable"}
    return fc.Belief(**(base | over))


def test_forecast_register_rows_carry_the_block_and_refuse_without_it(tmp_path: Path) -> None:
    reg = tmp_path / "forecast_register.jsonl"
    pub = fc.publish([_belief(), _belief(instrument_id="", unit="")], register=reg)
    assert pub.counts() == {"accepted": 1, "refused": 1}
    acc = pub.accepted[0][HC.KEY]
    assert acc["stage"] == "forecast" and acc["known_at"] == "2026-10-01T10:00:00+00:00"
    assert HC.field_defects(acc) == []
    assert any("handoff" in d for d in pub.refused[0]["defects"])


def test_a_belief_citing_a_later_vintage_is_refused() -> None:
    bad = fc.defects(_belief(known_at="2026-10-01T11:00:00+00:00"))
    assert any("lookahead" in d for d in bad)


# --------------------------------------------------------------------------- the fence
def _surfaces(*extra: HC.Surface) -> tuple[HC.Surface, ...]:
    return (HC.Surface("fr", "data/fr.jsonl", "forecast", "prod/fr.py", layout="jsonl_rows"),
            HC.Surface("ev", "data/ev.json", "allocator_input", "prod/ev.py"),
            HC.Surface("sl", "data/sleeves.json", "gateway_intent", "prod/promoter.py",
                       money_path=True), *extra)


@pytest.fixture()
def tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    uni = tmp_path / "desks/mt5/data/universe/universe.json"
    uni.parent.mkdir(parents=True)
    uni.write_text(json.dumps({"XAUUSD": {"currency_profit": "USD"},
                               "EURUSD": {"currency_profit": "USD"}}))
    (tmp_path / "prod").mkdir()
    for name, stage in (("fr", "forecast"), ("ev", "allocator_input")):
        (tmp_path / f"prod/{name}.py").write_text(
            f'from libs.research import handoff_contract\nSTAGE = "{stage}"\n')
    (tmp_path / "prod/promoter.py").write_text("# money path\n")
    (tmp_path / "data").mkdir()
    (tmp_path / "data/sleeves.json").write_text(json.dumps(
        {"sleeves": [{"name": "a", "symbol": "XAUUSD", "risk_frac": 0.02}]}))
    monkeypatch.setattr(HC, "SURFACES", _surfaces())
    monkeypatch.setattr(HC, "PENDING_MONEY_PATH", {"sl": "promoter is money path"})
    monkeypatch.setattr(HC, "PENDING_CEILING", 1)
    monkeypatch.setattr(fence, "allocator_inputs", lambda: [])
    return tmp_path


def _write_ev(tree: Path, **over: Any) -> None:
    doc = {"sleeves": {"s1": {"symbol": "XAUUSD"}, "s2": {"symbol": "EURUSD"}}}
    HC.stamp(doc, "allocator_input", **({"unit": "R", "horizon_s": 86400.0,
                                         "instrument_id": {"rows": "sleeves",
                                                           "field": "symbol"},
                                         "gross_or_net": "net",
                                         "known_at": "2026-10-01T11:00:00+00:00"} | over))
    (tree / "data/ev.json").write_text(json.dumps(doc))


def test_absent_artifacts_are_unmeasured_never_pass(tree: Path) -> None:
    doc = fence.measure(tree, now=NOW)
    assert doc["verdict"] == "UNMEASURED"
    assert {"fr", "ev"} <= set(doc["unmeasured"])
    assert doc["surfaces"]["sl"]["status"] == "PENDING"


def test_a_clean_stamped_chain_passes(tree: Path) -> None:
    _write_ev(tree)
    (tree / "data/fr.jsonl").write_text(json.dumps(
        {HC.KEY: HC.block("forecast", unit="probability", horizon_s=3600.0,
                          instrument_id="XAUUSD", gross_or_net="not_applicable",
                          known_at="2026-10-01T10:00:00+00:00")}) + "\n")
    doc = fence.measure(tree, now=NOW)
    assert doc["problems"] == [] and doc["verdict"] == "PASS", doc


def test_a_missing_field_fails(tree: Path) -> None:
    _write_ev(tree)
    d = json.loads((tree / "data/ev.json").read_text())
    del d[HC.KEY]["gross_or_net"]
    (tree / "data/ev.json").write_text(json.dumps(d))
    doc = fence.measure(tree, now=NOW)
    assert doc["verdict"] == "FAIL"
    assert any("missing field gross_or_net" in p for p in doc["problems"])


def test_an_unquoted_instrument_fails(tree: Path) -> None:
    doc = {"sleeves": {"s1": {"symbol": "XAUUSD.raw"}, "s2": {}}}
    HC.stamp(doc, "allocator_input", unit="R", horizon_s=86400.0,
             instrument_id={"rows": "sleeves", "field": "symbol"}, gross_or_net="net")
    (tree / "data/ev.json").write_text(json.dumps(doc))
    probs = fence.measure(tree, now=datetime.now(UTC))["problems"]
    assert any("XAUUSD.raw" in p for p in probs) and any("<missing>" in p for p in probs)


def test_net_upstream_republished_gross_fails(tree: Path) -> None:
    _write_ev(tree, gross_or_net="gross")
    (tree / "data/fr.jsonl").write_text(json.dumps(
        {HC.KEY: HC.block("forecast", unit="R", horizon_s=3600.0, instrument_id="XAUUSD",
                          gross_or_net="net", known_at="2026-10-01T10:00:00+00:00")}) + "\n")
    probs = fence.measure(tree, now=NOW)["problems"]
    assert any("GROSS" in p for p in probs)


def test_unstamped_artifact_after_the_stamping_code_landed_fails(tree: Path) -> None:
    ev = tree / "data/ev.json"
    ev.write_text(json.dumps({"sleeves": {}}))
    src = (tree / "prod/ev.py").stat().st_mtime
    os.utime(ev, (src + 60, src + 60))
    assert fence.measure(tree, now=NOW)["surfaces"]["ev"]["status"] == "UNMEASURED"
    late = src + fence.GRACE_S + 3600
    os.utime(ev, (late, late))
    doc = fence.measure(tree, now=NOW)
    assert doc["surfaces"]["ev"]["status"] == "FAIL"


def test_a_healed_pending_surface_fails_until_removed(tree: Path) -> None:
    doc = {"sleeves": [{"name": "a", "symbol": "XAUUSD", "risk_frac": 0.02}]}
    HC.stamp(doc, "gateway_intent", unit="heat_frac", horizon_s=3600.0,
             instrument_id={"rows": "sleeves", "field": "symbol"}, gross_or_net="net")
    (tree / "data/sleeves.json").write_text(json.dumps(doc))
    probs = fence.measure(tree, now=datetime.now(UTC) + timedelta(hours=1))["problems"]
    assert any("ratchet" in p for p in probs)


def test_pending_rows_are_still_held_to_identity_and_fraction_units(tree: Path) -> None:
    (tree / "data/sleeves.json").write_text(json.dumps(
        {"sleeves": [{"name": "a", "symbol": "GOLD", "risk_frac": 3.0}]}))
    probs = fence.measure(tree, now=NOW)["problems"]
    assert any("GOLD" in p for p in probs) and any("percent" in p for p in probs)


def test_a_producer_that_stops_stamping_fails_wiring(tree: Path) -> None:
    (tree / "prod/ev.py").write_text("# no contract here\n")
    assert any("does not stamp" in p for p in fence.wiring(tree))


def test_the_pending_list_only_shrinks(tree: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(HC, "PENDING_MONEY_PATH", {"sl": "x", "ev": "y"})
    probs = fence.wiring(tree)
    assert any("not a money-path surface" in p for p in probs)
    assert any("only shrinks" in p for p in probs)


# --------------------------------------------------------------------------- the real tree
def test_the_real_chain_is_wired() -> None:
    """Every allocator input is on a surface and every non-money producer stamps."""
    assert fence.wiring(ROOT) == []
    names = {s.name for s in HC.SURFACES}
    assert set(fence.allocator_inputs() or []) <= names
    assert len(HC.PENDING_MONEY_PATH) <= HC.PENDING_CEILING
    assert all(s.money_path for s in HC.SURFACES if s.name in HC.PENDING_MONEY_PATH)


def test_the_fence_is_on_the_law_gate() -> None:
    src = (ROOT / "scripts/run_law_gate.py").read_text("utf-8")
    assert '("check_handoff_contract.py", ())' in src
