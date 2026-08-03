"""AN ORGAN THAT CANNOT FIRE MUST NOT BE DISCOVERED BY SPENDING CREDITS ON IT.

Eleven of the desk's live defects reduce to "this organ has not run", with LLM credits named as
the blocker. That framing is only honest if the organs are otherwise sound -- otherwise the
credits buy a log file explaining that a prompt moved or the doctrine read empty.

Both failures were real and both were silent:

  THE CONVERSION DUTY WAS DEAD IN ALL SIX DIG SCRIPTS. Each computed `_MINE_PRIORITY` from
  `scripts/mine_gate.py` beneath fourteen lines of comment stating that the result is prepended to
  the organ's brief, then invoked `claude -p "$(cat <brief>)"` and never referenced the variable.
  Firing those organs with credits would have grown the very conversion backlog that
  `mine-conversion-unbacked` and `mine-law-unjudgeable` report -- at max effort, seven regions a
  day.

  THE DOCTRINE WAS ONE `mv` FROM CEASING TO EXIST. `_DOCTRINE` read a hardcoded path with
  `2>/dev/null`, so any relocation left it empty and every organ ran undirected with nothing in
  any log to say so.

These tests pin both, plus the property that makes the check worth having: verifying readiness
must not itself call `claude`.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.check_organ_readiness as C  # noqa: E402

DIG_RUNNERS = sorted({r for r, _ in C.ORGANS.values()})


def _bash(script: str, *args: str, dry: bool = True, root: Path | None = None):
    env = dict(os.environ, _BRAIN_ROOT=str(root or ROOT))
    if dry:
        env["BRAIN_DRY_RUN"] = "1"
    return subprocess.run(["bash", script, *args], cwd=ROOT, env=env,
                          capture_output=True, text=True, timeout=180, check=False)


# ------------------------------------------------------------------ the wiring

@pytest.mark.parametrize("runner", DIG_RUNNERS)
def test_every_dig_runner_parses(runner: str) -> None:
    assert subprocess.run(["bash", "-n", str(ROOT / runner)],
                          capture_output=True, check=False).returncode == 0


@pytest.mark.parametrize("runner", DIG_RUNNERS)
def test_every_dig_runner_wires_the_conversion_duty(runner: str) -> None:
    """THE REGRESSION GUARD FOR THE ORIGINAL BUG. `dig_prompt` prepends the §33 duty; a bare
    `cat <brief>` is the exact shape that left it dead in all six organs."""
    src = (ROOT / runner).read_text("utf-8")
    assert "dig_prompt" in src, f"{runner} does not call dig_prompt"


@pytest.mark.parametrize("runner", DIG_RUNNERS)
def test_no_runner_passes_a_bare_cat_as_its_prompt(runner: str) -> None:
    src = (ROOT / runner).read_text("utf-8")
    for line in src.splitlines():
        if line.lstrip().startswith("claude "):
            assert "$(cat ops/" not in line, f"{runner} passes a bare cat: {line[:90]}"


def test_a_computed_but_unused_variable_does_not_come_back() -> None:
    """The bug was not a typo -- it was a value computed, commented at length, and discarded. Any
    reintroduction of that pattern in the ops scripts fails here."""
    for p in sorted((ROOT / "ops").glob("run_*.sh")):
        src = p.read_text("utf-8")
        for var in ("_MINE_PRIORITY",):
            assigned = f'{var}="' in src
            used = any(f"${var}" in ln or f"${{{var}}}" in ln
                       for ln in src.splitlines() if f'{var}="' not in ln)
            assert not (assigned and not used), f"{p.name}: {var} assigned and never used"


# ---------------------------------------------------------------- the doctrine

def test_an_empty_doctrine_is_loud_not_silent(tmp_path: Path) -> None:
    """`_DOCTRINE` used a hardcoded path plus `2>/dev/null`, so a relocated checkout ran every
    organ with an empty system prompt and no trace anywhere. Emptiness must reach stderr."""
    r = subprocess.run(["bash", "-c", f"source {ROOT}/ops/brain_env.sh; true"],
                       cwd=ROOT, env=dict(os.environ, _BRAIN_ROOT=str(tmp_path)),
                       capture_output=True, text=True, timeout=60, check=False)
    assert "DOCTRINE EMPTY" in r.stderr


def test_the_doctrine_loads_from_this_checkout() -> None:
    """And the positive case: pointed at a real root, it is found and non-trivial."""
    r = subprocess.run(
        ["bash", "-c", f'source {ROOT}/ops/brain_env.sh; printf "%s" "${{#_DOCTRINE}}"'],
        cwd=ROOT, env=dict(os.environ, _BRAIN_ROOT=str(ROOT)),
        capture_output=True, text=True, timeout=60, check=False)
    assert int(r.stdout.strip() or 0) > 10_000


# ------------------------------------------------------------------- dry run

def test_dry_run_never_invokes_claude() -> None:
    """A PRE-FLIGHT THAT COSTS CREDITS IS NOT A PRE-FLIGHT. The dry-run guard is placed before
    `brain_auth_check` precisely because that check burns a `claude -p PING` per model in the
    fallback chain. `claude` is not installed here, so any attempt would surface as an error.
    """
    r = _bash("ops/run_prospector_dig.sh")
    assert "READY" in r.stdout
    assert "PING-OK" not in r.stdout + r.stderr
    assert "command not found" not in (r.stdout + r.stderr).lower()


@pytest.mark.parametrize("organ", sorted(C.ORGANS))
def test_every_organ_dry_runs_ready(organ: str) -> None:
    runner, _ = C.ORGANS[organ]
    args = [organ.split("-", 1)[1]] if organ.startswith("frontier-") else []
    r = _bash(runner, *args)
    assert "READY" in r.stdout, f"{organ}: {(r.stdout + r.stderr)[:200]}"
    assert "conversion duty PRESENT" in r.stdout


def test_the_assembled_prompt_leads_with_the_conversion_duty() -> None:
    """Order is the mechanism, not decoration: the gate instructs the run to spend its FIRST
    effort converting. A duty appended after a 10KB brief is a duty the organ reaches last."""
    r = subprocess.run(
        ["bash", "-c",
         f'source {ROOT}/ops/brain_env.sh 2>/dev/null; dig_prompt ops/prospector_dig_prompt.txt'],
        cwd=ROOT, env=dict(os.environ, _BRAIN_ROOT=str(ROOT)),
        capture_output=True, text=True, timeout=300, check=False)
    assert r.stdout.startswith("[§33]")
    assert len(r.stdout) > (ROOT / "ops/prospector_dig_prompt.txt").stat().st_size


# ------------------------------------------------------------------- the gate

def test_the_checker_passes_on_this_checkout() -> None:
    """Exit code is the contract: this is a gate run before spending, so 'fine' and 'broken' must
    be distinguishable without reading the output."""
    r = subprocess.run([sys.executable, str(ROOT / "scripts/check_organ_readiness.py")],
                       cwd=ROOT, capture_output=True, text=True, timeout=600, check=False)
    assert r.returncode == 0, r.stdout
    assert f"{len(C.ORGANS)}/{len(C.ORGANS)} READY" in r.stdout


def test_a_missing_brief_is_caught() -> None:
    res = C.check("fake", "ops/run_prospector_dig.sh", "ops/does_not_exist_prompt.txt")
    assert any("missing" in f for f in res["failures"])


def test_a_stub_brief_is_caught(tmp_path: Path) -> None:
    """A truncated prompt still runs and still bills, so size is checked rather than existence."""
    stub = ROOT / "ops/.stub_probe_prompt.txt"
    stub.write_text("dig stuff", "utf-8")
    try:
        res = C.check("fake", "ops/run_prospector_dig.sh", "ops/.stub_probe_prompt.txt")
        assert any("stub" in f for f in res["failures"])
    finally:
        stub.unlink(missing_ok=True)
