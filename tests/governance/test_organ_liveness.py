"""R0144 organ liveness -- installed, running and PRODUCING are three different facts.

An organ can pass the manifest check, appear in `crontab -l`, and have emitted nothing for a week.
That is how a miner goes dark unnoticed: nothing errors, no page fires, and the board stays green
because the board was only checking that the LINE existed.
"""
from __future__ import annotations

import os
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


def test_an_output_this_fence_cannot_watch_is_COUNTED_not_silently_dropped(tmp_path):
    """An organ declaring `reports/x.json` is neither green nor red -- it is ABSENT.

    Until this was counted it shared a silent `continue` with an organ that declared nothing at
    all, and the two demand opposite repairs: a missing EVIDENCE line is check_build_standard's
    problem, an unwatchable path is this parser's scope. 14 of the desk's real organs sit here,
    including resolve_llm_trader_book.py. n_checked read as full coverage and was not (L1.60).
    """
    man = (
        '# EVIDENCE: scripts/a.py -> data/a.json\n'
        '0 * * * * cd "$Q" && python scripts/a.py\n'
        '# EVIDENCE: scripts/r.py -> reports/r.json\n'
        '0 * * * * cd "$Q" && python scripts/r.py\n'
        '# no evidence line at all\n'
        '0 * * * * cd "$Q" && python scripts/n.py\n'
    )
    (tmp_path / "ops").mkdir()
    (tmp_path / "ops/crontab.manifest").write_text(man, encoding="utf-8")
    (tmp_path / "data").mkdir()
    (tmp_path / "data/a.json").write_text("{}", encoding="utf-8")

    rows = parse_manifest(man)
    assert rows[1]["artifacts"] == []                       # still not watched...
    assert rows[1]["unwatchable"] == ["reports/r.json"]     # ...but no longer invisible

    out = audit(tmp_path)
    assert out["n_checked"] == 1
    assert out["n_unwatchable_path"] == 1
    assert out["n_skipped_no_evidence"] == 1
    assert out["n_scheduled_seen"] == 3
    assert out["unwatchable"] == [{"script": "scripts/r.py", "declared": ["reports/r.json"]}]
    # The skip must NOT be laundered into a pass: an unwatchable organ is not counted fresh.
    assert out["n_fresh"] == 1


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
    # b2.jsonl IS written here. It used to be omitted, and the fence still said OK -- this very
    # fixture was the R0418 hole in miniature: scripts/b.py declares `data/b.json + data/b2.jsonl`
    # and the suite asserted a clean sweep while one declared output had never existed.
    for f in ("a.json", "b.json", "b2.jsonl"):
        (tmp_path / "data" / f).write_text("{}")
    rep = audit(tmp_path)
    assert rep["status"] == "OK" and rep["n_fresh"] == rep["n_checked"]


def test_one_live_artifact_does_not_hide_an_absent_sibling(tmp_path):
    """R0418. `age = min(fresh)` over the SURVIVING artifacts was the whole verdict.

    scripts/b.py declares `data/b.json + data/b2.jsonl`. Write only the first and the row read
    FRESH -- an output that has never once been produced, invisible because a neighbour in the
    same EVIDENCE block was young. The identical artifact, absent ALONE, is NEVER-PRODUCED and
    pages. Same fact, opposite verdict, decided by a neighbour (L1.28a/L1.60).
    """
    (tmp_path / "ops").mkdir()
    (tmp_path / "data").mkdir()
    (tmp_path / "ops/crontab.manifest").write_text(_MAN)
    (tmp_path / "data/a.json").write_text("{}")
    (tmp_path / "data/b.json").write_text("{}")          # b2.jsonl deliberately absent
    rep = audit(tmp_path)
    row = {o["script"]: o for o in rep["organs"]}["scripts/b.py"]
    assert row["state"] == "PARTIAL"                     # not FRESH
    assert row["missing_artifacts"] == ["data/b2.jsonl"]
    assert row["artifact_age_h"]["data/b2.jsonl"] is None
    assert rep["status"] == "DARK"                       # and it reaches the verdict
    assert rep["n_fresh"] < rep["n_checked"]


def test_the_stalest_declared_output_is_published_not_swallowed(tmp_path):
    """min() is KEPT, and the spread it hides is published beside it.

    Switching to max() was measured on the 9 real multi-artifact organs (2026-08-13) and flips 2
    to STALE -- both because their second output is a CONDITIONAL append-only log
    (run_organ_er.py:244 appends only on a treatment attempt, run_conviction_trader.py:1442 only
    on a fill). Quiet is not death there, and a board that is red most mornings is one nobody
    reads. So the laggard is NAMED rather than used as the verdict.
    """
    (tmp_path / "ops").mkdir()
    (tmp_path / "data").mkdir()
    (tmp_path / "ops/crontab.manifest").write_text(_MAN)
    for f in ("a.json", "b.json", "b2.jsonl"):
        (tmp_path / "data" / f).write_text("{}")
    old = time.time() - 400 * 3600
    os.utime(tmp_path / "data/b2.jsonl", (old, old))
    rep = audit(tmp_path)
    row = {o["script"]: o for o in rep["organs"]}["scripts/b.py"]
    assert row["state"] == "FRESH"                       # conditional log, still trusted
    assert row["age_h"] < 1                              # the optimistic number is unchanged...
    assert row["age_h_stalest"] > 399                    # ...and the gap it hid is now readable
    assert row["artifact_age_h"]["data/b2.jsonl"] > 399


def test_tolerance_is_loose_enough_that_one_missed_tick_is_not_a_failure(tmp_path):
    # A board that is red most mornings is a board nobody reads.
    (tmp_path / "ops").mkdir()
    (tmp_path / "data").mkdir()
    (tmp_path / "ops/crontab.manifest").write_text(_MAN)
    (tmp_path / "data/a.json").write_text("{}")
    (tmp_path / "data/b.json").write_text("{}")
    missed_one = time.time() - 1.5 * 3600          # hourly organ, one tick late
    os.utime(tmp_path / "data/a.json", (missed_one, missed_one))
    assert {o["script"]: o["state"] for o in audit(tmp_path)["organs"]}["scripts/a.py"] == "FRESH"
    assert STALE_MULTIPLE >= 3.0 and MIN_TOLERANCE_H >= 2.0


def test_an_unreadable_manifest_is_unmeasured_not_ok(tmp_path):
    rep = audit(tmp_path)
    assert rep["status"] == "UNMEASURED" and rep["organs"] == []
