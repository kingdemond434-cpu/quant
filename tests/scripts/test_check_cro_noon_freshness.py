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
    p = _ledger(tmp_path, [{"lane": "noon", "event": "end", "rc": 0,
                            "at": "2026-10-29T11:30:00+00:00"},
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
                     "--now", "2026-10-29T15:00:00+00:00"]) == chk.EXIT_RED == 2
    doc = json.loads(out.read_text("utf-8"))
    assert doc["status"] == "RED" and doc["last_noon_lane"] == "noon_box"
    assert doc["age_h"] > 26 and doc["noon_rows"] == 2


def test_absence_is_red_never_green(tmp_path: Path) -> None:
    now = chk.datetime.fromisoformat("2026-10-29T15:00:00+00:00")
    assert chk.measure(tmp_path / "missing.jsonl", now)["status"] == "RED"
    p = _ledger(tmp_path, [{"lane": "midnight", "at": "2026-10-29T01:00:00+00:00"}, "not json"])
    doc = chk.measure(p, now)
    assert doc["status"] == "RED" and doc["why"] == "no landed noon pass in the ledger"
    assert doc["malformed_rows"] == 1


def test_a_date_only_row_counts_from_its_day(tmp_path: Path) -> None:
    p = _ledger(tmp_path, [{"lane": "noon_box", "date": "2026-10-29"}])
    now = chk.datetime.fromisoformat("2026-10-29T20:00:00+00:00")
    doc = chk.measure(p, now)
    assert doc["status"] == "GREEN" and doc["last_noon_date_only"] is True
    assert "date-only" in doc["why"]


def test_a_pass_that_started_or_failed_never_reads_green(tmp_path: Path) -> None:
    # Auditor probe (#439 stack, 2026-10-29): a start row plus an rc=1 end row read GREEN.
    p = _ledger(tmp_path, [{"lane": "noon", "event": "start", "at": "2026-10-29T11:02:00+00:00"},
                           {"lane": "noon", "event": "end", "rc": 1,
                            "at": "2026-10-29T13:00:00+00:00"}])
    now = chk.datetime.fromisoformat("2026-10-29T15:00:00+00:00")
    doc = chk.measure(p, now)
    assert doc["status"] == "RED" and doc["noon_rows"] == 2 and doc["landed_rows"] == 0


def test_a_future_row_is_malformed_not_fresh(tmp_path: Path) -> None:
    p = _ledger(tmp_path, [{"lane": "noon_box", "at": "2027-01-01T00:00:00+00:00"}])
    now = chk.datetime.fromisoformat("2026-10-29T15:00:00+00:00")
    doc = chk.measure(p, now)
    assert doc["status"] == "RED" and doc["future_rows"] == 1 and doc["malformed_rows"] == 1


def test_a_bom_first_row_counts_and_bad_bytes_are_red(tmp_path: Path) -> None:
    p = tmp_path / "bom.jsonl"
    row = {"lane": "noon", "event": "end", "rc": 0, "at": "2026-10-29T13:00:00+00:00"}
    p.write_bytes(b"\xef\xbb\xbf" + json.dumps(row).encode() + b"\n")
    now = chk.datetime.fromisoformat("2026-10-29T15:00:00+00:00")
    assert chk.measure(p, now)["status"] == "GREEN"
    bad = tmp_path / "bad.jsonl"
    bad.write_bytes(b"\xff\xfe\x00garbage")
    assert chk.measure(bad, now)["status"] == "RED"


def _state(tmp_path: Path, rc: int | None, at: str | None) -> Path:
    p = tmp_path / "CRO_NOON_STATE.json"
    p.write_text(json.dumps({"lane": "noon", "last_rc": rc, "last_rc_at": at}), "utf-8")
    return p


def test_a_non_zero_launch_after_the_last_landing_is_red(tmp_path: Path) -> None:
    """K6: an early exit (rc 5, lease not acquired) writes no ledger row; the published lane
    state carries it, and a fresh ledger must not hide it."""
    p = _ledger(tmp_path, [{"lane": "noon", "event": "end", "rc": 0,
                            "at": "2026-11-16T12:30:00+00:00"}])
    now = chk.datetime.fromisoformat("2026-11-17T13:00:00+00:00")
    st = _state(tmp_path, 5, "2026-11-17T12:00:05+00:00")
    doc = chk.measure(p, now, state=st)
    assert doc["status"] == "RED" and "rc=5" in doc["why"] and doc["last_launch_rc"] == 5


def test_a_landing_after_the_failed_launch_stays_green(tmp_path: Path) -> None:
    p = _ledger(tmp_path, [{"lane": "noon", "event": "end", "rc": 0,
                            "at": "2026-11-17T14:00:00+00:00"}])
    now = chk.datetime.fromisoformat("2026-11-17T15:00:00+00:00")
    st = _state(tmp_path, 1, "2026-11-17T12:10:00+00:00")
    assert chk.measure(p, now, state=st)["status"] == "GREEN"


def test_an_absent_or_clean_state_changes_nothing(tmp_path: Path) -> None:
    p = _ledger(tmp_path, [{"lane": "noon", "event": "end", "rc": 0,
                            "at": "2026-11-17T12:30:00+00:00"}])
    now = chk.datetime.fromisoformat("2026-11-17T15:00:00+00:00")
    doc = chk.measure(p, now, state=tmp_path / "absent.json")
    assert doc["status"] == "GREEN" and doc["published_state"] == "UNMEASURED"
    st = _state(tmp_path, 0, "2026-11-17T13:00:00+00:00")
    assert chk.measure(p, now, state=st)["status"] == "GREEN"


def test_the_artifact_carries_no_local_path(tmp_path: Path) -> None:
    p = _ledger(tmp_path, [])
    doc = chk.measure(p, chk.datetime.fromisoformat("2026-11-17T15:00:00+00:00"))
    assert not str(doc["ledger"]).startswith("/") and ":\\" not in str(doc["ledger"])
