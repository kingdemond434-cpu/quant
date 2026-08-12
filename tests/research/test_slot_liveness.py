"""Twelve forward slots, zero accruing, twenty-six survivors queued -- and no alarm anywhere.

MEASURED 2026-08-12 on the live roster. Every sleeve read NO-EVIDENCE at 6.8 days against a 36h
staleness threshold, and `run_paper_sleeve_forward` said so faithfully on every run: "no rows added
since the baseline -- the source artifact has not been regenerated". That sentence is TRUE of four
completely different situations, and the desk had no way to tell them apart, so the one real defect
in the set -- a clock whose producer was on no schedule at all -- looked exactly like the nine that
were merely stale on an ephemeral container.

These tests pin the DISCRIMINATION, and pin just as hard the two things this module must never do:
score a container's fossil layer as a dead desk, and free a slot by itself.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from libs.research import slot_liveness as sl


def _row(artifact: str, *, rows_added: float = 0.0, age_h: float = 200.0) -> dict:
    start = datetime.now(tz=UTC) - timedelta(hours=age_h)
    return {"origin_artifact": artifact, "rows_added": rows_added,
            "shadow_start": start.isoformat()}


def _desk(tmp_path: Path, *, script: str = "", body: str = "", cron: str = "") -> Path:
    (tmp_path / "scripts").mkdir(parents=True, exist_ok=True)
    (tmp_path / "ops").mkdir(parents=True, exist_ok=True)
    if script:
        (tmp_path / "scripts" / script).write_text(body or "json.dump(x, f)\n", "utf-8")
    (tmp_path / "ops/crontab.manifest").write_text(cron, "utf-8")
    return tmp_path


def _artifact(root: Path, rel: str, *, age_h: float = 0.0) -> None:
    import os
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{}", "utf-8")
    if age_h:
        old = datetime.now(tz=UTC).timestamp() - age_h * 3600
        os.utime(p, (old, old))


# ------------------------------------------------------------------ the four states
def test_a_clock_whose_producer_is_on_no_schedule_is_born_dead(tmp_path: Path) -> None:
    """THE REAL DEFECT IN THE LIVE SET. liquidation_reversion_BTCUSDT's inputs are recorded
    continuously by an always-on systemd service, and the screen that turns them into rows was
    wired to nothing. `n` could never move -- on this box or any other."""
    root = _desk(tmp_path, script="screen_widget.py", body="json.dump(x, f)\n", cron="")
    _artifact(root, "data/widget_screen.json")
    h = sl.assess("c", _row("data/widget_screen.json"), root=root)
    assert h.state == "PRODUCER_UNSCHEDULED"
    assert not h.can_ever_accrue and h.blocks_a_slot
    assert "schedule screen_widget.py" in h.repair


def test_the_repair_is_a_cron_line_never_a_retirement(tmp_path: Path) -> None:
    """A missing organ must never be paid for by discarding a candidate. Retiring the clock would
    tidy the report and throw away the thing the pipeline exists to find."""
    root = _desk(tmp_path, script="screen_widget.py", cron="")
    _artifact(root, "data/widget_screen.json")
    h = sl.assess("c", _row("data/widget_screen.json"), root=root)
    assert "never a reason to retire" in h.repair


def test_a_scheduled_producer_on_a_stale_box_describes_the_box_not_the_desk(tmp_path) -> None:
    """THE LOAD-BEARING DISTINCTION. Nine of the ten live clocks are here. A container reset
    reverts tracked files and leaves data/ as a fossil layer, so a scheduled producer's output is
    routinely days old on a fresh container while the VPS is perfectly healthy. Reading that as a
    dead desk is how a container session concludes the pipeline has collapsed."""
    root = _desk(tmp_path, script="screen_widget.py",
                 cron="17 0 * * * python scripts/screen_widget.py\n")
    _artifact(root, "data/widget_screen.json", age_h=300)
    h = sl.assess("c", _row("data/widget_screen.json"), root=root)
    assert h.state == "SOURCE_STALE_HERE"
    assert h.can_ever_accrue, "a stale container is not a defect in the desk"
    assert not h.blocks_a_slot
    assert "container" in h.why and "VPS" in h.repair


def test_a_running_producer_whose_n_never_moves_is_structurally_frozen(tmp_path) -> None:
    """The subtle one. The producer fires, the file is fresh, and `n` still does not move -- the
    screen's window is FIXED rather than expanding, so this clock cannot resolve however long it
    waits. Waiting is the wrong response and only measurement can tell you that."""
    root = _desk(tmp_path, script="screen_widget.py",
                 cron="17 0 * * * python scripts/screen_widget.py\n")
    _artifact(root, "data/widget_screen.json", age_h=1)
    h = sl.assess("c", _row("data/widget_screen.json", age_h=400), root=root)
    assert h.state == "SOURCE_FROZEN" and h.blocks_a_slot
    assert "fixed" in h.why.lower()


def test_a_young_clock_with_a_fresh_producer_is_early_not_broken(tmp_path) -> None:
    """Zero rows on day one is the ordinary state. A check that called it a defect would page
    every time the pipeline worked."""
    root = _desk(tmp_path, script="screen_widget.py",
                 cron="17 0 * * * python scripts/screen_widget.py\n")
    _artifact(root, "data/widget_screen.json", age_h=1)
    h = sl.assess("c", _row("data/widget_screen.json", age_h=10), root=root)
    assert h.state == "TOO_EARLY" and h.can_ever_accrue and not h.blocks_a_slot


def test_rows_added_settles_it_regardless_of_everything_else(tmp_path) -> None:
    root = _desk(tmp_path, cron="")
    h = sl.assess("c", _row("data/widget_screen.json", rows_added=42), root=root)
    assert h.state == "ACCRUING" and h.can_ever_accrue


# ------------------------------------------------------------------ the detector's own honesty
def test_an_annotator_is_never_mistaken_for_a_producer(tmp_path: Path) -> None:
    """THE BUG THIS DETECTOR SHIPPED AND THEN FIXED, and it failed in the silent direction. The
    first draft took the first script mentioning the artifact path, so
    reports/axis_screens/liquidation_reversion_BTCUSDT.json resolved to finalize_axis_screens.py --
    which walks that directory and rewrites `verdict_adjusted` into files that already exist. A
    REWRITER adds no rows. It is scheduled, so the one genuinely dead clock in the set came back
    healthy and the detector said 'fine' about the only thing it existed to catch.
    """
    root = _desk(tmp_path, cron="8 7 * * * python scripts/finalize_axis_screens.py\n")
    (root / "scripts/finalize_axis_screens.py").write_text(
        'for p in Path("reports/axis_screens").glob("*.json"): p.write_text(x)\n', "utf-8")
    (root / "scripts/screen_liquidation_reversion.py").write_text(
        '_OUT = "reports/axis_screens"\nf.write_text(json.dumps(d))\n', "utf-8")
    producer, scheduled = sl.producer_for(
        "reports/axis_screens/liquidation_reversion_BTCUSDT.json", root)
    assert producer == "screen_liquidation_reversion.py", producer
    assert not scheduled, "and the truth is that the real producer is on no cron line"


def test_a_script_that_never_writes_is_not_a_producer(tmp_path: Path) -> None:
    root = _desk(tmp_path, cron="")
    (root / "scripts/read_widget_screen.py").write_text('json.load(open("x"))\n', "utf-8")
    assert sl.producer_for("data/widget_screen.json", root) == ("", False)


def test_a_directory_walker_that_never_names_the_file_cannot_claim_it(tmp_path) -> None:
    """The name is the evidence. Requiring stem-token overlap is what stops a glob from being
    counted as the author of every file it touches."""
    root = _desk(tmp_path, cron="")
    (root / "scripts/sweep_everything.py").write_text(
        'for p in Path("data").glob("*.json"): p.write_text("{}")\n', "utf-8")
    assert sl.producer_for("data/widget_screen.json", root) == ("", False)


def test_an_unattributable_clock_is_unknown_and_is_never_called_dead(tmp_path) -> None:
    """UNKNOWN must not resolve toward retirement. A clock nobody can attribute is unauditable in
    BOTH directions, and only one of those errors discards a real candidate."""
    h = sl.assess("c", {"rows_added": 0.0}, root=tmp_path)
    assert h.state == "UNKNOWN"
    assert h.can_ever_accrue and not h.blocks_a_slot


# ------------------------------------------------------------------ what it must never do
def test_the_report_claims_no_authority_over_any_slot() -> None:
    """Retirement SHRINKS the Holm m and LOOSENS every standing clock's bar -- slot_registry's own
    words: over-counting only tightens (the safe error), under-counting admits noise as edge. With
    26 survivors queued the pressure to automate this away is permanent and it points the wrong
    way. The decision was never hard; nothing triggered it."""
    rep = sl.report({}, root=Path(__file__).resolve().parents[2])
    assert rep["authority"].startswith("MEASUREMENT ONLY")
    assert "retires no clock" in rep["authority"]
    assert "LOOSENS" in rep["authority"]

    mod = Path(__file__).resolve().parents[2] / "libs/research/slot_liveness.py"
    src = mod.read_text("utf-8")
    for forbidden in ("MAX_FORWARD_SLOTS =", "write_snapshot(", "shadow_sleeves.json"):
        assert forbidden not in src, (
            f"{forbidden!r} appears in a report-only module -- nothing here may resize the cohort "
            "or edit the roster")


def test_the_live_desk_report_is_shaped_for_a_decision(tmp_path: Path) -> None:
    """A finding with no named repair is a complaint. Every non-accruing clock has to carry the
    thing a person would actually do about it."""
    root = _desk(tmp_path, script="screen_widget.py", cron="")
    _artifact(root, "data/widget_screen.json")
    rep = sl.report({"c": _row("data/widget_screen.json")}, root=root)
    assert rep["n_clocks"] == 1 and rep["accruing"] == 0
    assert rep["slots_blocked_by_a_clock_that_cannot_accrue"] == 1
    assert rep["repairable_by_scheduling_a_producer"][0]["producer"] == "screen_widget.py"
    for c in rep["clocks"]:
        if c["state"] != "ACCRUING":
            assert c["why"] and c["repair"], f"{c['name']} says nothing actionable"


# ------------------------------------------------------------------ the wiring
def test_the_checker_is_scheduled_and_pages() -> None:
    """L1.40: a detector nobody runs is a comment. This one exists because twelve slots sat at
    zero for 6.8 days with nothing looking."""
    root = Path(__file__).resolve().parents[2]
    man = (root / "ops/crontab.manifest").read_text("utf-8")
    lines = [ln for ln in man.splitlines()
             if "check_slot_liveness.py" in ln and ln[:1].isdigit()]
    assert lines, "the liveness check is on no schedule"
    assert any("--page" in ln for ln in lines), "it must page; a log nobody reads is not an alarm"


def test_the_producer_that_was_missing_is_now_scheduled() -> None:
    """THE REPAIR ITSELF, pinned. screen_liquidation_reversion.py had no cron line, so one forward
    clock could never accrue while its inputs piled up untouched."""
    root = Path(__file__).resolve().parents[2]
    man = (root / "ops/crontab.manifest").read_text("utf-8")
    assert any("screen_liquidation_reversion.py" in ln and ln[:1].isdigit()
               for ln in man.splitlines()), "the born-dead clock's producer is unscheduled again"


def test_the_spawner_runs_after_the_screens_that_feed_it() -> None:
    """A survivor found at 10:37 used to wait 22 hours for the next 08:45 pass. The second pass
    exists to make 'promote to shadow immediately' mean minutes rather than a day."""
    root = Path(__file__).resolve().parents[2]
    man = (root / "ops/crontab.manifest").read_text("utf-8")
    hhmm = []
    for ln in man.splitlines():
        if "run_paper_sleeve_spawner.py" in ln and ln[:1].isdigit():
            mi, hr = ln.split()[0], ln.split()[1]
            hhmm.append(int(hr) * 60 + int(mi))
    assert len(hhmm) >= 2, f"only {len(hhmm)} spawner pass(es) -- the late screens are unread"
    # The VRP screen lands at 10:37; a pass must follow it on the SAME day.
    assert max(hhmm) > 10 * 60 + 37, "no spawner pass reads the 10:37 screen on the day it runs"
    # ...and before the 11:15 forward runner, so a new sleeve is observed on the same cycle.
    assert max(hhmm) < 11 * 60 + 15, ("the late pass spawns AFTER the forward runner, so a new "
                                      "sleeve waits another day just to be observed")


def test_the_second_pass_shares_the_first_passes_lock() -> None:
    """Two schedules, one organ, one lock. A race a flock cannot serialise is the R0048 shape."""
    root = Path(__file__).resolve().parents[2]
    locks = {ln.split("flock -n ")[1].split()[0]
             for ln in (root / "ops/crontab.manifest").read_text("utf-8").splitlines()
             if "run_paper_sleeve_spawner.py" in ln and ln[:1].isdigit() and "flock -n " in ln}
    assert len(locks) == 1, f"the spawner's passes use different locks: {locks}"


def test_no_pass_raises_the_cohort_cap() -> None:
    """THE LINE THAT MUST NOT BE CROSSED. With 26 survivors queued, the fastest way to 'promote
    them all' is to raise the cap -- which breaks the fixed-for-life forward bar the standing
    clocks were admitted under and manufactures survivors rather than finding them."""
    from libs.research.slot_registry import MAX_FORWARD_SLOTS
    assert MAX_FORWARD_SLOTS == 12
    root = Path(__file__).resolve().parents[2]
    man = (root / "ops/crontab.manifest").read_text("utf-8")
    for ln in man.splitlines():
        if "run_paper_sleeve_spawner.py" in ln:
            assert "--cap" not in ln and "MAX_FORWARD_SLOTS" not in ln, ln


def test_the_liveness_artifact_is_json_a_container_can_read() -> None:
    root = Path(__file__).resolve().parents[2]
    p = root / "data/slot_liveness.json"
    if p.exists():
        d = json.loads(p.read_text("utf-8"))
        assert "authority" in d and "clocks" in d
