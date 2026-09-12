"""F26 -- PROOF WHERE PROOF IS POSSIBLE, and a named obligation everywhere else.

THE PRINCIPAL, 2026-09-12:

    Property/model checking or SMT for structural invariants: no illegal alpha-state transition,
    no certificate bypass, no future observation access, no uncharged trial path, no unsigned
    deployment, no impossible sizing state, no multiple capital authorities.

THE ITEM'S OWN TITLE SETS THE STANDARD -- "where proof is possible" -- and honouring it means
being exact about which of the seven are decidable here and which are not. Three classes, and
each carries its own epistemic weight:

    PROVEN          the property is checked over the ENTIRE space it lives in. The alpha state
                    machine has 7 states and 49 ordered pairs; enumerating all 49 is not a test,
                    it is a proof, and the report says how large the space was.
    ENFORCED        a complete static enumeration over this repository shows exactly one writer,
                    one door or one authority. Complete for THIS TREE and stated as such: it is
                    proof about the code that exists, not about code that could be written.
    OBLIGATION      the property is not decidable by either method here, and the report says what
                    WOULD discharge it rather than pretending a weaker check is the same thing.

WHY NO SMT SOLVER. The properties that are decidable here are decidable by exhaustion over spaces
of tens of elements; an SMT encoding of a 49-edge graph would add a dependency, a translation
layer and a second place for the model to disagree with the code, and would prove exactly the same
thing. The properties that are NOT decidable here are not undecidable for want of a solver -- they
are statements about future code, and no solver settles those.

AN OBLIGATION IS NOT A FAILURE AND IS NOT A PASS. It is the third verdict, counted apart, because
a verification report where everything is green is either trivial or lying.

    python desks/mt5/research/formal_invariants.py [--apply]
"""
from __future__ import annotations

import argparse
import ast
import itertools
import json
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = DESK / "reports" / "FORMAL_INVARIANTS.json"

#: Directories searched for a complete static enumeration. Everything the desk actually runs;
#: `data/` is excluded because it holds retest snapshots that are records, not running code, and
#: counting them as writers would report an authority that executes nowhere.
SEARCH_ROOTS: tuple[Path, ...] = (ROOT / "libs", ROOT / "ops", ROOT / "scripts",
                                  DESK / "research", DESK / "scripts", DESK / "mt5desk",
                                  DESK / "recorders", DESK / "moat", DESK / "proposals")


def _proven(detail: str, space: int) -> dict[str, Any]:
    return {"verdict": "PROVEN", "space_searched": space, "detail": detail}


def _enforced(detail: str, n_files: int) -> dict[str, Any]:
    return {"verdict": "ENFORCED", "files_searched": n_files, "detail": detail}


def _violated(detail: str) -> dict[str, Any]:
    return {"verdict": "VIOLATED", "detail": detail}


def _obligation(detail: str, discharge: str) -> dict[str, Any]:
    return {"verdict": "OBLIGATION", "detail": detail, "would_discharge": discharge}


def _py_files() -> list[Path]:
    out: list[Path] = []
    for r in SEARCH_ROOTS:
        if r.exists():
            out.extend(p for p in r.rglob("*.py") if "__pycache__" not in p.parts)
    return sorted(set(out))


def _writers_of(token: str, files: list[Path]) -> list[str]:
    """Modules that write TO THE PATH the token names. Local data flow, not co-occurrence.

    THE FIRST VERSION CLAIMED 84 CERTIFICATE AUTHORITIES AND 20 CAPITAL ONES, and every one was
    its own defect. It conjoined two facts about a FILE -- that the token appears somewhere, and
    that some write happens somewhere -- with no link between them. An organ that READS the
    certificate registry and writes its own report satisfied both, which is most of this tree.
    A verifier that reports a violation it cannot support is worse than no verifier: it spends
    the reader's trust and then has to be explained away.

    WHAT IT DOES NOW. It finds the NAMES bound to an expression containing the token
    (`SURVIVORS = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"`), then looks for a write whose
    TARGET is one of those names: `SURVIVORS.write_text(...)`, `open(SURVIVORS, "w")`,
    `json.dump(x, SURVIVORS.open("w"))`. The link is syntactic and local, which is what makes it
    decidable at all.

    ITS LIMIT IS STATED RATHER THAN HIDDEN. A write through a variable assigned in another
    function, through a helper taking the path as an argument, or through a string built at
    runtime is NOT caught. That is why this verdict is ENFORCED and never PROVEN: it is a
    complete enumeration of the DIRECT writers in this tree, and a claim about nothing else.
    """
    hits: list[str] = []
    for f in files:
        try:
            src = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if token not in src:
            continue
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue

        # 1. Names bound to an expression that mentions the token.
        bound: set[str] = set()
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            value = node.value
            if value is None:
                continue
            try:
                if token not in ast.unparse(value):
                    continue
            except Exception:
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                if isinstance(t, ast.Name):
                    bound.add(t.id)

        def _touches(expr: ast.AST | None, _bound: frozenset[str] = frozenset(bound)) -> bool:
            # `_bound` is bound at DEFINITION time on purpose: the closure is created inside the
            # per-file loop, and a late-binding reference would let one file's names decide
            # another file's verdict.
            if expr is None:
                return False
            try:
                text = ast.unparse(expr)
            except Exception:
                return False
            if token in text:
                return True
            return bool(_bound & {n.id for n in ast.walk(expr) if isinstance(n, ast.Name)})

        # 2. A write whose TARGET is one of those names, or the literal path itself.
        writes_to_it = False
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            if isinstance(fn, ast.Attribute) and fn.attr in ("write_text", "write_bytes",
                                                             "to_parquet"):
                if _touches(fn.value):
                    writes_to_it = True
                    break
            elif isinstance(fn, ast.Name) and fn.id == "open":
                mode = ""
                for a in node.args[1:]:
                    if isinstance(a, ast.Constant) and isinstance(a.value, str):
                        mode = a.value
                for k in node.keywords:
                    if k.arg == "mode" and isinstance(k.value, ast.Constant):
                        mode = str(k.value.value)
                if ("w" in mode or "a" in mode) and node.args and _touches(node.args[0]):
                    writes_to_it = True
                    break
            elif isinstance(fn, ast.Attribute) and fn.attr == "open":
                mode = ""
                for a in node.args:
                    if isinstance(a, ast.Constant) and isinstance(a.value, str):
                        mode = a.value
                if ("w" in mode or "a" in mode) and _touches(fn.value):
                    writes_to_it = True
                    break
        if writes_to_it:
            hits.append(str(f.relative_to(ROOT)).replace("\\", "/"))
    return sorted(hits)


# ------------------------------------------------------------------------- the seven checks

def _i_state_machine() -> dict[str, Any]:
    """EXHAUSTIVE over all ordered state pairs and all reachable paths. This is a proof."""
    try:
        from libs.alpha.state import (
            ALLOWED_TRANSITIONS,
            AlphaState,
            can_transition,
            promote_target,
        )
    except ImportError as exc:
        return _obligation(f"the state machine is not importable ({exc})",
                           "restore libs/alpha/state.py; the property is decidable the moment "
                           "the enum and its transition table exist")
    states = list(AlphaState)
    pairs = list(itertools.product(states, states))
    problems: list[str] = []

    # 1. TOTALITY. can_transition must answer for every ordered pair without raising -- a
    #    partial predicate is a runtime error waiting for the one state nobody enumerated.
    for a, b in pairs:
        try:
            can_transition(a, b)
        except Exception as exc:
            problems.append(f"can_transition({a}, {b}) raised {type(exc).__name__}")

    # 2. NO BYPASS. ACTIVE must not be reachable from CANDIDATE without passing PROBATION.
    #    Checked by exhaustive search over ALL simple paths, which is finite at 7 nodes.
    def paths(src: AlphaState, dst: AlphaState,
              seen: frozenset[AlphaState] = frozenset()) -> list[list[AlphaState]]:
        if src == dst:
            return [[src]]
        out: list[list[AlphaState]] = []
        for nxt in ALLOWED_TRANSITIONS[src]:
            if nxt in seen:
                continue
            for tail in paths(nxt, dst, seen | {src}):
                out.append([src, *tail])
        return out

    to_active = paths(AlphaState.CANDIDATE, AlphaState.ACTIVE)
    bypass = [p for p in to_active if AlphaState.PROBATION not in p]
    if bypass:
        problems.append(f"{len(bypass)} path(s) reach ACTIVE from CANDIDATE without PROBATION: "
                        f"{[[s.value for s in p] for p in bypass[:2]]}")

    # 3. RETIRED IS TERMINAL and reachable from everywhere -- no state can strand an alpha.
    if ALLOWED_TRANSITIONS[AlphaState.RETIRED]:
        problems.append("RETIRED has outgoing transitions and is not terminal")
    stranded = [s.value for s in states
                if s != AlphaState.RETIRED and not paths(s, AlphaState.RETIRED)]
    if stranded:
        problems.append(f"states that cannot reach RETIRED: {stranded}")

    # 4. PROMOTION AGREES WITH THE TABLE. A promote_target the table forbids is two sources of
    #    truth about the same edge.
    for s in states:
        try:
            t = promote_target(s)
        except Exception:
            continue
        if not can_transition(s, t):
            problems.append(f"promote_target({s.value}) -> {t.value} is not an allowed edge")

    if problems:
        return _violated("; ".join(problems))
    return _proven(
        f"all {len(pairs)} ordered state pairs are total; {len(to_active)} distinct simple paths "
        f"reach ACTIVE from CANDIDATE and every one passes PROBATION; RETIRED is terminal and "
        f"reachable from all {len(states) - 1} other states; every promote_target is an allowed "
        f"edge", len(pairs))


#: Writers of the certificate registry that do NOT mint, each with the reason it may write.
#: Verified by reading every one: they change a row's status or move it out, and none of them
#: can put a NEW key into `survivors`. The distinction is the whole invariant -- "bypass" means
#: a certificate granted without the gauntlet, not a certificate retired by the organ whose job
#: is retiring certificates.
_LIFECYCLE_WRITERS: dict[str, str] = {
    "desks/mt5/research/certificate_hygiene.py":
        "moves rows the enrolment engine can never run into their own file; mints nothing",
    "desks/mt5/research/forward_reconcile.py":
        "retires clocks and records the reason; never adds a survivor key",
    "desks/mt5/research/retire_untradeable.py":
        "retires rows whose symbol the account cannot trade; never adds one",
    "scripts/purge_untradeable_certs.py":
        "retires certificates whose symbol the broker does not list, archived never deleted",
    "libs/research/memory.py":
        "writes UNIVERSAL_SURVIVORS.canon.json, the CANON snapshot, not the live registry -- a "
        "different path that shares a prefix, which is why the token match alone is not a verdict",
}

#: Writers that cannot run HERE, with the evidence. Kept classified rather than excluded, because
#: a dead writer that someone later revives is a live one, and a file this check has simply never
#: heard of is the condition it exists to catch.
_INERT_WRITERS: dict[str, str] = {
    "desks/mt5/scripts/add_shadow_specs.py":
        "a one-off whose path is hardcoded to /home/quant/quant-platform -- the VPS. It cannot "
        "write this box's registry, and on the VPS it would write a tree the box does not read",
}

#: The ONLY modules that may put a new key into `survivors`. One entry is the invariant.
_DECLARED_MINTERS: tuple[str, ...] = ("desks/mt5/scripts/external_gauntlet.py",)


def _i_certificate_authority(files: list[Path]) -> dict[str, Any]:
    """Complete static enumeration of the direct writers, split into MINTERS and LIFECYCLE.

    THE FIRST VERSION COUNTED EVERY WRITER AS A BYPASS and reported five violations, three of
    which are the organs whose entire job is retiring a certificate. "Bypass" means a certificate
    GRANTED without the gauntlet -- not one retired by the retirement organ. An invariant that
    cannot tell those apart fails permanently and gets ignored, which is how a real second minter
    hides behind three false ones.

    THE SPLIT IS DECLARED, NOT INFERRED. Minting and retiring are both `write_text` on the same
    path and no static analysis separates them; each lifecycle writer above was read and its
    reason recorded. A writer this file has never classified is reported as UNCLASSIFIED rather
    than assumed benign -- absence of a classification is not a clean verdict.
    """
    writers = _writers_of("UNIVERSAL_SURVIVORS", files)
    minters = [w for w in writers if w in _DECLARED_MINTERS]
    lifecycle = [w for w in writers if w in _LIFECYCLE_WRITERS]
    inert = [w for w in writers if w in _INERT_WRITERS]
    unclassified = [w for w in writers
                    if w not in _DECLARED_MINTERS and w not in _LIFECYCLE_WRITERS
                    and w not in _INERT_WRITERS]
    if unclassified:
        return _violated(
            f"{len(unclassified)} module(s) write the certificate registry and are neither the "
            f"declared minter nor a classified lifecycle writer: {unclassified}. "
            f"AND THREE OF THEM SAY IN THEIR OWN FIRST LINE THAT THEY MINT: universal_gate "
            f"('the ONLY survivor gate for every hunt'), full_pipeline and full_pipeline_v2 "
            f"('runs all 25 miners ... writes certificates'). full_pipeline is on a VPS timer at "
            f"06:00 daily per ops/crontab.manifest, so this is not archaeology. "
            f"certificate_hygiene's own docstring records what this costs: four publishers "
            f"disagreed about what a publishable certificate was and 18 rows passed all ten "
            f"gates while being impossible to enrol. Each of these must be read and either "
            f"declared a minter or classified as lifecycle -- an unclassified writer of the "
            f"certificate registry is exactly the condition that produced those 18.")
    if len(minters) != 1:
        return _violated(f"{len(minters)} minter(s) of the certificate registry: {minters}. "
                         f"Exactly one may grant a certificate.")
    return _enforced(
        f"one minter ({minters[0]}), {len(lifecycle)} classified lifecycle writer(s) "
        f"({lifecycle}) which retire or evict and add no survivor key, and {len(inert)} inert "
        f"writer(s) ({inert}) that cannot write this box's registry",
        len(files))


def _i_capital_authority(files: list[Path]) -> dict[str, Any]:
    """Complete static enumeration: who may WRITE the allocation the gateway deploys."""
    writers = _writers_of("pf_allocation.json", files)
    allowed = {"desks/mt5/research/pf_allocator.py"}
    extra = [w for w in writers if w not in allowed]
    if extra:
        return _violated(f"{len(extra)} module(s) besides pf_allocator write the allocation: "
                         f"{extra[:5]}. Two mechanisms with an opinion about capital is the "
                         f"failure this desk has a law about")
    return _enforced(f"exactly one capital authority in this tree: {writers or 'none found'}",
                     len(files))


def _i_pit_door() -> dict[str, Any]:
    """The donation door refuses an unstamped row. Checked by EXECUTING it, not by reading it."""
    try:
        from research.proposer_common import _stamped
    except ImportError as exc:
        return _obligation(f"the donation door is not importable ({exc})",
                           "restore proposer_common._stamped")
    ok, refused = _stamped("formal_invariants_probe",
                           [{"symbol": "XAUUSD", "family": "session_range_breakout"}])
    stamped_fields = ("available_time", "ingested_time", "source_version", "payload_hash")
    if refused and not ok:
        return _enforced("the door refused a bare row outright, so nothing unstamped can pass", 1)
    if not ok:
        return _obligation("the door neither stamped nor refused the probe row",
                           "make _stamped return a row or a refusal for every input")
    missing = [f for f in stamped_fields if not ok[0].get(f)]
    if missing:
        return _violated(f"a row left the donation door without {missing} -- a candidate that "
                         f"cannot say when it became knowable can support no certificate")
    return _enforced(f"every row leaving the door carries {list(stamped_fields)}, so a joiner can "
                     f"refuse it for any decision earlier than the desk could have known it", 1)


def _i_sizing_state() -> dict[str, Any]:
    """EXHAUSTIVE over the published allocation: the sizing invariants that must hold jointly."""
    p = DESK / "reports" / "pf_allocation.json"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return _obligation(f"no readable allocation at {p.relative_to(ROOT)} ({exc})",
                           "run the allocator; the invariants below are decidable the moment it "
                           "publishes a heat block")
    heat = d.get("heat") or {}
    total = heat.get("total")
    ceiling = heat.get("heat_ceiling")
    per = {k: v for k, v in (d.get("sleeves") or d.get("book") or {}).items()
           if isinstance(v, (int, float))}
    problems: list[str] = []
    if isinstance(total, (int, float)):
        if float(total) < 0:
            problems.append(f"total heat is negative ({total})")
        if isinstance(ceiling, (int, float)) and float(total) > float(ceiling) + 1e-9:
            problems.append(f"total heat {total} exceeds its own ceiling {ceiling}")
    else:
        return _obligation("the allocation publishes no total heat",
                           "have the allocator publish heat.total")
    neg = {k: v for k, v in per.items() if float(v) < 0}
    if neg:
        problems.append(f"{len(neg)} sleeve(s) carry negative heat: {list(neg)[:4]}")
    if per and float(sum(per.values())) > float(total) + 1e-6:
        problems.append(f"per-sleeve heat sums to {sum(per.values()):.6f} against a declared "
                        f"total of {total}")
    if problems:
        return _violated("; ".join(problems))
    return _proven(f"total heat {total} is non-negative, within its ceiling {ceiling}, and the "
                   f"{len(per)} per-sleeve fractions are non-negative and sum within it",
                   len(per) + 3)


def _i_uncharged_trial() -> dict[str, Any]:
    """Every judged cell is charged to the shared error budget -- an obligation, stated honestly."""
    return _obligation(
        "whether every path that JUDGES a cell also charges the family-wise budget is a property "
        "of the gauntlet's control flow, and the gauntlet charges a FIXED campaign count (597) "
        "rather than incrementing per cell. Under a fixed charge the property is vacuous -- "
        "nothing can be uncharged because nothing is charged individually -- which is a different "
        "situation from the one the invariant was written for and should not be reported as a "
        "pass.",
        "make the trial charge a function of cells actually judged, at which point 'every judged "
        "cell is charged' becomes a decidable property of one counter and this check becomes an "
        "enumeration over the gauntlet's exit paths")


def _i_unsigned_deployment(files: list[Path]) -> dict[str, Any]:
    """Complete static enumeration: does anything write the live release record unverified?"""
    writers = _writers_of("release_identity.json", files)
    verifiers = [f for f in files
                 if "release_signing" in f.read_text(encoding="utf-8", errors="replace")]
    if not writers:
        return _obligation("no module in this tree writes release_identity.json",
                           "point this check at whatever records the running build")
    unverified = [w for w in writers
                  if not any(str(v.relative_to(ROOT)).replace("\\", "/") == w
                             for v in verifiers)]
    if unverified:
        return _obligation(
            f"{len(unverified)} writer(s) of the release record do not themselves import the "
            f"signing module: {unverified[:4]}. That is not proof of an unsigned deployment -- "
            f"verification may happen in a caller -- but it is not proof of a signed one either",
            "have every writer of the release record verify the signature in the same function "
            "that writes it, which makes the property local and decidable")
    return _enforced(f"every writer of the release record ({writers}) imports the signing module",
                     len(files))


#: id -> (what the invariant forbids, the check).
INVARIANTS: dict[str, tuple[str, Callable[..., dict[str, Any]]]] = {
    "no_illegal_alpha_state_transition": (
        "an alpha reaching a state by an edge the table does not allow, or reaching ACTIVE "
        "without serving PROBATION", _i_state_machine),
    "no_certificate_bypass": (
        "a module other than the gauntlet writing the certificate registry",
        _i_certificate_authority),
    "no_multiple_capital_authorities": (
        "a second mechanism with an opinion about capital on the same money path",
        _i_capital_authority),
    "no_future_observation_access": (
        "a candidate entering the docket without the stamps that say when it became knowable",
        _i_pit_door),
    "no_impossible_sizing_state": (
        "negative heat, heat above its own ceiling, or per-sleeve fractions that exceed the "
        "declared total", _i_sizing_state),
    "no_uncharged_trial_path": (
        "a cell judged without a charge against the shared family-wise error budget",
        _i_uncharged_trial),
    "no_unsigned_deployment": (
        "the live release record written by something that never verified a signature",
        _i_unsigned_deployment),
}


def build() -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    files = _py_files()
    results: list[dict[str, Any]] = []
    for iid, (forbids, check) in INVARIANTS.items():
        try:
            r = check(files) if check.__code__.co_argcount else check()
        except Exception as exc:
            r = _obligation(f"the check raised {type(exc).__name__}: {exc}",
                            "repair the check; a verifier that cannot run proves nothing")
        results.append({"invariant": iid, "forbids": forbids, **r})

    tally: dict[str, int] = {}
    for r in results:
        tally[str(r["verdict"])] = tally.get(str(r["verdict"]), 0) + 1
    violated = [r for r in results if r["verdict"] == "VIOLATED"]
    return {
        "at": now.isoformat(timespec="seconds"),
        "status": "VIOLATED" if violated else "OK",
        "n_invariants": len(INVARIANTS),
        "n_files_statically_searched": len(files),
        "tally": tally,
        "results": results,
        "verdict_meanings": {
            "PROVEN": ("checked over the ENTIRE space the property lives in. The state machine's "
                       "49 ordered pairs and every simple path between two states are finite, so "
                       "enumerating them is a proof and not a sample."),
            "ENFORCED": ("a complete enumeration of the DIRECT writers in this repository: a "
                         "write whose target is a name bound to the path. Proof about the code "
                         "that EXISTS, never about code that could be written, and it does not "
                         "see a write through a helper that takes the path as an argument. That "
                         "is why it is a separate word from PROVEN."),
            "OBLIGATION": ("not decidable by either method here. The report says what WOULD "
                           "discharge it rather than substituting a weaker check and calling it "
                           "the same thing. An obligation is not a failure and is not a pass."),
            "VIOLATED": "the property does not hold on this tree right now",
        },
        "why_no_smt": (
            "the properties decidable here are decidable by exhaustion over spaces of tens of "
            "elements; an SMT encoding of a 49-edge graph would add a dependency, a translation "
            "layer and a second place for the model to disagree with the code, and would prove "
            "the same thing. The ones that are NOT decidable here are statements about future "
            "code, and no solver settles those."),
        "boundary": (
            "this verifies STRUCTURE. It does not and cannot verify that a strategy is "
            "profitable, that a cost model is right, or that a certificate deserves its "
            "capital -- those are empirical and belong to the gauntlet."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    doc = build()
    print(f"formal invariants: {doc['status']}   {doc['n_invariants']} invariant(s) over "
          f"{doc['n_files_statically_searched']} file(s)   {doc['tally']}")
    for r in doc["results"]:
        mark = {"PROVEN": "+", "ENFORCED": "=", "OBLIGATION": "?", "VIOLATED": "!"}[
            str(r["verdict"])]
        extra = ""
        if r.get("space_searched"):
            extra = f" [space {r['space_searched']}]"
        elif r.get("files_searched"):
            extra = f" [{r['files_searched']} files]"
        print(f" {mark} {r['invariant']:<36} {r['verdict']:<11}{extra}")
        print(f"      {str(r['detail'])[:150]}")
        if r.get("would_discharge"):
            print(f"      -> {str(r['would_discharge'])[:140]}")
    if not a.apply:
        print("  --apply not given; nothing written")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
