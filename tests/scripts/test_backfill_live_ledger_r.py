"""The zero-R backfill recomputes only floored rows, labels the basis, and never invents."""
from __future__ import annotations

import json
from pathlib import Path

from scripts import backfill_live_ledger_r as bf


def test_backfill_recomputes_floored_rows_only(tmp_path: Path):
    rows = [
        {"sleeve": "a", "entry_price": 0.81911, "sl": 0.82042, "volume": 0.03,
         "contract_size": 100000.0, "pl_quote": 1.34, "r_multiple": 0.0,
         "r_unreconstructible": False},
        {"sleeve": "b", "entry_price": 2400.0, "sl": 2390.0, "volume": 0.02,
         "contract_size": 100.0, "pl_quote": -20.0, "r_multiple": -1.0},
        {"sleeve": "c", "entry_price": 0.0, "sl": 0.0, "volume": 0.01, "contract_size": 1.0,
         "pl_quote": 5.0, "r_multiple": 0.0, "r_unreconstructible": True},
        {"sleeve": "d", "entry_price": 1.1, "sl": 1.1, "volume": 0.01, "contract_size": 1.0,
         "pl_quote": 5.0, "r_multiple": 0.0},
    ]
    new, counts = bf.backfill(rows)
    assert counts == {"rows": 4, "backfilled": 1, "kept": 2, "unreconstructible": 1}
    a = new[0]
    assert a["r_backfilled"] is True and a["r_multiple_before"] == 0.0
    assert abs(a["r_multiple"] - 1.34 / (0.00131 * 100000.0 * 0.03)) < 1e-3
    assert new[1]["r_multiple"] == -1.0 and "r_backfilled" not in new[1]
    assert new[3]["r_unreconstructible"] is True and "zero distance" in new[3]["r_backfill_why"]
    # idempotent: a second pass changes nothing
    again, counts2 = bf.backfill(new)
    assert counts2["backfilled"] == 0 and again[0]["r_multiple"] == a["r_multiple"]


def test_cli_rewrites_in_place_only_with_apply(tmp_path: Path):
    p = tmp_path / "live_ledger.jsonl"
    row = {"entry_price": 1.0, "sl": 0.99, "volume": 1.0, "contract_size": 100.0,
           "pl_quote": 2.0, "r_multiple": 0.0}
    p.write_text(json.dumps(row) + "\nnot json\n", encoding="utf-8")
    assert bf.main(["--ledger", str(p)]) == 0
    assert json.loads(p.read_text(encoding="utf-8").splitlines()[0])["r_multiple"] == 0.0
    assert bf.main(["--ledger", str(p), "--apply"]) == 0
    lines = p.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "not json"                       # unparsed lines are kept verbatim
    assert abs(json.loads(lines[1])["r_multiple"] - 2.0) < 1e-9


def test_sealed_backfill_cannot_replace_evidence(tmp_path, monkeypatch):
    import pytest
    monkeypatch.setattr(bf, 'ROOT', tmp_path)
    desk = tmp_path / 'desks/mt5/data'
    desk.mkdir(parents=True)
    p = desk / 'live_ledger.jsonl'
    row = {'entry_price': 1.0, 'sl': 0.99, 'volume': 1.0, 'contract_size': 100.0,
           'pl_quote': 2.0, 'r_multiple': 0.0}
    original = (json.dumps(row) + '\n').encode()
    p.write_bytes(original)
    manifest = desk / 'IMMUTABLE_MANIFEST.json'
    seal = {'append_only': {'desks/mt5/data/live_ledger.jsonl':
                           {'records': 1, 'prefix_sha': 'preserve-this-seal'}}}
    manifest.write_text(json.dumps(seal))
    seal_bytes = manifest.read_bytes()
    assert bf.main(['--ledger', str(p)]) == 0
    with pytest.raises(RuntimeError, match='1 sealed records'):
        bf.main(['--ledger', str(p), '--apply'])
    assert p.read_bytes() == original
    assert manifest.read_bytes() == seal_bytes
    assert not p.with_suffix('.jsonl.tmp').exists()


def test_missing_or_corrupt_canonical_seal_is_not_rewrite_authority(tmp_path, monkeypatch):
    import pytest
    monkeypatch.setattr(bf, 'ROOT', tmp_path)
    p = tmp_path / 'desks/mt5/data/live_ledger.jsonl'
    p.parent.mkdir(parents=True)
    p.write_text('original evidence')
    for body in (None, 'not json', '{}', '{"append_only": []}'):
        manifest = p.parent / 'IMMUTABLE_MANIFEST.json'
        if body is not None:
            manifest.write_text(body)
        with pytest.raises(RuntimeError, match='Cannot prove'):
            bf.assert_unsealed_for_rewrite(p)
        assert p.read_text() == 'original evidence'
