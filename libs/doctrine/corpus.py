"""WHAT AN ORGAN ACTUALLY RECEIVES -- the doctrine payload, derived from its injector.

WHY THIS EXISTS, measured 2026-08-28. The principal's consolidation of 2026-08-25 emptied
`ops/principal_doctrine.txt` of its law text: the file became the slim order channel (sealed core
+ MT5 universe mandate) and the operative constitution moved to `docs/LAWS.md`. `ops/brain_env.sh`
was changed in the same breath to `cat` BOTH files into one payload, so not one organ lost one
line of law.

Every fence that read the law, however, still read ONE FILE. Five of them plus the prompt ratchet
went red, reporting twelve invariants "DROPPED" and laws L1.28b/L1.29/L1.30/L1.31/L2.3 absent --
about text sitting in the sibling document injected in the same `cat`. Twenty-five tests red, the
desk-wide CI gate down for days, and every one of those reds a lie.

THE FALSE RED IS THE DANGEROUS HALF, not an inconvenience. `max_audit.check_ci_gate` carries the
lesson in its own body: a red nobody can act on recurs, gets skimmed, and BURIES a real one. A
doctrine-reach fence stuck red cannot tell the desk that a law genuinely stopped reaching its
organs -- which is the only thing it was built to say.

THE UNIT IS THE PAYLOAD, NOT THE FILE. A law reaches an organ if it is anywhere in what gets
injected. Which files those are is a fact about `brain_env.sh`, so this module READS
`brain_env.sh` rather than restating its list: relocate a law between the two governing documents,
or add a third, and the fences follow with no edit here. The literal below is a BOOTSTRAP SEED for
the case where the parse fails, and it says so -- never a boundary (LAWS section 1, anti-hardcode).

WHAT IS STILL GUARANTEED. A law deleted from BOTH documents is absent from the payload and every
fence fails by name, exactly as before. What is no longer reported is the movement of text between
two files an organ receives as one string -- which was never a regression, only a relocation.
"""
from __future__ import annotations

import re
from pathlib import Path

__all__ = ["DOCTRINE_SEED", "doctrine_files", "doctrine_text"]

_ROOT = Path(__file__).resolve().parents[2]

#: BOOTSTRAP SEED, not a boundary. Used only when brain_env.sh cannot be read or parsed; the
#: authoritative list is whatever that script actually concatenates.
DOCTRINE_SEED: tuple[str, ...] = ("ops/principal_doctrine.txt", "docs/LAWS.md")

#: The assignment that builds the payload. Kept as a pattern rather than a line number so an
#: edit above it does not silently break the parse.
_ASSIGN = re.compile(r'^_DOCTRINE="\$\(cat\s+(?P<args>[^)]*)\)"', re.M)
_PATH = re.compile(r'"\$\{?_BRAIN_ROOT\}?/([^"]+)"')


def doctrine_files(root: Path | str = _ROOT) -> tuple[str, ...]:
    """The repo-relative files `ops/brain_env.sh` concatenates into every organ's doctrine.

    Falls back to DOCTRINE_SEED if the script is unreadable or the assignment has been rewritten
    beyond recognition -- an unparseable injector must not silently narrow the corpus to nothing,
    which would turn every doctrine fence green for the wrong reason.
    """
    base = Path(root)
    try:
        src = (base / "ops" / "brain_env.sh").read_text("utf-8")
    except OSError:
        return DOCTRINE_SEED
    m = _ASSIGN.search(src)
    if not m:
        return DOCTRINE_SEED
    found = tuple(_PATH.findall(m.group("args")))
    return found or DOCTRINE_SEED


def doctrine_text(root: Path | str = _ROOT) -> str:
    """The payload as an organ receives it: every injected file, concatenated, in order."""
    base = Path(root)
    parts = []
    for rel in doctrine_files(base):
        try:
            parts.append((base / rel).read_text("utf-8"))
        except OSError:
            continue
    return "\n".join(parts)
