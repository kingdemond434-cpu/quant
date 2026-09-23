"""Regression guard for check_scheduled_scripts' PATH RESOLUTION.

Found 2026-09-03: the token regex was unanchored on the left, so any organ living under a
sub-desk (`desks/mt5/scripts/foo.py`) was stat'd as the bare tail `scripts/foo.py`. That is
wrong in both directions -- a false positive on an organ that exists (which trains the desk to
ignore this fence, L1.43) and, the dangerous half, a MISSING sub-desk organ reported healthy
whenever a same-named file happens to exist under the top-level `scripts/`. This check exists
precisely to catch a scheduled organ that dies on ENOENT, so a silent pass is its total failure.
"""

from __future__ import annotations

from pathlib import Path

import scripts.max_audit as m


def _write_unit(root: Path, name: str, execstart: str) -> None:
    (root / "ops").mkdir(parents=True, exist_ok=True)
    (root / "ops" / name).write_text(
        f"[Service]\nExecStart={execstart}\n", encoding="utf-8")


class TestScheduledScriptPathResolution:
    def _run(self, tmp_path: Path, monkeypatch) -> list[tuple[str, str]]:
        monkeypatch.setattr(m, "ROOT", tmp_path)
        monkeypatch.chdir(tmp_path)
        # No crontab in the sandbox: unit files are the whole population, which is the
        # documented fallback the check already supports.
        monkeypatch.setenv("PATH", str(tmp_path))
        defects: list[tuple[str, str]] = []
        m.check_scheduled_scripts(defects)
        return defects

    def test_subdesk_organ_that_exists_is_not_flagged(self, tmp_path, monkeypatch) -> None:
        target = tmp_path / "desks/mt5/scripts/fxblue_track_record_miner.py"
        target.parent.mkdir(parents=True)
        target.write_text("# organ\n", encoding="utf-8")
        _write_unit(
            tmp_path, "quant-fxblue.service",
            "/opt/.venv/bin/python desks/mt5/scripts/fxblue_track_record_miner.py --once")
        assert self._run(tmp_path, monkeypatch) == []

    def test_missing_subdesk_organ_is_flagged_even_when_a_namesake_exists(
            self, tmp_path, monkeypatch) -> None:
        # The silent-pass case: the scheduled organ is ABSENT, but a file of the same basename
        # sits under the top-level scripts/. The truncating regex resolved to the namesake and
        # reported green while the unit died on ENOENT every fire.
        (tmp_path / "scripts").mkdir(parents=True)
        (tmp_path / "scripts/miner.py").write_text("# a different file\n", encoding="utf-8")
        _write_unit(tmp_path, "quant-x.service",
                    "/opt/.venv/bin/python desks/mt5/scripts/miner.py")
        defects = self._run(tmp_path, monkeypatch)
        assert [d[0] for d in defects] == ["scheduled-script-missing"]
        assert "desks/mt5/scripts/miner.py" in defects[0][1]

    def test_absolute_path_inside_the_checkout_resolves(self, tmp_path, monkeypatch) -> None:
        (tmp_path / "ops").mkdir(parents=True, exist_ok=True)
        (tmp_path / "ops/run_thing.sh").write_text("#!/bin/bash\n", encoding="utf-8")
        _write_unit(tmp_path, "quant-abs.service", f"/bin/bash {tmp_path}/ops/run_thing.sh")
        assert self._run(tmp_path, monkeypatch) == []

    def test_absolute_path_inside_the_checkout_that_is_missing_is_flagged(
            self, tmp_path, monkeypatch) -> None:
        _write_unit(tmp_path, "quant-abs2.service", f"/bin/bash {tmp_path}/ops/gone.sh")
        defects = self._run(tmp_path, monkeypatch)
        assert [d[0] for d in defects] == ["scheduled-script-missing"]

    def test_plain_toplevel_reference_still_works(self, tmp_path, monkeypatch) -> None:
        _write_unit(tmp_path, "quant-plain.service", "/opt/py scripts/absent.py")
        defects = self._run(tmp_path, monkeypatch)
        assert [d[0] for d in defects] == ["scheduled-script-missing"]
        assert "scripts/absent.py" in defects[0][1]
