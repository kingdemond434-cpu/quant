"""L1.28b(d): the conversion queue's drain mechanism, and the inversion it nearly inherited.

The load-bearing test in this file is ``test_arrivals_collapsed_says_find_harder_never_drain``.
Before 2026-08-05 ``check_conversion.py`` derived ``"repair_mode": status != "OK"``, so the flag
was TRUE for ARRIVALS-COLLAPSED -- a status meaning the desk is finding too LITTLE -- while the
flag's documented effect is to redirect the next brain window away from finding. The flag was
inert (its only consumer picked an advice string), so the inversion cost nothing. Wiring the
actuator is exactly what would have made it cost something.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from libs.ops.repair_mode import (
    _BANNED_VERBS,
    DIRECTION_FOR_STATUS,
    duty,
)

_ROOT = Path(__file__).resolve().parents[2]


def _write(root: Path, **over) -> Path:
    """A conversion artifact shaped like the live one, overridable per test."""
    d = {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
        "status": "REPAIR-MODE", "repair_mode": True, "direction": "DRAIN",
        "backlog": 204, "past_due": 67,
        "past_due_ids": [f"R{i:04d}" for i in range(1, 21)],   # artifact truncates to 20
        "arrivals_7d": 381, "dispositions_7d": 210,
        "oldest_backlog_age_days": 10.45, "arrivals_baseline_7d": 9.75,
    }
    d.update(over)
    (root / "data").mkdir(parents=True, exist_ok=True)
    p = root / "data" / "conversion_status.json"
    p.write_text(json.dumps(d), "utf-8")
    return p


# --- the inversion --------------------------------------------------------------------------

def test_arrivals_collapsed_says_find_harder_never_drain(tmp_path):
    """THE regression. ARRIVALS-COLLAPSED is the OPPOSITE defect and earns the opposite duty.

    Fails against the pre-fix mapping, where every non-OK status meant "drain".
    """
    _write(tmp_path, status="ARRIVALS-COLLAPSED", arrivals_7d=2)
    r = duty(root=tmp_path)
    assert r.direction == "FIND-HARDER"
    assert r.owed is True                     # it still owes work -- just not THIS work
    assert "HUNT HARDER" in r.text
    # The one sentence that must never appear in this state.
    assert "REPAIR WINDOW" not in r.text
    assert "DRAIN THESE FIRST" not in r.text
    # And it must say why, so a reader cannot re-derive the inversion from the output.
    assert "L1.25a" in r.text


def test_arrivals_collapsed_is_not_repair_mode_in_the_published_artifact():
    """The source of the flag, not just the actuator: the two must agree by construction."""
    assert DIRECTION_FOR_STATUS["ARRIVALS-COLLAPSED"] == "FIND-HARDER"
    assert DIRECTION_FOR_STATUS["REPAIR-MODE"] == "DRAIN"
    assert DIRECTION_FOR_STATUS["OK"] == "STEADY"


@pytest.mark.parametrize("status", ["FLATLINE", "REPAIR-MODE", "DEBT-GROWING"])
def test_backlog_states_drain(tmp_path, status):
    _write(tmp_path, status=status)
    r = duty(root=tmp_path)
    assert r.direction == "DRAIN"
    assert r.owed is True
    assert "REPAIR WINDOW" in r.text


def test_ok_is_steady_and_emits_nothing(tmp_path):
    _write(tmp_path, status="OK", backlog=3, past_due=0, past_due_ids=[])
    r = duty(root=tmp_path)
    assert r.direction == "STEADY"
    assert r.owed is False
    assert r.text == ""


# --- unmeasured owes work (L1.28a) ----------------------------------------------------------

def test_missing_artifact_owes_work_and_is_not_silence(tmp_path):
    r = duty(root=tmp_path)                    # nothing written at all
    assert r.direction == "UNMEASURED"
    assert r.measured is False
    assert r.owed is True
    assert r.text, "an unreadable conversion state must emit a duty, never an empty string"
    assert "OWING WORK" in r.text


def test_unknown_status_is_unmeasured_not_steady(tmp_path):
    """A future enum member must not fall down an `else` branch into silence (R0237's class)."""
    _write(tmp_path, status="SOME-NEW-STATUS")
    r = duty(root=tmp_path)
    assert r.direction == "UNMEASURED"
    assert r.owed is True


def test_stale_artifact_is_unmeasured(tmp_path):
    p = _write(tmp_path, generated="2026-01-01T00:00:00+00:00")
    old = time.time() - 60 * 60 * 24 * 30
    os.utime(p, (old, old))
    r = duty(root=tmp_path)
    assert r.direction == "UNMEASURED"
    assert r.owed is True


# --- it can only ADD work (L1.28b(f), L1.25a, L1.32) -----------------------------------------

@pytest.mark.parametrize("status", ["FLATLINE", "REPAIR-MODE", "DEBT-GROWING",
                                    "ARRIVALS-COLLAPSED", "OK", "MYSTERY"])
def test_no_emitted_text_can_throttle_anything(tmp_path, status):
    """Structural, not aspirational: the module has no vocabulary for stopping.

    Same guarantee as libs/execution/excitation.py having no vocabulary for size. A later edit
    that teaches this actuator to say "pause the miners" fails here rather than reaching an organ.
    """
    _write(tmp_path, status=status)
    text = duty(root=tmp_path).text.lower()
    for verb in _BANNED_VERBS:
        assert verb not in text, f"{status}: emitted text contains throttling verb {verb!r}"


def test_drain_text_carries_the_protection_clause_verbatim(tmp_path):
    """An organ reading the duty must not be able to mistake it for a throttle."""
    _write(tmp_path)
    text = duty(root=tmp_path).text
    assert "ADDS A DUTY AND REMOVES NONE" in text
    for organ in ("collectors", "recorders", "miners", "diggers", "forward clocks", "fences"):
        assert organ in text
    assert "FULL CADENCE" in text


# --- denominators (L1.57) ---------------------------------------------------------------------

def test_past_due_count_comes_from_the_count_not_the_truncated_name_list(tmp_path):
    """The artifact truncates ``past_due_ids`` to 20; the true count is 67.

    Reporting ``len(past_due_ids)`` would publish 20 -- a count of what the writer wrote down
    rather than of what the run found, which is the exact L1.57 defect, emitted by the actuator
    built to enforce it. Caught on the first live smoke test of this module.
    """
    _write(tmp_path, past_due=67, past_due_ids=[f"R{i:04d}" for i in range(1, 21)])
    r = duty(root=tmp_path)
    assert r.n_past_due == 67
    assert len(r.past_due) == 20
    assert "67 past grace" in r.text
    assert "20 past grace" not in r.text
    # "+N more" must be derived from the true total, never from the capped list.
    assert "(+55 more)" in r.text


def test_count_falls_back_to_the_names_when_the_count_is_absent(tmp_path):
    d = json.loads(_write(tmp_path).read_text())
    d.pop("past_due")
    (tmp_path / "data" / "conversion_status.json").write_text(json.dumps(d), "utf-8")
    r = duty(root=tmp_path)
    assert r.n_past_due == 20      # honest: it is all the evidence there is


# --- the law must REACH an organ (L1.36) ------------------------------------------------------

def test_brain_env_injects_the_duty_at_every_organ_spawn():
    """A fenced law that no organ ever receives cannot change behaviour (L1.36 REACHING).

    This is the whole defect: the flag existed, was published, was fenced, and reached nobody.
    """
    src = (_ROOT / "ops" / "brain_env.sh").read_text("utf-8")
    assert "libs.ops.repair_mode" in src, "the actuator must be invoked at organ spawn"
    assert "_DOCTRINE=" in src
    # It must extend the doctrine every organ already receives, not live in one script.
    assert "_REPAIR_DUTY" in src


def test_check_conversion_derives_direction_from_the_shared_map():
    """One mapping, one place. A second derivation of it is the bug this file exists for."""
    src = (_ROOT / "scripts" / "check_conversion.py").read_text("utf-8")
    assert "DIRECTION_FOR_STATUS" in src
    # The exact CODE form, not the substring -- the file explains the old derivation in prose and
    # must stay free to do so. What may not come back is the assignment.
    assert '"repair_mode": status != "OK"' not in src, "the inverted derivation must not come back"


def test_actuator_cli_prints_the_block_and_never_blocks_a_spawn():
    """L1.37: the spawn gate PAGES, it does not KILL -- an organ must always be able to start."""
    r = subprocess.run([sys.executable, "-m", "libs.ops.repair_mode"],
                       cwd=_ROOT, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-2000:]
