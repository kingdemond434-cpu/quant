"""R0215 -- a dark organ is diagnosed and TREATED the same day, not merely counted."""
from __future__ import annotations

import json

from scripts.run_organ_er import (
    _SECONDARY,
    COMA_HOURS,
    build_report,
    diagnose,
)


def _ward(tmp_path, *, manifest="0 * * * * run_toy.py\n", log=""):
    (tmp_path / "data/cro_ai_logs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "ops").mkdir(exist_ok=True)
    (tmp_path / "ops/crontab.manifest").write_text(manifest, "utf-8")
    if log:
        (tmp_path / "data/cro_ai_logs/toy.log").write_text(log, "utf-8")
    return tmp_path


def _runner(tmp_path, name, body):
    d = tmp_path / "scripts"
    d.mkdir(exist_ok=True)
    (d / name).write_text(body, "utf-8")
    return f"scripts/{name}"


# ---- triage: the treatment depends entirely on the cause ---------------------------------------

def test_unscheduled_is_not_treated_by_re_firing(tmp_path):
    """Re-firing an organ nothing ever scheduled hides the real fault forever."""
    _ward(tmp_path, manifest="nothing here\n")
    d = diagnose(tmp_path, "toy", "data/toy.json", 1.0, manifest="nothing here")
    assert d["state"] == "UNSCHEDULED" and d["treatable_here"] is False
    assert "manifest line" in d["action"]


def test_a_blocked_organ_escalates_instead_of_burning_a_slot_per_tick(tmp_path):
    """No re-fire fixes a patient whose treatment is a credit card."""
    _ward(tmp_path, log="openrouter returned 402 payment required")
    d = diagnose(tmp_path, "toy", "data/toy.json", 1.0, manifest="run_toy.py")
    assert d["state"] == "BLOCKED" and d["treatable_here"] is False


def test_transient_is_starved_and_gets_a_re_fire(tmp_path):
    _ward(tmp_path, log="HTTP 529 overloaded, retry later")
    d = diagnose(tmp_path, "toy", "data/toy.json", 1.0, manifest="run_toy.py")
    assert d["state"] == "STARVED" and d["treatable_here"] is True


def test_a_crash_is_treated_once_then_escalated_with_its_error(tmp_path):
    _ward(tmp_path, log="Traceback (most recent call last): ValueError: boom")
    d = diagnose(tmp_path, "toy", "data/toy.json", 1.0, manifest="run_toy.py")
    assert d["state"] == "CRASHED" and d["treatable_here"] is True
    assert "second identical crash is a bug" in d["action"]


def test_a_fresh_artifact_is_healthy_and_never_enters_the_ward(tmp_path):
    _ward(tmp_path)
    (tmp_path / "data/toy.json").write_text(json.dumps(
        {"generated": __import__("datetime").datetime.now(
            __import__("datetime").UTC).isoformat()}), "utf-8")
    assert diagnose(tmp_path, "toy", "data/toy.json", 1.0)["state"] == "HEALTHY"


# ---- the registry defect this organ found on its first run -------------------------------------

def test_a_secondary_artifact_is_not_counted_as_a_second_patient(tmp_path):
    """data/hunt_coverage.json is written by kimi_hunter and by nothing else, yet the exploration
    registry lists it as its own organ -- so one silent organ was billed as two dead ones, and the
    artifact would report UNSCHEDULED forever because it has no runner to schedule."""
    assert _SECONDARY["hunt_coverage"] == "kimi_hunter"
    _ward(tmp_path, manifest="")
    d = diagnose(tmp_path, "hunt_coverage", "data/hunt_coverage.json", 1.0, manifest="")
    assert d["state"] == "SECONDARY"
    assert d["producer"] == "kimi_hunter"
    assert d["coma"] is False                    # not a patient, so not a coma
    assert d["treatable_here"] is False
    assert "double-counts one patient as two" in d["action"]


# ---- treatment: the artifact is the evidence, never the exit status ----------------------------

def test_a_real_cure_discharges(tmp_path):
    _ward(tmp_path)
    r = _runner(tmp_path, "run_toy.py",
                "import json,pathlib,datetime\n"
                "p=pathlib.Path('data/toy.json'); p.parent.mkdir(parents=True,exist_ok=True)\n"
                "p.write_text(json.dumps({'generated':"
                "datetime.datetime.now(datetime.UTC).isoformat()}))\n")
    rep = build_report(tmp_path, do_treat=True,
                       family={"toy": ("data/toy.json", 1.0, "x")}, runners={"toy": r})
    assert rep["status"] == "TREATED"
    assert rep["treatments"][0]["outcome"] == "DISCHARGED"


def test_exit_zero_with_no_artifact_is_not_a_cure(tmp_path):
    """Exit status is the organ's opinion of itself; the artifact is the evidence. Trusting the
    return code would let a silently-broken organ be marked healthy forever."""
    _ward(tmp_path, manifest="0 * * * * run_liar.py\n")
    r = _runner(tmp_path, "run_liar.py", "pass\n")
    rep = build_report(tmp_path, do_treat=True,
                       family={"liar": ("data/liar.json", 1.0, "x")}, runners={"liar": r})
    t = rep["treatments"][0]
    assert t["rc"] == 0 and t["outcome"] == "STILL-ADMITTED"
    assert "opinion of itself" in t["why"]


def test_every_treatment_is_recorded_with_its_diagnosis(tmp_path):
    """'We tried' must be a dated fact, so a treatment that never works shows up as a pattern."""
    _ward(tmp_path, manifest="0 * * * * run_liar.py\n")
    r = _runner(tmp_path, "run_liar.py", "pass\n")
    build_report(tmp_path, do_treat=True,
                 family={"liar": ("data/liar.json", 1.0, "x")}, runners={"liar": r})
    rows = [json.loads(x) for x in
            (tmp_path / "data/organ_er_log.jsonl").read_text("utf-8").splitlines() if x.strip()]
    assert rows and rows[0]["diagnosis"]["organ"] == "liar"
    assert rows[0]["treatment"]["outcome"] == "STILL-ADMITTED"
    assert rows[0]["at"]


def test_an_untreated_coma_is_a_defect_not_backlog(tmp_path):
    """'It is on the list' is exactly the state the same-day standard forbids."""
    _ward(tmp_path, manifest="0 * * * * run_toy.py\n")
    rep = build_report(tmp_path, do_treat=False,
                       family={"toy": ("data/toy.json", 1.0, "x")}, runners={})
    assert rep["status"] in ("COMA-UNTREATED", "SICK-UNTREATED")
    assert rep["coma_hours"] == COMA_HOURS


def test_no_runner_is_named_never_silently_skipped(tmp_path):
    """An untreatable patient nobody names is the failure this organ exists to end."""
    _ward(tmp_path, manifest="0 * * * * run_toy.py\n", log="HTTP 529 overloaded")
    rep = build_report(tmp_path, do_treat=True,
                       family={"toy": ("data/toy.json", 1.0, "x")}, runners={})
    assert rep["treatments"][0]["outcome"] == "NO-RUNNER"
