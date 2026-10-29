"""The noon CRO pass turns RED when it stops landing (rule 23's RED check, 2026-10-29)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import check_cro_noon_freshness as chk  # noqa: E402


def _ledger(tmp_path: Path, rows: list[dict | str]) -> Path:
    p = tmp_path / "cro_cycle_ledger.jsonl"
    p.write_text("\n".join(r if isinstance(r, str) else json.dumps(r) for r in rows) + "\n",
                 "utf-8")
    return p


def test_a_fresh_noon_row_is_green(tmp_path: Path) -> None:
    p = _ledger(tmp_path, [{"lane": "noon", "event": "end", "at": "2026-10-29T11:30:00+00:00"},
                           {"lane": "midnight", "at": "2026-10-29T23:00:00+00:00"}])
    out = tmp_path / "out.json"
    assert chk.main(["--ledger", str(p), "--out", str(out),
                     "--now", "2026-10-30T09:00:00+00:00"]) == 0
    doc = json.loads(out.read_text("utf-8"))
    assert doc["status"] == "GREEN" and doc["age_h"] == 21.5 and doc["last_noon_lane"] == "noon"


def test_the_newest_noon_row_older_than_26h_is_red(tmp_path: Path) -> None:
    # The measured case: two noon rows in a month, the newest 10-21, read on 10-29.
    p = _ledger(tmp_path, [{"lane": "noon", "date": "2026-09-30",
                            "at": "2026-09-30T11:45:00+00:00"},
                           {"lane": "noon_box", "date": "2026-10-21",
                            "at": "2026-10-21T11:40:00+00:00"},
                           {"lane": "midnight", "at": "2026-10-29T01:00:00+00:00"}])
    out = tmp_path / "out.json"
    assert chk.main(["--ledger", str(p), "--out", str(out),
                     "--now", "2026-10-29T15:00:00+00:00"]) == 1
    doc = json.loads(out.read_text("utf-8"))
    assert doc["status"] == "RED" and doc["last_noon_lane"] == "noon_box"
    assert doc["age_h"] > 26 and doc["noon_rows"] == 2


def test_absence_is_red_never_green(tmp_path: Path) -> None:
    now = chk.datetime.fromisoformat("2026-10-29T15:00:00+00:00")
    assert chk.measure(tmp_path / "missing.jsonl", now)["status"] == "RED"
    p = _ledger(tmp_path, [{"lane": "midnight", "at": "2026-10-29T01:00:00+00:00"}, "not json"])
    doc = chk.measure(p, now)
    assert doc["status"] == "RED" and doc["why"] == "no noon row in the ledger"
    assert doc["malformed_rows"] == 1


def test_a_date_only_row_counts_from_its_day(tmp_path: Path) -> None:
    p = _ledger(tmp_path, [{"lane": "noon_box", "date": "2026-10-29"}])
    now = chk.datetime.fromisoformat("2026-10-29T20:00:00+00:00")
    assert chk.measure(p, now)["status"] == "GREEN"
