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


def test_the_verdict_crosses_the_wire_off_the_box() -> None:
    # The noon routine and the coordinator read this verdict from origin. For a week it was
    # written on the box and never published: `**/reports/*` ignored it and the sync never
    # listed it, so the RED this check exists to raise reached nobody off the box.
    import subprocess

    from libs.ops.state_publication import published_paths
    rel = chk.ARTIFACT.relative_to(ROOT).as_posix()
    assert rel in published_paths(ROOT)
    ignored = subprocess.run(["git", "check-ignore", "-q", rel], cwd=ROOT)
    assert ignored.returncode == 1, f"{rel} is gitignored, so the sync would publish nothing"


def test_the_leg_runs_where_a_never_run_leg_is_admitted() -> None:
    # On the box the core plan admitted only its always-run legs for a week, so this leg sat in
    # NEVER RUN and its report never existed. It belongs to the meta department plan.
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "hourly_cycle_for_plan", ROOT / "desks" / "mt5" / "research" / "hourly_cycle.py")
    assert spec and spec.loader
    hc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hc)
    assert "cro_noon_freshness" not in hc.CORE_LEGS
    assert hc.department_of("cro_noon_freshness") == "meta"
    assert hc.in_plan("cro_noon_freshness", "dept:meta")
    from libs.ops.leg_rotation import ALWAYS_RUN
    assert "cro_noon_freshness" in ALWAYS_RUN
