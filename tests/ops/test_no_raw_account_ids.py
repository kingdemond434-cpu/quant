"""scripts/check_no_raw_account_ids.py: a raw account number in a tracked file is a FAIL over its
floor, the value is never printed, and the floor only lets a file shrink."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import check_no_raw_account_ids as fence  # noqa: E402

FAKE = 81234567


@pytest.mark.parametrize("value,want", [
    (FAKE, True), (str(FAKE), True), (float(FAKE), True), (12345, True),
    (9999, False), (True, False), (None, False), ("sha256:0123456789abcdef", False),
    ("FusionMarkets-Live", False), ("1234567890123", False),
])
def test_is_raw_id(value: object, want: bool) -> None:
    assert fence.is_raw_id(value) is want


def test_count_in_reads_identifier_keys_at_any_depth() -> None:
    doc = {"account": FAKE, "deal": FAKE, "symbols": {"EURUSD": {"login": str(FAKE)}},
           "rows": [{"account_key": "sha256:00", "account": None}]}
    assert fence.count_in(doc) == 2


def _repo(tmp_path: Path, files: dict[str, str], floor: dict[str, int]) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    for rel, text in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    fl = tmp_path / "floor.json"
    fl.write_text(json.dumps({"files": floor}), encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
    return fl


def test_a_new_file_fails_and_never_prints_the_value(tmp_path: Path) -> None:
    fl = _repo(tmp_path, {"desks/mt5/data/x.jsonl": json.dumps({"account": FAKE}) + "\n"}, {})
    rep = fence.census(tmp_path, fl)
    assert rep["status"] == "FAIL"
    assert rep["arrivals"] == {"desks/mt5/data/x.jsonl": {"count": 1, "floor": 0}}
    assert str(FAKE) not in json.dumps(rep)


def test_the_floor_holds_legacy_rows_and_a_new_row_over_it_fails(tmp_path: Path) -> None:
    rows = "".join(json.dumps({"account": FAKE + i}) + "\n" for i in range(3))
    fl = _repo(tmp_path, {"l.jsonl": rows}, {"l.jsonl": 3})
    assert fence.census(tmp_path, fl)["status"] == "OK"
    (tmp_path / "l.jsonl").write_text(rows + json.dumps({"account": FAKE}) + "\n",
                                      encoding="utf-8")
    assert fence.census(tmp_path, fl)["status"] == "FAIL"


def test_a_healed_file_passes_and_is_named(tmp_path: Path) -> None:
    fl = _repo(tmp_path, {"b.json": json.dumps({"account_key": "sha256:00"})},
               {"b.json": 249})
    rep = fence.census(tmp_path, fl)
    assert rep["status"] == "OK"
    assert rep["healed"] == {"b.json": {"count": 0, "floor": 249}}


def test_mined_public_records_are_out_of_scope(tmp_path: Path) -> None:
    fl = _repo(tmp_path, {"data/intelligence/site/r.json": json.dumps({"account_id": str(FAKE)})},
               {})
    assert fence.census(tmp_path, fl)["status"] == "OK"


def test_a_missing_floor_is_unmeasured_and_fails(tmp_path: Path) -> None:
    _repo(tmp_path, {"a.json": "{}"}, {})
    rep = fence.census(tmp_path, tmp_path / "absent.json")
    assert rep["status"] == "UNMEASURED"


def test_the_committed_tree_passes() -> None:
    assert fence.census()["status"] == "OK"
