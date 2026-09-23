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
