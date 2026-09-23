"""THE PLUMBING-INVARIANT HIERARCHY -- what each money-path law is pinned BY, and how hard.

    python scripts/check_plumbing_invariants.py            # verify, print the census, exit 1 on a lie
    python scripts/check_plumbing_invariants.py --render   # also rewrite docs/research/PLUMBING_INVARIANTS.md

WHY A HIERARCHY AND NOT A TEST COUNT (Tier-1 B26). Every invariant below was already "covered":
each had a test, each test passed, and the ledger's honest entry for all of them was the same
sentence -- *pinned by example*. An example proves the law on the ONE state its author thought
of, and none of the states that actually broke this desk were states anybody thought of: an
identity that was `ok` but UNMEASURED, a registry row frozen before `forward_start` existed,
three certificates agreeing on the CHF leg at the venue minimum lot. So "tested" is not the unit.
The unit is HOW MUCH OF THE STATE SPACE the test speaks for:

    EXAMPLE   one hand-written state. The law holds there and nowhere is it claimed to hold else.
    PROPERTY  a generator draws states and the law is asserted over every draw. A counterexample
              is found by the machine, not by an incident.
    PROOF     the domain is FINITE and the test enumerates all of it. There is no counterexample
              left to find; this is the strongest thing a test can be, and it is available only
              where the state space is small enough to walk (four booleans, a retcode table).

THE CHECK IS THAT THE LEDGER IS NOT LYING. Every enforcing test named here must exist, and must
be COLLECTED by pytest under its exact node id -- a renamed test, a file moved, a test quietly
deleted, or one that no longer collects (an import error is the usual way) all read as a lie and
exit 1. This is the same rule `check_tier1_program.py` applies to the programme ledger: a ledger
nobody verifies is worth less than no ledger, because it is believed.

Registered in `scripts/run_law_gate.py` (_LAW_FENCES): it reads scripts/, desks/mt5/tests/ and
libs/, all committed, so it means the same thing in CI, in a fresh clone and on the box.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RENDERED = ROOT / "docs" / "research" / "PLUMBING_INVARIANTS.md"
ARTIFACT = ROOT / "desks" / "mt5" / "reports" / "PLUMBING_INVARIANTS.json"

LEVELS = ("EXAMPLE", "PROPERTY", "PROOF")

#: The ledger. `subject` is the code the law is ABOUT -- the thing that would have to change for
#: the law to break -- and `tests` are the node ids that speak for it. A level is a claim about
#: the generator, not about the assertion: PROPERTY means states are drawn, PROOF means they are
#: all walked.
INVARIANTS: tuple[dict[str, Any], ...] = (
    {
        "id": "PI-1",
        "invariant": "no-order-without-authority",
        "law": "LAWS 4 (production firewall) + L1.38 sterile cockpit + L1.44 consumption-time "
               "freshness: the box opens new risk only while the code it runs is the code that "
               "was sealed and tested, and UNMEASURED is never a licence (L1.28a).",
        "subject": "desks/mt5/mt5desk/release_identity.py:144 Identity.allows_new_risk; "
                   "desks/mt5/mt5desk/decision_core.py:1940 release_gate",
        "level": "PROOF",
        "why_level": "the decision is a function of four booleans (ok, measured, stale, "
                     "stale_refuses); the test walks all sixteen states, and `release_gate` is "
                     "driven through all sixteen plus a raising identity module. Nothing is left "
                     "undrawn.",
        "tests": (
            "desks/mt5/tests/test_plumbing_invariants.py::test_no_order_without_authority",
            "desks/mt5/tests/test_plumbing_invariants.py::"
            "test_release_gate_refuses_rather_than_raises",
        ),
    },
    {
        "id": "PI-2",
        "invariant": "no-forward-rebase",
        "law": "L1.58 SAME-DAY PIPELINE: the forward window is never compressed, backdated or "
               "waived; every clock carries a `forward_start` stamped at pre-registration.",
        "subject": "desks/mt5/research/sleeve_registry.py:238 freeze",
        "level": "PROPERTY",
        "why_level": "the domain is every SEQUENCE of freeze calls, which is infinite; sequences "
                     "of up to twelve calls over three keys and four stamps (including the null "
                     "stamp that caused the 2026-08-27 backfill defect) are drawn by hypothesis, "
                     "and the law -- identity append-only, forward_start monotone-earlier -- is "
                     "asserted after every call in every sequence.",
        "tests": ("desks/mt5/tests/test_plumbing_invariants.py::test_no_forward_rebase",),
    },
    {
        "id": "PI-3",
        "invariant": "no-duplicate-risk",
        "law": "L1.18/L1.18a maximum INDEPENDENT compounding sources: three certificates that "
               "happen to agree are one bet, and at the venue minimum lot sizing cannot answer "
               "a duplicate (measured 2026-09-16, EURCHF sell 0.01 three times).",
        "subject": "desks/mt5/mt5desk/leg_balance.py:92 already_held; "
                   "desks/mt5/mt5desk/gateway.py:1243 same_side_count",
        "level": "PROPERTY",
        "why_level": "books of up to eight positions over three symbols, both sides, tagged and "
                     "untagged, with a pending decision from this same pass, are drawn and the "
                     "held-lots answer is checked against an independent recount; "
                     "`same_side_count` is separately shown never to UNDER-count the desk's own "
                     "tagged legs, which is the direction that lets a second bet through.",
        "tests": (
            "desks/mt5/tests/test_plumbing_invariants.py::test_no_duplicate_risk",
            "desks/mt5/tests/test_plumbing_invariants.py::"
            "test_same_side_count_never_undercounts_tagged_legs",
        ),
    },
    {
        "id": "PI-4",
        "invariant": "no-inserted-gate",
        "law": "L1.60 ONE PIPELINE, NO INSERTED GATES: no screen, searcher or miner may apply a "
               "threshold of its own in EITHER direction, and multiplicity is judged once, on "
               "the SEALED constants of the policy -- never on a quantity a producer supplies.",
        "subject": "desks/mt5/research/gate_policy.py (the canonical policy's constants)",
        "level": "PROPERTY",
        "why_level": "producer-supplied trial counts are drawn and the policy module's own "
                     "numeric constants are re-read after each: a bar that moved because a "
                     "producer spoke is the breach, and it is checked rather than assumed.",
        "tests": ("desks/mt5/tests/test_plumbing_invariants.py::"
                  "test_no_inserted_gate_producer_cannot_move_the_bar",),
    },
    {
        "id": "PI-5",
        "invariant": "heat-floor-never-breached",
        "law": "GROWTH_GOVERNANCE + LAWS 2a: 20% floor, flat, 24/7; the resolved heat is FILLED, "
               "never reported short; growth is free above it to the 30% ceiling. The one "
               "declared exception is the objective's own catastrophe constraint (L1.23, sealed).",
        "subject": "desks/mt5/research/heat_policy.py:520 resolve",
        "level": "PROPERTY",
        "why_level": "free optima from -0.5 to 1.5 and randomised growth curves (including "
                     "curves that pay nothing anywhere) are drawn; every resolution that is not "
                     "the sealed catastrophe branch must land on or above the floor and on or "
                     "below the hard ceiling.",
        "tests": ("desks/mt5/tests/test_plumbing_invariants.py::"
                  "test_heat_floor_is_never_breached",),
    },
    {
        "id": "PI-6",
        "invariant": "immutable-core-intact",
        "law": "L2.8a IMMUTABLE CORE (sealed): the principal's doctrine is hashed, fails loud, "
               "and only the principal reseals it.",
        "subject": "ops/principal_doctrine.txt sealed by scripts/check_constitution_core.py",
        "level": "PROOF",
        "why_level": "a keyed digest over the whole sealed text: the domain is the file's bytes "
                     "and the check reads all of them. Nothing is sampled.",
        "tests": ("desks/mt5/tests/test_plumbing_invariants.py::"
                  "test_immutable_core_seal_is_intact",),
    },
    {
        "id": "PI-7",
        "invariant": "money-path-decisions-reachable",
        "law": "LAWS 7 enforcement wiring + L1.38: a decision that moved must still be reachable "
               "through the gateway, and the core must import with no broker library present.",
        "subject": "desks/mt5/mt5desk/decision_core.py",
        "level": "EXAMPLE",
        "why_level": "the reachability and import laws are asserted on the tree as it is -- one "
                     "state, the current one. There is no generator over 'a tree' that means "
                     "anything, so this stays EXAMPLE honestly rather than being relabelled.",
        "tests": (
            "desks/mt5/tests/test_decision_core.py::"
            "test_the_core_imports_without_the_broker_library",
            "desks/mt5/tests/test_decision_core.py::"
            "test_every_decision_that_moved_is_still_reachable_through_the_gateway",
        ),
    },
)


def _node_file(node: str) -> Path:
    return ROOT / node.split("::", 1)[0]


def collected(paths: list[Path], timeout: float = 300.0) -> tuple[set[str], str]:
    """Every node id pytest can collect from `paths`, and the reason it could not.

    COLLECTION IS THE MEASUREMENT (CLAUDE.md: "COLLECTION IS A SEPARATE GATE"). A test file that
    exists and contains the right `def` but raises on import is exactly the state this fence is
    for -- the law reads enforced and nothing runs it (L1.49).
    """
    if not paths:
        return set(), "no test files to collect"
    try:
        # NO EXTRA `-q`: pyproject's addopts already carries one, and a second collapses the
        # node ids into a per-file count -- which reads here as "nothing collects".
        r = subprocess.run([sys.executable, "-m", "pytest", "--co", "-p", "no:cacheprovider",
                            *[str(p) for p in paths]],
                           capture_output=True, text=True, cwd=str(ROOT), timeout=timeout,
                           check=False)
    except (subprocess.TimeoutExpired, OSError) as exc:
        return set(), f"collection did not run: {type(exc).__name__}: {exc}"
    out = set()
    for line in (r.stdout or "").splitlines():
        line = line.strip()
        if "::" in line and not line.startswith(("=", "-", "<")):
            out.add(line.replace("\\", "/"))
    # A node id printed as `path::test` is normalised to the repo-relative form the ledger uses.
    return out, ("" if r.returncode == 0 else
                 f"pytest --co exited {r.returncode}: {(r.stdout or r.stderr or '')[-300:]}")


def check(root: Path = ROOT, *, collect: bool = True) -> tuple[list[str], dict[str, Any]]:
    problems: list[str] = []
    files: list[Path] = []
    for inv in INVARIANTS:
        if inv["level"] not in LEVELS:
            problems.append(f"{inv['id']}: level {inv['level']!r} is not one of {LEVELS}")
        if not inv.get("tests"):
            problems.append(f"{inv['id']}: no enforcing test -- an invariant nothing runs is a "
                            f"claim the desk cannot cash (L1.49)")
        for node in inv["tests"]:
            f = root / node.split("::", 1)[0]
            if not f.exists():
                problems.append(f"{inv['id']}: enforcing test file {node.split('::')[0]} "
                                f"does not exist")
                continue
            if f not in files:
                files.append(f)
            if "::" in node:
                fn = node.split("::", 1)[1]
                if not re.search(rf"^\s*def {re.escape(fn)}\s*\(", f.read_text("utf-8"), re.M):
                    problems.append(f"{inv['id']}: {f.name} carries no `def {fn}`")
    census = {lv: sum(1 for i in INVARIANTS if i["level"] == lv) for lv in LEVELS}
    nodes: set[str] = set()
    why = ""
    if collect and not problems:
        nodes, why = collected(files)
        if why:
            problems.append(f"collection: {why}")
        for inv in INVARIANTS:
            for node in inv["tests"]:
                if "::" not in node:
                    continue
                if node.replace("\\", "/") not in nodes:
                    problems.append(f"{inv['id']}: pytest does not collect {node}")
    return problems, {"n": len(INVARIANTS), "by_level": census, "n_collected": len(nodes),
                      "n_test_files": len(files)}


def render(census: dict[str, Any]) -> str:
    out = ["# Plumbing invariants — the verification hierarchy", "",
           "Generated by `python scripts/check_plumbing_invariants.py --render`. Do not edit by "
           "hand; edit the ledger in that script. The checker exits 1 when an entry here names a "
           "test that does not exist, does not carry the named function, or is not collected by "
           "pytest — so this table is a measurement, not a description.", "",
           "| level | meaning |", "|---|---|",
           "| EXAMPLE | one hand-written state; the law holds there and nowhere else is claimed |",
           "| PROPERTY | states are drawn by a generator and the law is asserted over every draw |",
           "| PROOF | the domain is finite and the test walks all of it; no counterexample remains |",
           "",
           f"**Census:** {census['n']} invariants — "
           + ", ".join(f"{k} {v}" for k, v in census["by_level"].items())
           + f" · {census['n_collected']} node(s) collected from {census['n_test_files']} file(s).",
           "", "## Invariants", ""]
    for inv in INVARIANTS:
        out += [f"### {inv['id']} — {inv['invariant']} · **{inv['level']}**", "",
                f"- **Law.** {inv['law']}",
                f"- **Subject.** `{inv['subject']}`",
                f"- **Why this level.** {inv['why_level']}",
                "- **Enforced by.**"]
        out += [f"  - `{n}`" for n in inv["tests"]]
        out.append("")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--no-collect", action="store_true",
                    help="skip the pytest collection probe (structure only)")
    ap.add_argument("--out", type=Path, default=RENDERED)
    args = ap.parse_args(argv)
    problems, census = check(collect=not args.no_collect)
    print("plumbing invariants: " + ", ".join(f"{k} {v}" for k, v in census["by_level"].items())
          + f" ({census['n']} total); {census['n_collected']} enforcing node(s) collected")
    for p in problems:
        print(f"  LIE: {p}")
    try:
        ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
        ARTIFACT.write_text(json.dumps(
            {"census": census, "problems": problems,
             "invariants": [{k: (list(v) if isinstance(v, tuple) else v)
                             for k, v in i.items()} for i in INVARIANTS]},
            indent=1), "utf-8")
    except OSError:
        pass
    if args.render:
        args.out.write_text(render(census), "utf-8")
        print(f"rendered {args.out}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
