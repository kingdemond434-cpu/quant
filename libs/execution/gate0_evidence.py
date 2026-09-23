"""The Gate-0 evidence readings that two organs must never disagree about (L1.61, R0536/R0537).

WHY THIS MODULE EXISTS. ``libs/execution/staging.py:s1_entry_met`` is called by BOTH
``scripts/check_gate0_ready.py`` (the board a human reads on launch day) and
``scripts/run_live_guard.py`` (the executor-side evaluator). The gate arithmetic was already
shared; the EVIDENCE was not. Each organ built the ``evidence`` dict from its own sources, and
two of the five criteria were built from sources that do not exist:

  * ``principal_signoff`` -- the guard read ``data/stage_state.json['principal_signoff']``,
    A KEY NO CODE ANYWHERE WRITES, while consent actually lives in ``data/gate0_signoff.json``
    (the principal signed 2026-07-30). The guard therefore reported consent False permanently
    and was STRUCTURALLY INCAPABLE of ever seeing a signoff.
  * ``symbol_count`` -- the guard reached the criterion ONLY through the ``data/ramp_state.json``
    evidence spread, a file that has never existed on this box, so ``int(...)`` defaulted to 0
    and the criterion read False while ``data/cashcarry_config.json`` has ``top=4``.

Both sides read their own source successfully and published honestly, so no single-artifact
instrument could see it -- that is L1.61's whole argument, and this is the repair it prescribes:
REPAIR THE INPUT, NOT THE VERDICT. The contract is now one function per criterion, so a future
edit cannot re-create the divergence by touching one caller.

THIS MODULE MEASURES AND NOTHING ELSE. It opens no gate, sizes nothing and promotes nothing:
``s1_entry_met`` still requires all five criteria, and on an unarmed box ``keys_present`` is
False, so the gate it feeds stays shut on its own genuine grounds. What changes is that two
criteria stop being DEFAULTS rendered as measurements.

ABSENCE IS A REAL ANSWER HERE, AND IT IS NOT AN UNMEASURED ONE. The signoff file IS the consent:
its absence means "the principal has not signed", not "the input is missing" (L1.28a's
distinction runs the other way for a file whose existence is itself the datum). Deleting it
revokes. That is why ``principal_signoff`` returns a plain bool while ``symbol_count`` -- whose
source can genuinely be unreadable -- returns None rather than a fabricated 0.
"""

from __future__ import annotations

import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent

#: The file IS the consent. Nothing writes a flag; the principal's act creates this artifact and
#: deleting it revokes. Both organs must ask this one question of this one path.
SIGNOFF_REL = "data/gate0_signoff.json"

#: The executor's live knob for concurrent carries. Gate 0 admits 4-5 names.
CONFIG_REL = "data/cashcarry_config.json"


def principal_signoff(root: Path | None = None) -> bool:
    """Has the principal recorded Gate-0 consent?

    Presence of the artifact is the whole predicate -- deliberately NOT a parse of its contents.
    A corrupt-but-present signoff must not read as a revocation, and a readable-but-empty one
    must not read as consent; the act the principal took was creating the file.
    """
    return ((root or _ROOT) / SIGNOFF_REL).exists()


def symbol_count(root: Path | None = None) -> int | None:
    """How many concurrent carries are configured? ``None`` when the config cannot be read.

    None is NOT zero. A caller that turns an unreadable config into 0 publishes a criterion
    verdict it never measured, which is exactly the defect this module exists to end -- callers
    feeding ``s1_entry_met`` should pass the value through only when it is not None and let the
    gate's own fail-closed default refuse otherwise.
    """
    try:
        cfg = json.loads(((root or _ROOT) / CONFIG_REL).read_text("utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(cfg, dict):
        return None
    try:
        return int(cfg.get("top", 0))
    except (TypeError, ValueError):
        return None
