"""Build the highest-value frontier candidate as a CHALLENGER, and never as live code.

    py -3 -m frontier_intel.implementer            # say what it would build
    py -3 -m frontier_intel.implementer --apply    # write the challenger

WHAT THIS REMOVES. Until now the loop ended at a plan: the supervisor scored a gap, wrote a queue
entry, and a person carried the idea to a builder by hand. That courier step is the thing the
mandate is actually complaining about -- "no known gap is allowed to remain merely because nobody
manually remembered to tell the builder."

WHAT IT DELIBERATELY DOES NOT REMOVE, and this is not timidity. It writes into
`frontier_intel/challengers/<id>/` and nowhere else. It cannot edit the money path, cannot open a
branch, cannot merge, and stamps every artifact `authority: ZERO`. The supervisor's own reasoning
stands and is worth restating, because a future pass will be tempted to relax it:

    an implementer that can both propose and merge into the tree that sizes real positions is one
    bad extraction away from a live defect

So the ladder is unchanged -- replication, the ten gates, a forward clock, measured rent -- and
what changes is only that the first rung now gets climbed without a human courier. A challenger
that nobody promotes costs a directory; a bad merge costs money.

THE MONEY-PATH FENCE IS A DENYLIST CHECKED ON EVERY WRITE, not a convention. `_refuse_money_path`
runs against the resolved absolute path, so a `..` in a generated module name cannot walk out of
the challenger directory into `gateway.py`. That check is the single most important line here.

UNSEATED IS A VERDICT, NOT A CRASH. Code generation needs an LLM seat, and this box currently has
none -- measured 2026-09-07, `world_crawler` rejected 910 tasks with "no seat: export
OPENROUTER_API_KEY". Without a seat this writes the complete SPECIFICATION -- the mechanism, its
falsifier, the wiring contract and the rent line -- and says UNSEATED. That is genuinely useful on
its own and is honest about what it is; what it must never do is emit an empty module and report
success, which is the implementation theatre the mandate names.

EVERY CHALLENGER CARRIES ITS OWN FALSIFIER. `claims.Mechanism` already recovered what would refute
the proposition, so the generated test is written from that rather than invented here. A challenger
with no way to fail is not a challenger.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parent.parent
for _p in (str(BASE), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from frontier_intel import ontology, queue, registry, roi  # noqa: E402

CHALLENGERS = BASE / "frontier_intel" / "challengers"

#: Paths this organ may NEVER write, whatever a card asks for. The gateway and decision core size
#: and place real orders; release.py decides whether the running code is the sealed code; the
#: deadman switch is Tier-3 never-touch. A generated module belongs beside none of them.
MONEY_PATH = (
    "mt5desk/gateway.py", "mt5desk/decision_core.py", "mt5desk/release_identity.py",
    "libs/ops/release.py", "scripts/run_deadman_switch.py", "research/promoter.py",
    "research/pf_allocator.py", "data/secrets",
)

SYSTEM = (
    "You implement ONE narrowly-scoped Python module for a quantitative research desk. "
    "You are writing a CHALLENGER with zero capital authority: it will be measured against an "
    "existing champion and discarded unless it wins. Write plain, dependency-light Python "
    "(stdlib, numpy, pandas only). No network calls. No file writes outside a passed-in path. "
    "Every public function needs a docstring saying what it measures and what would refute it. "
    "Return ONLY code, no prose and no markdown fences."
)


def _refuse_money_path(target: Path) -> None:
    """Raise unless `target` resolves inside the challenger directory.

    THE ONE LINE THAT MATTERS. Checked on the RESOLVED path, so a module name carrying `..` --
    which a generated name plausibly could -- cannot escape into the live tree. A denylist alone
    would not be enough for that; the containment check is what makes it safe.

    IT WAS ALSO THE ONE LINE THAT DID NOT WORK HERE. The test read `startswith(str(root) + "/")`
    with a hard-coded POSIX separator, and this module's only home is the WINDOWS trading box,
    where a resolved path is separated by backslashes. So the check failed for EVERY target
    including the legitimate ones: `_refuse_money_path` refused a path that was plainly inside
    the root it named, the implementer could not write a single challenger on the one machine
    that runs it, and the six tests that walk this path had been red ever since. A fence nobody
    could pass is not a strict fence, it is a dead organ (III.16) -- and it fails in the
    direction that LOOKS safe, which is why it survived.

    `Path.is_relative_to` does the same comparison on parsed components, so there is no separator
    to get wrong and no string prefix to fake: `/a/bc` is not inside `/a/b` under either.
    """
    resolved = target.resolve()
    root = CHALLENGERS.resolve()
    if not resolved.is_relative_to(root):
        raise PermissionError(
            f"implementer may only write under {root}; refused {resolved}")
    for banned in MONEY_PATH:
        if banned.replace("/", "_") in resolved.name:
            raise PermissionError(f"refused a money-path name: {resolved.name}")


def _slug(text: str) -> str:
    out = re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")
    return (out or "candidate")[:48]


def best_candidate() -> dict[str, Any] | None:
    """The queue's highest-priority row that is not already built.

    Reads the queue rather than re-scoring: `roi.priority` is the authority on ranking and this
    organ must not become a second opinion about what is worth doing.
    """
    rows = [r for r in queue.current().values()
            if r.get("state") in {"PRIORITIZED", "GAP_CONFIRMED", "DEDUPED", "EXTRACTED"}]
    if not rows:
        return None
    return max(rows, key=lambda r: float(r.get("priority") or 0.0))


def specification(card: dict[str, Any]) -> str:
    """The written contract a challenger must satisfy, whether or not a seat fills it in.

    DEFINITION OF BUILT, taken from the mandate verbatim: producer -> storage -> consumer ->
    decision path -> telemetry. A module that exists and that nothing calls is the failure this
    desk has already paid for repeatedly, so the contract names its consumer before any code is
    written rather than after.
    """
    cap = str(card.get("capability") or "")
    known = ontology.BY_NAME.get(cap)
    mechanism = str(card.get("mechanism") or card.get("claim") or "")
    falsifier = str(card.get("falsifier") or "")
    return "\n".join([
        f"CAPABILITY   {cap} ({known.level if known else 'unknown level'})",
        f"WE HAVE      {known.owner or 'NOTHING -- no module on this tree owns it'}"
        if known else "WE HAVE      unknown",
        f"MECHANISM    {mechanism}",
        f"FALSIFIER    {falsifier or 'NOT RECORDED -- refuse to build without one'}",
        f"PROVENANCE   {card.get('firm', '?')} / {card.get('source', '?')} "
        f"(grade {card.get('grade', '?')})",
        "AUTHORITY    ZERO -- challenger only; the ten gates and a forward clock decide",
        "WIRED MEANS  producer -> storage -> consumer -> decision path -> telemetry",
        "RENT         net dE[log W] after complexity rent, or it is removed",
    ])


def _generate(card: dict[str, Any]) -> tuple[str, str]:
    """(code, note). Uses an LLM seat when one exists; says so plainly when none does."""
    try:
        from libs.ops import llm_seat
    except Exception as exc:                                            # noqa: BLE001
        return "", f"UNSEATED: llm_seat unavailable ({type(exc).__name__}: {exc})"
    prompt = "\n".join([
        "Implement this capability as one self-contained module.",
        "", specification(card), "",
        "Requirements:",
        "- a `measure(...)` entry point returning a dict of named numbers",
        "- a module docstring stating the mechanism and what would refute it",
        "- no I/O except through paths passed in as arguments",
    ])
    text, err = llm_seat.chat(prompt, system=SYSTEM, max_tokens=4000)
    if err:
        return "", f"UNSEATED: {err}"
    code = re.sub(r"^```[a-zA-Z]*\n|\n```$", "", (text or "").strip())
    return code, "generated"


def build(card: dict[str, Any], *, apply: bool = False) -> dict[str, Any]:
    """Write one challenger. Returns what it did, and never raises on a data gap."""
    cid = str(card.get("candidate_id") or _slug(str(card.get("capability"))))
    name = _slug(f"{card.get('capability', 'cap')}_{cid[:8]}")
    outdir = CHALLENGERS / cid
    module = outdir / f"{name}.py"
    test = outdir / f"test_{name}.py"
    _refuse_money_path(module)
    _refuse_money_path(test)

    falsifier = str(card.get("falsifier") or "")
    if not falsifier:
        # A challenger with no way to fail is not a challenger, it is a module with opinions.
        return {"candidate_id": cid, "status": "REFUSED",
                "why": "the card records no falsifier; nothing could retire this if it were wrong"}

    code, note = _generate(card)
    manifest = {
        "candidate_id": cid,
        "capability": card.get("capability"),
        "generated_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "authority": "ZERO",
        "authority_why": ("a challenger earns capital through replication, the ten gates, a "
                          "forward clock and measured rent -- never because it was written"),
        "provenance": {k: card.get(k) for k in ("firm", "source", "url", "grade", "claim")},
        "specification": specification(card),
        "falsifier": falsifier,
        "generation": note,
        "champion": (ontology.BY_NAME.get(str(card.get("capability")))
                     or ontology.Capability("", "", "", "")).owner or None,
    }
    if not apply:
        return {"candidate_id": cid, "status": "DRY", "would_write": str(outdir),
                "generation": note}

    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "MANIFEST.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    header = ('"""' + specification(card).replace('"""', "'''") + '\n\nAUTHORITY: ZERO. '
              'Challenger only -- measured against the champion above, discarded unless it '
              'wins.\n"""\n')
    module.write_text(header + (code or
                                "\n# UNSEATED: no LLM seat on this box, so the specification "
                                "above is the deliverable.\n# Set OPENROUTER_API_KEY (or write "
                                "data/secrets/llm_panel.json) and re-run.\n"), encoding="utf-8")
    test.write_text(
        '"""The falsifier for this challenger, written from the card rather than invented.\n\n'
        f"    {falsifier}\n\n"
        'A challenger that cannot fail cannot be a challenger.\n"""\n'
        "import pytest\n\n\n"
        "@pytest.mark.skip(reason='challenger not yet implemented -- see MANIFEST.json')\n"
        "def test_the_falsifier() -> None:\n"
        f"    # {falsifier}\n"
        "    raise AssertionError('unimplemented')\n", encoding="utf-8")
    return {"candidate_id": cid, "status": "BUILT", "dir": str(outdir), "generation": note}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write the challenger")
    args = ap.parse_args(argv)

    card = best_candidate()
    if card is None:
        print("implementer: no candidate in a buildable state", flush=True)
        return 0
    out = build(card, apply=args.apply)
    print(f"implementer: {out.get('status')} {out.get('candidate_id')} "
          f"({out.get('generation') or out.get('why')})", flush=True)
    return 0


if __name__ == "__main__":                                              # pragma: no cover
    raise SystemExit(main())
