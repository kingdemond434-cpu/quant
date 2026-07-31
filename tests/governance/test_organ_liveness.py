"""R0144 organ liveness -- installed, running and PRODUCING are three different facts.

An organ can pass the manifest check, appear in `crontab -l`, and have emitted nothing for a week.
That is how a miner goes dark unnoticed: nothing errors, no page fires, and the board stays green
because the board was only checking that the LINE existed.
"""
from __future__ import annotations

import time

from scripts.check_organ_liveness import (
    MIN_TOLERANCE_H,
    STALE_MULTIPLE,
    audit,
    cadence_hours,
    parse_manifest,
)

_MAN = """# EVIDENCE: scripts/a.py -> data/a.json; docs/CONSTITUTION.md L1.1
0 * * * * cd "$Q" && python scripts/a.py
# EVIDENCE: scripts/b.py -> data/b.json + data/b2.jsonl
0 4 * * * cd "$Q" && python scripts/b.py
# no evidence line for this one
*/5 * * * * cd "$Q" && python scripts/c.py
"""


def test_the_semicolon_separator_is_parsed():
    # The first version missed ';', so `data/a.json; docs/...` parsed as `data/a.json;` and every
    # such organ read NEVER-PRODUCED. A wrongly-red board gets disabled -- worse than no fence.
    rows = parse_manifest(_MAN)
    assert rows[0]["artifacts"] == ["data/a.json"]
    assert rows[1]["artifacts"] == ["data/b.json", "data/b2.jsonl"]
    assert rows[2]["artifacts"] == []          # no declared evidence -> not this fence's problem


def test_cadence_is_derived_from_the_cron_expression():
    assert abs(cadence_hours("0 * * * *") - 1.0) < 1e-9
    assert abs(cadence_hours("*/15 * * * *") - 0.25) < 1e-9
    assert abs(cadence_hours("0 4 * * *") - 24.0) < 1e-9
    assert abs(cadence_hours("0 4 * * 0") - 24.0 * 7) < 1e-6
    assert cadence_hours("garbage") is None


def test_an_organ_that_never_wrote_its_artifact_is_distinguished_from_one_that_stopped(tmp_path):
    # Different diagnoses -- NEVER-PRODUCED is wiring, STALE is auth/quota/upstream. Collapsing
    # them sends someone to debug the wrong thing.
    (tmp_path / "ops").mkdir()
    (tmp_path / "data").mkdir()
    (tmp_path / "ops/crontab.manifest").write_text(_MAN)
    (tmp_path / "data/b.json").write_text("{}")
    old = time.time() - 500 * 3600
    import os
    os.utime(tmp_path / "data/b.json", (old, old))
    rep = audit(tmp_path)
    states = {o["script"]: o["state"] for o in rep["organs"]}
    assert states["scripts/a.py"] == "NEVER-PRODUCED"
    assert states["scripts/b.py"] == "STALE"
    assert rep["status"] == "DARK"
    assert "WIRING" in rep["diagnosis"] and "STOPPED" in rep["diagnosis"]


def test_a_fresh_organ_passes(tmp_path):
    (tmp_path / "ops").mkdir()
    (tmp_path / "data").mkdir()
    (tmp_path / "ops/crontab.manifest").write_text(_MAN)
    for f in ("a.json", "b.json"):
        (tmp_path / "data" / f).write_text("{}")
    rep = audit(tmp_path)
    assert rep["status"] == "OK" and rep["n_fresh"] == rep["n_checked"]


def test_tolerance_is_loose_enough_that_one_missed_tick_is_not_a_failure(tmp_path):
    # A board that is red most mornings is a board nobody reads.
    (tmp_path / "ops").mkdir()
    (tmp_path / "data").mkdir()
    (tmp_path / "ops/crontab.manifest").write_text(_MAN)
    import os
    (tmp_path / "data/a.json").write_text("{}")
    (tmp_path / "data/b.json").write_text("{}")
    missed_one = time.time() - 1.5 * 3600          # hourly organ, one tick late
    os.utime(tmp_path / "data/a.json", (missed_one, missed_one))
    assert {o["script"]: o["state"] for o in audit(tmp_path)["organs"]}["scripts/a.py"] == "FRESH"
    assert STALE_MULTIPLE >= 3.0 and MIN_TOLERANCE_H >= 2.0


def test_an_unreadable_manifest_is_unmeasured_not_ok(tmp_path):
    rep = audit(tmp_path)
    assert rep["status"] == "UNMEASURED" and rep["organs"] == []
