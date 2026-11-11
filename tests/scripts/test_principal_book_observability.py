"""The health probe reads the same principal overlay as the gateway, without broker calls."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desks" / "mt5"))
from research import allocator_liveness as liveness  # noqa: E402
from scripts import check_allocator_join as join  # noqa: E402


@pytest.mark.parametrize("case,enabled,value,status,n_joined", [
    ("absent", None, None, "BROKEN", 0),
    ("principal", True, 0.1, "OK", 1),
    ("disabled", False, 0.1, "BROKEN", 0),
    ("invalid", True, 1.0, "BROKEN", 0),
    ("string", True, "0.1", "BROKEN", 0),
    ("zero", True, 0.0, "OK", 1),
])
def test_principal_book_matches_sizing_authority(tmp_path, monkeypatch,
                                               case, enabled, value, status, n_joined):
    allocation = {"book": {"OTHER_family_asia": 0.1},
                  "book_fallback": {"book": {"OTHER_family_asia": 0.1}}}
    row = {"name": "audchf_overnight_gap_decay_asia_p_hash_principal",
           "symbol": "AUDCHF", "family": "overnight_gap_decay", "selector": "asia",
           "risk_frac": 0.1, "status": "LIVE"}
    alloc = tmp_path / "allocation.json"
    sleeves = tmp_path / "sleeves.json"
    alloc.write_text(json.dumps(allocation))
    sleeves.write_text(json.dumps({"sleeves": [row]}))
    monkeypatch.setattr(join, "ALLOC", alloc)
    monkeypatch.setattr(join, "SLEEVES", sleeves)
    monkeypatch.setattr(liveness, "DATA", tmp_path)
    if enabled is not None:
        (tmp_path / "CERT_BOOK_LIVE.json").write_text(json.dumps({
            "enabled": enabled, "fusion": {"AUDCHF_overnight_gap_decay_asia": value}}))
    measurement = join.measure()
    book = liveness._live_book(allocation, allocation["book"])
    assert measurement["status"] == status
    assert book["n_joined"] == n_joined
    if case == "principal":
        assert book["rows"][row["name"]]["allocation_source"] == "principal_cert_book"
        assert book["rows"][row["name"]]["frac"] == 0.1
        assert measurement["books"]["dynamic"]["raw_allocator_joined"] == 0
    if case == "zero":
        assert book["rows"][row["name"]]["frac"] == 0.0
    assert allocation["book"] == {"OTHER_family_asia": 0.1}
