"""Gap #58 regression guards -- the repo must always be able to reconstitute the desk.

The load-bearing test here is test_every_referenced_script_exists: it fails the day someone
deletes a script that ops/crontab.manifest still schedules (the DEAD CRON class -- a restored
box would fail that entry silently every tick, forever). The rest lock the checker's own
contract: parse, committed-timer rot detection, JSON report, graceful no-crontab path, and a
nonzero exit on a manifest that references a missing script."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import scripts.check_scheduler_manifest as c

ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------------------------
# real-repo guards (these are the point of the whole exercise)
# ---------------------------------------------------------------------------------------------


class TestRealManifest:
    def test_manifest_parses(self) -> None:
        man = c.parse_manifest(ROOT / "ops/crontab.manifest")
        assert man.parse_problems == []
        # the reconstruction names 17 cron lines + 13 systemd units (manifest header);
        # floors not equalities so adding entries never breaks this test.
        assert len(man.cron) >= 15
        assert len(man.systemd) >= 13
        for entry in man.cron:
            assert len(entry.schedule.split()) == 5, entry

    def test_all_five_committed_dig_units_present(self) -> None:
        man = c.parse_manifest(ROOT / "ops/crontab.manifest")
        units = {u.unit for u in man.systemd}
        for stem in ("blindrediscovery", "dataaxis", "frontier", "litminer", "prospector"):
            assert f"quant-{stem}.timer" in units

    def test_every_referenced_script_exists(self) -> None:
        """THE regression test: manifest-scheduled scripts may never be deleted without
        updating the manifest -- a dead cron entry is a silent nightly failure on the box
        and a broken DR floor in the repo."""
        man = c.parse_manifest(ROOT / "ops/crontab.manifest")
        missing = c.check_scripts_exist(ROOT, man)
        assert missing == [], f"manifest schedules scripts absent from the repo: {missing}"

    def test_committed_timers_resolve_and_are_manifested(self) -> None:
        man = c.parse_manifest(ROOT / "ops/crontab.manifest")
        assert c.check_committed_timers(ROOT, man) == []

    def test_row58_named_jobs_are_covered(self) -> None:
        """The register row that opened this gap names the uncommitted jobs; each must now be
        reconstitutable from the manifest (docs/GAP_REGISTER.md:272)."""
        man = c.parse_manifest(ROOT / "ops/crontab.manifest")
        refs = set(c.referenced_paths(man))
        for script in (
            "scripts/watchdog.py",                      # executor/deadman respawn + run_alerts tick
            "scripts/ensure_recorder.py",               # recorder self-heal
            "scripts/run_recorder_spot.py",             # spot recorder pgrep guard
            "scripts/run_recorder_bybit.py",            # bybit recorder pgrep guard
            "scripts/run_venue_divergence_shadow.py",   # the */5 divergence sampler
            "scripts/daily_research_cycle.py",          # shadows/cost_model/nav_attest/git_snapshot
            "scripts/run_cashcarry_executor.py",        # systemd plane, quant-cashcarry
            "scripts/run_deadman_switch.py",            # systemd plane, quant-deadman
        ):
            assert script in refs, f"{script} lost from the manifest"


# ---------------------------------------------------------------------------------------------
# checker contract on fixture trees
# ---------------------------------------------------------------------------------------------


def _fixture_repo(tmp_path: Path, manifest: str, *, with_script: bool = True) -> Path:
    (tmp_path / "ops").mkdir()
    (tmp_path / "scripts").mkdir()
    if with_script:
        (tmp_path / "scripts/real_job.py").write_text("print('hi')\n", "utf-8")
    (tmp_path / "ops/crontab.manifest").write_text(manifest, "utf-8")
    return tmp_path


_GOOD = """# fixture manifest
QUANT_ROOT=/srv/desk
*/5 * * * * cd "$QUANT_ROOT" && .venv/bin/python scripts/real_job.py >> data/x.log 2>&1
"""

_BAD = """# fixture manifest with a dead cron entry
0 2 * * * cd "$QUANT_ROOT" && .venv/bin/python scripts/ghost_job.py
"""


class TestCheckerContract:
    def test_clean_fixture_exits_zero(self, tmp_path: Path,
                                      monkeypatch: pytest.MonkeyPatch) -> None:
        root = _fixture_repo(tmp_path, _GOOD)
        monkeypatch.setattr(c, "read_live_crontab", lambda: None)
        assert c.main(["--root", str(root)]) == 0

    def test_missing_script_exits_nonzero(self, tmp_path: Path,
                                          monkeypatch: pytest.MonkeyPatch) -> None:
        """(a) is the deploy gate: deploy/reconstitute_cron.sh refuses on this exit."""
        root = _fixture_repo(tmp_path, _BAD, with_script=False)
        monkeypatch.setattr(c, "read_live_crontab", lambda: None)
        assert c.main(["--root", str(root)]) == 2
        # --report-only tolerates drift, NEVER a missing script
        assert c.main(["--root", str(root), "--report-only"]) == 2

    def test_json_report_written_and_machine_readable(self, tmp_path: Path,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
        root = _fixture_repo(tmp_path, _GOOD)
        monkeypatch.setattr(c, "read_live_crontab", lambda: None)
        assert c.main(["--root", str(root), "--json"]) == 0
        report = json.loads((root / "data/scheduler_manifest_report.json").read_text("utf-8"))
        assert report["checks"]["scripts_exist"]["ok"] is True
        assert report["checks"]["live_crontab"]["readable"] is False
        assert report["checks"]["live_crontab"]["note"] == "no live crontab readable"
        assert report["referenced_scripts"] == ["scripts/real_job.py"]
        assert report["exit_code"] == 0

    def test_json_report_names_the_missing_script(self, tmp_path: Path,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
        root = _fixture_repo(tmp_path, _BAD, with_script=False)
        monkeypatch.setattr(c, "read_live_crontab", lambda: None)
        assert c.main(["--root", str(root), "--json"]) == 2
        report = json.loads((root / "data/scheduler_manifest_report.json").read_text("utf-8"))
        assert report["checks"]["scripts_exist"]["missing"] == ["scripts/ghost_job.py"]
        assert report["exit_code"] == 2

    def test_committed_timer_rot_is_flagged(self, tmp_path: Path,
                                            monkeypatch: pytest.MonkeyPatch) -> None:
        """(b): a committed timer whose script the manifest does not name = rotted manifest."""
        root = _fixture_repo(tmp_path, _GOOD)
        (root / "ops/other_dig.sh").write_text("#!/bin/sh\n", "utf-8")
        (root / "ops/quant-x.timer").write_text(
            "[Timer]\nOnCalendar=*-*-* 12:00:00\n", "utf-8")
        (root / "ops/quant-x.service").write_text(
            "[Service]\nExecStart=/bin/bash /home/quant/quant-platform/ops/other_dig.sh\n",
            "utf-8")
        monkeypatch.setattr(c, "read_live_crontab", lambda: None)
        assert c.main(["--root", str(root)]) == 2
        man = c.parse_manifest(root / "ops/crontab.manifest")
        problems = c.check_committed_timers(root, man)
        assert problems and "absent from the manifest" in problems[0]

    def test_oncalendar_must_exactly_match_manifest(
            self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A timezone/cadence mismatch is structural even when the right script is named."""
        manifest = _GOOD + (
            'SYSTEMD unit="quant-x.timer" on="*-*-* 00:00:00 Europe/London" '
            'exec="ops/other_dig.sh"\n'
        )
        root = _fixture_repo(tmp_path, manifest)
        (root / "ops/other_dig.sh").write_text("#!/bin/sh\n", "utf-8")
        (root / "ops/quant-x.timer").write_text(
            "[Timer]\nOnCalendar=*-*-* 00:00:00 Europe/Dublin\n", "utf-8"
        )
        (root / "ops/quant-x.service").write_text(
            "[Service]\nExecStart=/bin/bash /srv/desk/ops/other_dig.sh\n", "utf-8"
        )
        monkeypatch.setattr(c, "read_live_crontab", lambda: None)
        man = c.parse_manifest(root / "ops/crontab.manifest")
        problems = c.check_committed_timers(root, man)
        assert len(problems) == 1
        assert "does not exactly match" in problems[0]
        assert "Europe/Dublin" in problems[0] and "Europe/London" in problems[0]
        assert c.main(["--root", str(root), "--report-only"]) == 2

    def test_exact_oncalendar_match_is_clean(
            self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        schedule = "*-*-* 00:00:00 Europe/Dublin"
        manifest = _GOOD + (
            f'SYSTEMD unit="quant-x.timer" on="{schedule}" exec="ops/other_dig.sh"\n'
        )
        root = _fixture_repo(tmp_path, manifest)
        (root / "ops/other_dig.sh").write_text("#!/bin/sh\n", "utf-8")
        (root / "ops/quant-x.timer").write_text(
            f"[Timer]\nOnCalendar={schedule}\n", "utf-8"
        )
        (root / "ops/quant-x.service").write_text(
            "[Service]\nExecStart=/bin/bash /srv/desk/ops/other_dig.sh\n", "utf-8"
        )
        monkeypatch.setattr(c, "read_live_crontab", lambda: None)
        man = c.parse_manifest(root / "ops/crontab.manifest")
        assert c.check_committed_timers(root, man) == []
        assert c.main(["--root", str(root)]) == 0

    def test_drift_detected_both_directions(self, tmp_path: Path,
                                            monkeypatch: pytest.MonkeyPatch) -> None:
        root = _fixture_repo(tmp_path, _GOOD)
        live = ("QUANT_ROOT=/srv/desk\n"
                "# a comment\n"
                "0 9 * * * cd /srv/desk && .venv/bin/python scripts/live_only.py\n")
        monkeypatch.setattr(c, "read_live_crontab", lambda: live)
        assert c.main(["--root", str(root)]) == 1                     # drift -> nonzero
        assert c.main(["--root", str(root), "--report-only"]) == 0    # tolerated on request
        man = c.parse_manifest(root / "ops/crontab.manifest")
        missing_live, extra_live, dupes = c.diff_live(root, man, live)
        assert len(missing_live) == 1 and "real_job.py" in missing_live[0]
        assert len(extra_live) == 1 and "live_only.py" in extra_live[0]
        assert dupes == []

    def test_a_job_scheduled_twice_is_drift_not_a_match(
            self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """THE REGRESSION THIS FENCE SHIPPED WITH. diff_live compared `set`s, so an exact duplicate
        live line collapsed into the manifest's copy and BOTH differences came back empty -- the
        fence printed "matches manifest" and exited OK. Measured on the real box 2026-08-01: 154
        live job lines vs 137 manifest entries, 17 jobs running twice, verdict OK.

        The duplicate is the ONLY drift shape a set cannot represent, which is why it needs its own
        test rather than a variation of the both-directions one above.
        """
        root = _fixture_repo(tmp_path, _GOOD)
        job = ('*/5 * * * * cd /srv/desk && '
               ".venv/bin/python scripts/real_job.py >> data/x.log 2>&1\n")
        live = job + job                                   # scheduled twice, byte-identical
        monkeypatch.setattr(c, "read_live_crontab", lambda: live)
        man = c.parse_manifest(root / "ops/crontab.manifest")
        missing_live, extra_live, dupes = c.diff_live(root, man, live)
        assert missing_live == [] and extra_live == []     # a set sees nothing wrong here
        assert len(dupes) == 1 and "real_job.py" in dupes[0]
        assert "live x2" in dupes[0] and "manifest x1" in dupes[0]
        assert c.main(["--root", str(root)]) == 1          # and it must FAIL the gate

    def test_root_normalization_makes_identical_jobs_equal(self, tmp_path: Path) -> None:
        """$QUANT_ROOT in the manifest vs the literal VPS path live must compare equal --
        otherwise every drift report would be 100% false positives."""
        root = _fixture_repo(tmp_path, _GOOD)
        man = c.parse_manifest(root / "ops/crontab.manifest")
        live = ('*/5 * * * * cd /srv/desk && '
                ".venv/bin/python scripts/real_job.py >> data/x.log 2>&1\n")
        missing_live, extra_live, dupes = c.diff_live(root, man, live)
        assert missing_live == [] and extra_live == [] and dupes == []


# ---------------------------------------------------------------------------------------------
# (d) same-script-different-lock (R0326)
# ---------------------------------------------------------------------------------------------

_TWO_LOCKS = """# fixture manifest: one script, two lines, two DIFFERENT lock files
30 1 * * * cd "$QUANT_ROOT" && flock -n data/.a.lock bash scripts/real_job.py
30 3 * * * cd "$QUANT_ROOT" && flock -n /tmp/b.lock bash scripts/real_job.py
"""

_ONE_LOCK = """# fixture manifest: one script, two lines, the SAME lock file
30 1 * * * cd "$QUANT_ROOT" && flock -n data/.a.lock bash scripts/real_job.py
30 3 * * * cd "$QUANT_ROOT" && flock -n data/.a.lock bash scripts/real_job.py
"""


class TestLockCoherence:
    """R0326: ops/crontab.manifest scheduled run_crypto_factory.sh twice under two different
    lock paths. Both lines said `flock -n`, so the duplication LOOKED serialized -- but flock
    only excludes holders of the same lock file, so the two runs could overlap freely. This is
    mutual exclusion that reads as present and is not, which is worse than none at all."""

    def test_same_script_under_two_locks_is_structural(self, tmp_path: Path,
                                                       monkeypatch: pytest.MonkeyPatch) -> None:
        root = _fixture_repo(tmp_path, _TWO_LOCKS)
        monkeypatch.setattr(c, "read_live_crontab", lambda: None)
        man = c.parse_manifest(root / "ops/crontab.manifest")
        problems = c.check_lock_coherence(man)
        assert len(problems) == 1 and "different locks" in problems[0]
        # structural, so --report-only must NOT tolerate it (same class as a dead cron)
        assert c.main(["--root", str(root)]) == 2
        assert c.main(["--root", str(root), "--report-only"]) == 2

    def test_same_script_under_one_lock_is_clean(self, tmp_path: Path,
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
        """Duplication itself is not the defect -- INCOHERENT duplication is."""
        root = _fixture_repo(tmp_path, _ONE_LOCK)
        monkeypatch.setattr(c, "read_live_crontab", lambda: None)
        man = c.parse_manifest(root / "ops/crontab.manifest")
        assert c.check_lock_coherence(man) == []
        assert c.main(["--root", str(root)]) == 0

    def test_the_real_manifest_is_lock_coherent(self) -> None:
        """The live regression this row closed: keeps it closed."""
        man = c.parse_manifest(ROOT / "ops/crontab.manifest")
        assert c.check_lock_coherence(man) == []
