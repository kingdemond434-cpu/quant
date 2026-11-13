"""The fixture-isolation fence: a synthetic strategy in a survivor or performance record fails.

The first test is the one that matters: the placebo audit's positive control is BUILT TO PASS the
ten gates, so the only thing between it and the book is that its identity is recognised.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "check_fixture_isolation", ROOT / "scripts" / "check_fixture_isolation.py")
assert _spec and _spec.loader
fi = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = fi
_spec.loader.exec_module(fi)


def _tree(tmp_path: Path, files: dict[str, object]) -> Path:
    """A root holding the producers' real source and the given records."""
    for rel, _literal in fi.MINTED_BY:
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text((ROOT / rel).read_text("utf-8"), encoding="utf-8")
    for rel, body in files.items():
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(body if isinstance(body, str) else json.dumps(body), encoding="utf-8")
    return tmp_path


CLEAN = {"n": 1, "survivors": {"external.EURUSD carry LONG": {
    "hunt": "external", "cell": "EURUSD carry LONG", "sym": "EURUSD", "family": "carry",
    "note": "canaries and the placebo_ twins are excluded by the fence"}}}


def test_a_passing_positive_control_in_the_survivor_register_fails(tmp_path):
    doc = json.loads(json.dumps(CLEAN))
    doc["survivors"]["external.CANARY placebo_positive_control LONG"] = {
        "hunt": "external", "cell": "CANARY placebo_positive_control LONG", "sym": "CANARY",
        "family": "placebo_positive_control"}
    out = fi.measure(_tree(tmp_path, {fi.RECORDS[0][0]: doc}))
    assert out["verdict"] == "FAIL"
    assert out["records"][fi.RECORDS[0][0]]["n_fixtures"] >= 3
    assert any("placebo_positive_control" in p for p in out["problems"])


def test_a_clean_register_reads_clean_and_prose_is_not_an_identity(tmp_path):
    out = fi.measure(_tree(tmp_path, {fi.RECORDS[0][0]: CLEAN}))
    assert out["records"][fi.RECORDS[0][0]] == {"status": "CLEAN", "fixtures": [],
                                                "n_fixtures": 0}
    assert not out["problems"]


def test_an_absent_record_is_unmeasured_never_pass(tmp_path):
    out = fi.measure(_tree(tmp_path, {fi.RECORDS[0][0]: CLEAN}))
    assert out["verdict"] == "UNMEASURED"
    assert set(out["unmeasured"]) == {rel for rel, _ in fi.RECORDS[1:]}


def test_every_record_clean_is_pass(tmp_path):
    deal = json.dumps({"sleeve": "gold_asia", "symbol": "XAUUSD"}) + "\n"
    files: dict[str, object] = {rel: (CLEAN if layout == "json" else deal)
                                for rel, layout in fi.RECORDS}
    assert fi.measure(_tree(tmp_path, files))["verdict"] == "PASS"


def test_a_canary_deal_in_the_live_ledger_fails(tmp_path):
    rows = "\n".join(json.dumps(r) for r in (
        {"sleeve": "gold_asia", "symbol": "XAUUSD", "profit": 1.0},
        {"sleeve": "canary_noise", "symbol": "CANARY", "profit": 9.0})) + "\n"
    out = fi.measure(_tree(tmp_path, {"desks/mt5/data/live_ledger.jsonl": rows}))
    assert out["verdict"] == "FAIL"
    assert out["records"]["desks/mt5/data/live_ledger.jsonl"]["n_fixtures"] == 2


def test_a_fixture_sleeve_row_fails(tmp_path):
    doc = {"sleeves": [{"name": "fixture.cell_1", "symbol": "EURUSD", "status": "LIVE"}]}
    out = fi.measure(_tree(tmp_path, {"desks/mt5/data/sleeves.json": doc}))
    assert out["verdict"] == "FAIL"


def test_an_unreadable_record_is_unmeasured(tmp_path):
    out = fi.measure(_tree(tmp_path, {"desks/mt5/data/sleeves.json": "{not json"}))
    assert out["records"]["desks/mt5/data/sleeves.json"]["status"] == "UNMEASURED"
    assert out["verdict"] == "UNMEASURED"


def test_a_renamed_fixture_family_fails_the_wiring(tmp_path):
    root = _tree(tmp_path, {})
    src = root / "desks/mt5/research/placebo_audit.py"
    src.write_text(src.read_text("utf-8").replace('f"placebo_{p.name}"', 'f"control_{p.name}"'),
                   encoding="utf-8")
    probs = fi.wiring(root)
    assert len(probs) == 1 and "placebo_audit.py" in probs[0]
    assert fi.measure(root)["verdict"] == "FAIL"


@pytest.mark.parametrize("identity", [
    "canary_noise", "CANARY", "placebo_reversed_sign", "external.CANARY canary_overfit LONG",
    "fixture", "fixture.cell", "hunt/fixture_sweep.json", "qquant.placebo_positive_control"])
def test_fixture_identities(identity):
    assert fi.is_fixture(identity)


@pytest.mark.parametrize("identity", [
    "EURUSD", "carry", "synthetic_cross", "XAUUSD.asia", "session_range_breakout",
    "qquant.hunt16.json.AUDNZD dav_range_filter_adx SHORT", "canaryless", "noplacebo_x", "", None,
    7])
def test_real_identities_are_not_fixtures(identity):
    assert not fi.is_fixture(identity)


def test_the_tree_this_runs_in_holds_no_fixture_in_a_record():
    out = fi.measure(ROOT)
    assert out["verdict"] != "FAIL", out["problems"]
    assert not fi.wiring(ROOT)


def test_the_fence_is_on_the_law_gate():
    assert '("check_fixture_isolation.py", ())' in (ROOT / "scripts/run_law_gate.py").read_text(
        "utf-8")
