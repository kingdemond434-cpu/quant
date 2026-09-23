"""THE MULTIPLE-TESTING CHARGE IS A WALL, NOT A RATCHET -- and this is the gate that keeps it one.

THE PRINCIPAL'S STANDING ORDER, given repeatedly and most recently on 2026-09-11: breadth and
growth are not opposed, the trial charge is FIXED, and searching more must never make a candidate
harder to promote. The decision itself is older -- `libs/autodiscovery/orchestrator.py:127`
records it as FIXED-WALL DEFLATION (principal 2026-07-23): "The DSR bar must be a WALL, not a
ratchet that rises every time the desk tests anything -- otherwise objective #2 (maximize
discovery) mechanically sabotages objective #1." It is implemented twice, correctly:

  * ACROSS campaigns, by NOT accumulating. `research/gate_policy.trial_basis()` returns the
    spec's `fixed_campaign_trials(597)`; nothing adds yesterday's trials to today's.
  * WITHIN a batch, by not scaling with batch width. The same function's own comment records the
    bug it closed: "sr0 0.3786 at 597 charged trials, 1.3593 at 5,963, same gate, same policy,
    same cell" -- a candidate's bar used to move with whatever else happened to be scheduled that
    hour, which is a tax on breadth and nothing else.

WHY THIS TEST EXISTS ANYWAY. On 2026-09-11 an external review concluded the desk's hurdle rises
with cumulative trials (6.11 annual Sharpe at N=16,560) and that "max breadth and max promotion
are arithmetically opposed in this design". That is FALSE for the path that admits capital --
`libs/validation/campaign_design.dsr_hurdle_annual`, the function it computed from, is called by
no organ on the trading path -- but it was a reasonable reading, because a SECOND copy of the
gauntlet existed at `desks/mt5/external_gauntlet.py` carrying

    TRIALS_MULTIPLIER = 7.0
    n_trials = max(2, math.ceil(matrix.shape[1] * TRIALS_MULTIPLIER))    # batch width!

which bypassed the policy entirely. It was untracked and unscheduled, so it taxed nothing -- but
a correct law with a bypass lying next to it is one copy-paste from being untrue, and it had
already misled one careful reader into believing the desk's core design was self-defeating.

So the property is pinned mechanically: the scheduled gauntlet derives its charge from
`charged_trial_count`, and no module under the desk recomputes a trial count from how many cells
a sweep happened to carry.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parent.parent
_ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

#: The gauntlet the box actually runs: task MT5-Gauntlet -> `scripts\external_gauntlet.py`.
CANONICAL = DESK / "scripts" / "external_gauntlet.py"

#: A trial count derived from the WIDTH OF THE SWEEP. `matrix.shape[1]` is the number of cells in
#: this batch, `len(cells)` likewise -- multiplying either by a multiplier is precisely the tax
#: the fixed wall removed.
_BATCH_SCALED = re.compile(
    r"n_trials\s*=.*(?:matrix\.shape\[1\]|len\(\s*cells\s*\)|n_cells)\s*\*", re.IGNORECASE)


def _py_files() -> list[Path]:
    return [p for p in sorted(DESK.rglob("*.py")) if p.name != Path(__file__).name]


def test_the_scheduled_gauntlet_charges_the_fixed_wall() -> None:
    """MT5-Gauntlet's script must take its trial count from policy, not invent one."""
    assert CANONICAL.exists(), f"the scheduled gauntlet is missing: {CANONICAL}"
    src = CANONICAL.read_text(encoding="utf-8", errors="replace")
    assert "charged_trial_count" in src, (
        "scripts/external_gauntlet.py no longer derives n_trials from `charged_trial_count`. "
        "That function is where the principal's fixed wall lives (gate_policy.trial_basis -> "
        "fixed_campaign_trials). Computing a trial count locally reintroduces the breadth tax.")


def test_the_fixed_wall_is_actually_declared_in_policy() -> None:
    """A fail-closed fallback that is always taken is not a wall. The spec must carry the number."""
    from research import gate_policy
    fixed = gate_policy._SPEC_FIXED_TRIALS
    assert isinstance(fixed, int) and fixed >= 2, (
        f"gate_spec.yaml declares no fixed_trial_count (got {fixed!r}), so charged_trial_count() "
        f"falls back to raw_cells x multiplier -- the batch-width tax, silently.")
    n, why = gate_policy.charged_trial_count(50, None, None)
    wide, wide_why = gate_policy.charged_trial_count(5000, None, None)
    assert n == wide == fixed, (
        f"the charge moved with the sweep width: {n} at 50 cells ({why}) vs {wide} at 5000 "
        f"({wide_why}). Breadth must never raise a candidate's bar.")
    # THE SECOND DOOR, closed 2026-08-29 and pinned here. The hurdle is
    # expected_max_sharpe(n_trials, variance_of_sharpes), and pinning trials alone left the bar
    # rising with a wider batch's Sharpe dispersion: 0.0149 at 460 cells vs 0.6238 at 1,985, a
    # bar four times higher for the same candidate. Both inputs must be constants or neither is.
    assert isinstance(gate_policy.FIXED_VARIANCE_OF_SHARPES, float), (
        "fixed_variance_of_sharpes is not declared, so the dispersion input still floats with "
        "the sweep and breadth taxes the bar through the second door.")


def test_no_module_recomputes_a_trial_count_from_batch_width() -> None:
    """The bypass that misled the 2026-09-11 review must not come back anywhere on the desk."""
    offenders: list[str] = []
    for p in _py_files():
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            if _BATCH_SCALED.search(line):
                offenders.append(f"{p.relative_to(DESK)}:{i}: {line.strip()[:100]}")
    assert not offenders, (
        "a trial count is being scaled by the number of cells in the sweep, which taxes breadth "
        "and contradicts the fixed wall (principal 2026-07-23, restated 2026-09-11). Route it "
        "through `gate_policy.charged_trial_count`:\n  " + "\n  ".join(offenders))
