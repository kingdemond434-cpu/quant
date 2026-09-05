"""Scheduled shell launchers must survive a commit landing mid-run (gap-fixer 2026-08-26).

bash reads a script INCREMENTALLY, by byte offset. This desk commits ~200x/day into the tree
its launchers execute from and a dig holds its slot up to three hours, so a commit that changes
a launcher's LENGTH mid-run makes bash resume inside a line.

It happened on 63680c05: a ~120-byte comment growth in ops/run_frontier_rotation.sh at 11:22
while a dig was running. data/cro_ai_logs/seat_frontier.log recorded comment text executed as a
command, output from the STALE version, and `syntax error near unexpected token 'fi'`.

The seal is three properties and this pins all three, because any two alone still leave the
script re-running from the top: a `{` on its own line, an `exit` as the last statement INSIDE
the group, and a `}` as the file's final line.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

from scripts import max_audit

ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_every_scheduled_launcher_is_sealed():
    defects: list = []
    max_audit.check_launcher_seal(defects)
    assert not defects, defects[0][1] if defects else ""


def test_every_launcher_still_parses():
    """A seal that breaks the script it protects is a worse outage than the one it prevents."""
    for f in sorted((ROOT / "ops").glob("run_*.sh")):
        r = subprocess.run(["bash", "-n", str(f)], capture_output=True, text=True)
        assert r.returncode == 0, f"{f.name}: {r.stderr.strip()[:200]}"


def test_the_fence_fails_on_an_unsealed_launcher(tmp_path, monkeypatch):
    """POSITIVE CONTROL. A fence never shown to fire has had only its passes observed."""
    ops = tmp_path / "ops"
    ops.mkdir()
    (ops / "run_naked.sh").write_text("#!/usr/bin/env bash\nset -e\necho hi\n", "utf-8")
    monkeypatch.setattr(max_audit, "ROOT", tmp_path)
    monkeypatch.setattr(max_audit, "_launcher_is_scheduled", lambda _n: True)
    defects: list = []
    max_audit.check_launcher_seal(defects)
    assert defects and "run_naked.sh" in defects[0][1]


def test_a_brace_without_an_inner_exit_is_not_sealed(tmp_path, monkeypatch):
    """MEASURED, not assumed: `{ ... }` alone protected the body and bash STILL read past the
    closing brace and re-ran the whole script. Only the exit inside the group ends the process
    before another byte is read, so a braced-but-exitless script must not pass."""
    ops = tmp_path / "ops"
    ops.mkdir()
    (ops / "run_braced.sh").write_text(
        "#!/usr/bin/env bash\nset -e\n{\necho hi\n}\n", "utf-8")
    monkeypatch.setattr(max_audit, "ROOT", tmp_path)
    monkeypatch.setattr(max_audit, "_launcher_is_scheduled", lambda _n: True)
    defects: list = []
    max_audit.check_launcher_seal(defects)
    assert defects and "run_braced.sh" in defects[0][1]


def test_an_unscheduled_script_is_not_flagged(tmp_path, monkeypatch):
    """A script nothing invokes cannot be corrupted mid-run, and flagging it is the kind of
    noise that gets a fence switched off."""
    ops = tmp_path / "ops"
    ops.mkdir()
    (ops / "run_naked.sh").write_text("#!/usr/bin/env bash\necho hi\n", "utf-8")
    monkeypatch.setattr(max_audit, "ROOT", tmp_path)
    monkeypatch.setattr(max_audit, "_launcher_is_scheduled", lambda _n: False)
    defects: list = []
    max_audit.check_launcher_seal(defects)
    assert not defects


def test_a_sealed_script_survives_a_real_mid_run_rewrite(tmp_path):
    """END-TO-END, on a real bash process: run a sealed script, rewrite it mid-flight with a
    length change, and require exactly one clean pass. This is the failure verbatim."""
    s = tmp_path / "victim.sh"
    marker = tmp_path / "ran.txt"
    s.write_text(
        "#!/usr/bin/env bash\nset -uo pipefail\n{\n"
        f"echo start >> {marker}\n"
        "sleep 2\n"
        "if true; then\n"
        f"    echo branch >> {marker}\n"
        "fi\n"
        f"echo end >> {marker}\n"
        "exit 0\n}\n", "utf-8")
    proc = subprocess.Popen([sys.executable, "-c",
                             f"import subprocess;subprocess.run(['bash',{str(s)!r}])"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    import time
    time.sleep(0.6)
    s.write_text(s.read_text("utf-8").replace(
        "set -uo pipefail",
        "set -uo pipefail\n# an hourly sync commit adds a comment\n# and another, shifting "
        "every downstream byte offset"), "utf-8")
    proc.wait(timeout=30)
    lines = marker.read_text("utf-8").split()
    assert lines == ["start", "branch", "end"], lines
