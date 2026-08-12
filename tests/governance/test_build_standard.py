"""L1.41 build standard -- nothing enters below the bar; timid work is never caught later."""
from __future__ import annotations

import ast
from pathlib import Path

from scripts.check_build_standard import (
    _GOVERNED,
    _SCHEDULE_EXEMPT,
    _has_own_schedule_line,
    _has_silent_swallow,
    _scheduled_parent,
    audit_organ,
    build_report,
)


def test_every_governed_organ_meets_the_standard():
    rep = build_report()
    assert rep["status"] == "OK", rep["detail"]
    assert rep["n_governed"] >= 12


def test_the_fence_governs_itself():
    # A build-standard fence exempt from its own standard is the decoration it exists to detect.
    assert "check_build_standard.py" in _GOVERNED


def test_missing_refusal_path_is_caught(tmp_path):
    (tmp_path / "scripts").mkdir(parents=True)
    (tmp_path / "scripts/x.py").write_text("def main():\n    return 0\n", "utf-8")
    r = audit_organ(tmp_path, "x.py", manifest="", matrix_src="", test_blob="")
    assert any("NO-REFUSAL-PATH" in v for v in r["violations"])
    assert any("UNTESTED" in v for v in r["violations"])
    assert any("UNSCHEDULED" in v for v in r["violations"])
    assert any("UNMAPPED" in v for v in r["violations"])


def test_silent_swallow_detected_and_logged_alternative_is_not():
    swallow = ast.parse("try:\n    x=1\nexcept OSError:\n    pass\n")
    assert _has_silent_swallow(swallow) is True
    handled = ast.parse("try:\n    x=1\nexcept OSError as e:\n    notes.append(e)\n")
    assert _has_silent_swallow(handled) is False


def test_schedule_exemptions_carry_a_reason():
    # "No cron line" must be a DECISION, never a default.
    for organ, reason in _SCHEDULE_EXEMPT.items():
        assert organ in _GOVERNED
        assert len(reason) > 40, f"{organ}: exemption reason too thin to be a decision"


def test_missing_organ_fails_rather_than_passing_silently(tmp_path):
    (tmp_path / "scripts").mkdir(parents=True)
    r = audit_organ(tmp_path, "nope.py", manifest="", matrix_src="", test_blob="")
    assert r["ok"] is False and "MISSING" in r["violations"][0]


def test_runs_inside_the_law_gate():
    src = Path("scripts/run_law_gate.py").read_text("utf-8")
    assert "check_build_standard.py" in src        # so every commit/push/CI run enforces it


# ------------------------------------------------------------------ the comment-mention bug
def test_a_comment_mentioning_an_organ_is_not_a_schedule(tmp_path: Path) -> None:
    """THE BUG, REPRODUCED EXACTLY. Found 2026-08-12 chasing why run_discovery.py read as
    scheduled when it has no cron/systemd line at all. Both this check and _scheduled_parent used
    a bare `name in manifest` substring test over the WHOLE file, comments included -- and this
    desk writes '# EVIDENCE: scripts/X.py -> ...' on nearly every cron block as a matter of
    convention, so any organ merely DOCUMENTED elsewhere satisfied the check and skipped
    scheduling verification entirely, whether or not a real line existed."""
    manifest = "# EVIDENCE: scripts/run_discovery.py -> web/discovery.json, see the docstring\n"
    assert not _has_own_schedule_line("run_discovery.py", manifest)


def test_a_real_cron_line_does_satisfy_it(tmp_path: Path) -> None:
    assert _has_own_schedule_line("widget.py", "5 6 * * * python scripts/widget.py\n")


def test_a_real_systemd_line_does_satisfy_it() -> None:
    manifest = 'SYSTEMD unit="quant-widget.service" on="always" exec="scripts/widget.py"\n'
    assert _has_own_schedule_line("widget.py", manifest)


def test_a_comment_referencing_a_scheduled_sibling_does_not_borrow_its_schedule(
        tmp_path: Path) -> None:
    """THE SAME BUG, ONE LEVEL UP. `_scheduled_parent`'s own candidate-parent check used the
    identical naive substring test, so a script merely mentioned in a comment near a real cron
    line for something else could be mistaken for the scheduled parent lending run_discovery.py
    a transitive schedule it did not have."""
    (tmp_path / "scripts").mkdir(parents=True)
    (tmp_path / "scripts/decoy.py").write_text(
        "# see also scripts/child.py for the discovery half\nprint('hi')\n", "utf-8")
    manifest = ("# EVIDENCE: scripts/decoy.py documents scripts/child.py above\n"
               "5 6 * * * python scripts/unrelated.py\n")
    assert _scheduled_parent(tmp_path, "child.py", manifest) == ""


def test_an_organ_only_ever_mentioned_in_a_comment_is_flagged_unscheduled(tmp_path: Path) -> None:
    (tmp_path / "scripts").mkdir(parents=True)
    (tmp_path / "scripts/x.py").write_text(
        "def main():\n    return 'REFUSED'\n", "utf-8")
    manifest = "# EVIDENCE: scripts/x.py -> data/x.json, first run 2026-08-01\n"
    r = audit_organ(tmp_path, "x.py", manifest=manifest, matrix_src="x.py", test_blob="test_x")
    assert any("UNSCHEDULED" in v for v in r["violations"])
