"""INTERNAL CLAIM RECONCILIATION (L1.61) -- two boards, one fact, and nothing ever held both.

The desk built double-entry reconciliation against the VENUE (``run_venue_reconcile.py``, after a
13-model panel demanded it) and never once built one against ITSELF. Every instrument here is
single-artifact BY CONSTRUCTION: ``path_refs.phantoms`` asks whether a writer exists, ``fresh``
asks whether a file is old, ``input_provenance`` asks whether MY inputs were present,
``denominator``/``attrition`` ask whether I scanned anything. An organ can read its inputs
successfully, compute honestly, publish a well-formed fresh artifact and pass all five while
asserting the exact opposite of what the organ next to it asserts about the same fact.
CONTRADICTION IS NOT A PROPERTY OF ANY SINGLE ARTIFACT. It exists only in the RELATION between
two, and until now nothing on this desk ever held two at once.

THE PROVING INSTANCE WAS LIVE ON THE ONLY PATH TO CAPITAL. ``data/gate0_readiness.json`` names
its own subject -- "S1 entry (Gate 0) -- libs/execution/staging.py:s1_entry_met" -- and
``data/live_guard.json`` evaluates the same five criteria through the same function. FOUR OF THE
FIVE DISAGREED: the board a HUMAN reads reported principal_signoff, keys_present,
connector_verified and symbol_count_4_5 all READY while the executor-side evaluator reported all
four False. Each side read its own source successfully, so no fence could fire.

WHY THE GENERAL VERSION WAS REFUTED, AND THIS ONE IS HAND-REGISTERED. The first design indexed
every leaf key across ``data/**.json``. Measured 2026-08-12: 590 artifacts, 10,003 distinct leaf
names, 4,523 published by >=2 artifacts, 418 in scalar disagreement -- and a random sample of 25
of those disagreements contained ZERO genuine same-meaning contradictions. ``why`` has 78
publishers of free text; ``window_days`` is 1.0 in one artifact and 90 in another and BOTH ARE
CORRECT; ``ready`` is a bool in one and a count in another. A fence emitting 418 findings of
which ~all are noise gets acked into silence, which is exactly how the phantom-paths fence spent
its first months (R0356). THE REGISTRY IS THEREFORE SMALL, HAND-BUILT AND MONEY-PATH ONLY: every
claim is a fact two organs genuinely both assert, and a claim that stops resolving goes
UNRESOLVED rather than quietly dropping out of the denominator.

THE NOISE-KILLER IS THE L1.55 CROSS-REFERENCE. When one side of a contradiction was built from an
ABSENT or DEFAULTED input, that side is labelled FABRICATED and the fence names WHICH SIDE TO
REPAIR. Without it a contradiction is a puzzle; with it, it is a work order.

ANTI-TIMIDITY READING (L1.28): a MEASUREMENT duty and a SCOPE EXPANSION. It lifts nothing, sizes
nothing, promotes nothing, opens no gate and loosens no bar -- it has no vocabulary for changing
any value it reads. Its entire effect is to make "these two boards agree" distinguishable from
"these two boards have never been compared", which were byte-identical on this desk until now.
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent.parent

#: Per-claim verdicts. UNRESOLVED is never folded into a pass (L1.28a): fewer than two sides
#: resolved means the claim was NOT compared, which is a different statement from "they agree".
AGREED = "AGREED"
CONTRADICTED = "CONTRADICTED"
UNRESOLVED = "UNRESOLVED"


@dataclass(frozen=True)
class Resolution:
    """One publisher's answer to one claim.

    ``resolved`` False means this side could not be read at all -- the artifact was missing, the
    key absent, or the status an explicit refusal such as Gate 0's ``BLOCKED-UNKNOWN``. That is
    an honest non-answer and is kept DISTINCT from a False value, because a side that refused to
    answer and a side that answered "no" demand opposite responses.

    ``fabricated`` marks a side whose producer declared (L1.55) that it built this number from an
    ABSENT or DEFAULTED input. The value is still reported -- the point is that a reader can see
    which half of a disagreement is a measurement and which is a default in a measurement's
    clothing.
    """

    value: Any
    resolved: bool
    detail: str
    fabricated: bool = False


@dataclass(frozen=True)
class Publisher:
    """One organ's published answer, and how to extract it from that organ's artifact.

    ``measures`` is a one-line statement of what this organ ACTUALLY computes, taken from reading
    its code rather than from the name it publishes under. It is load-bearing: the first run of
    this fence found two contradictions where both sides were correct and simply answering
    DIFFERENT QUESTIONS under the same name, which demands a different repair from a side that
    read an absent input. Without this field the report cannot tell those apart, and a fence that
    mislabels the repair gets acked into silence.
    """

    organ: str
    artifact: str
    extract: Callable[[Any], Resolution]
    measures: str = ""


@dataclass(frozen=True)
class Claim:
    """A single fact that two or more organs independently publish.

    ``question`` is prose on purpose: a claim whose question cannot be stated in one sentence is
    almost always two different facts sharing a name, which is the collision class that refuted
    the general index.
    """

    name: str
    question: str
    publishers: tuple[Publisher, ...]
    kind: str = "bool"
    tolerance: float = 0.0
    law: str = ""


# --------------------------------------------------------------------------------------------
# extractors -- one per artifact SHAPE, not one per claim
# --------------------------------------------------------------------------------------------

def _gate0_criterion(name: str) -> Callable[[Any], Resolution]:
    """Read one criterion from the Gate-0 readiness board's ``rows[]``."""

    def _x(doc: Any) -> Resolution:
        rows = doc.get("rows") if isinstance(doc, dict) else None
        if not isinstance(rows, list):
            return Resolution(None, False, "no rows[] in artifact")
        for r in rows:
            if isinstance(r, dict) and r.get("criterion") == name:
                st = r.get("status")
                detail = str(r.get("detail", ""))[:90]
                if st == "READY":
                    return Resolution(True, True, f"READY -- {detail}")
                if st == "NOT-READY":
                    return Resolution(False, True, f"NOT-READY -- {detail}")
                # BLOCKED-UNKNOWN is the board's own refusal path. It is NOT a verdict and is
                # never compared as one.
                return Resolution(None, False, f"status={st!r} is a refusal, not a verdict")
        return Resolution(None, False, f"criterion {name!r} absent from rows[]")

    return _x


def _guard_criterion(name: str, *, from_absent_input: bool = False) -> Callable[[Any], Resolution]:
    """Read one criterion out of the live guard's ``stage_gate`` block.

    ``s1_entry_met`` returns its reasoning as a flat ``k=v, k=v`` string, so that string is the
    only published record of what the executor-side evaluator concluded per criterion.

    ``from_absent_input`` is set ONLY for the criteria whose value genuinely derives from an input
    the producer declared missing. The producer's ``measured`` flag is BLOCK-LEVEL and taints all
    five criteria equally, but four of them are computed after -- and therefore override -- the
    absent spread. The first run of this fence inherited that block-level flag and labelled two
    genuine measurements FABRICATED; over-claiming an attribution is the same defect this fence
    exists to catch, one level up, so the taint is now registered per criterion from a read of
    the producer's code.
    """

    def _x(doc: Any) -> Resolution:
        sg = doc.get("stage_gate") if isinstance(doc, dict) else None
        if not isinstance(sg, dict):
            return Resolution(None, False, "no stage_gate block")
        why = sg.get("why")
        if not isinstance(why, str):
            return Resolution(None, False, "stage_gate.why absent or not a string")
        m = re.search(rf"(?:^|[,\s]){re.escape(name)}=(True|False)\b", why)
        if m is None:
            return Resolution(None, False, f"{name} not evaluated in stage_gate.why")
        # L1.55: the producer already publishes whether its inputs were real. A False that came
        # from an absent input is a DEFAULT, not a measurement, and the fence says so rather than
        # making a reader guess which half to repair -- but ONLY for the criteria that actually
        # read that input.
        # The precise absent input is named by the claim's registered `measures`, not by the
        # provenance list: the provenance block is block-level and lists only the file the
        # producer happened to declare, which is not always the input THIS criterion read.
        fab = from_absent_input and sg.get("measured") is False
        note = " (producer declared this block unmeasured)" if fab else ""
        return Resolution(m.group(1) == "True", True,
                          f"stage_gate.why {name}={m.group(1)}{note}", fabricated=fab)

    return _x


def _plain_key(*path: str) -> Callable[[Any], Resolution]:
    """Read a scalar at a fixed key path."""

    def _x(doc: Any) -> Resolution:
        cur: Any = doc
        for k in path:
            if not isinstance(cur, dict) or k not in cur:
                return Resolution(None, False, f"key {'.'.join(path)!r} absent")
            cur = cur[k]
        if isinstance(cur, dict | list):
            return Resolution(None, False, f"key {'.'.join(path)!r} is a container, not a scalar")
        return Resolution(cur, True, f"{'.'.join(path)}={cur!r}")

    return _x


# --------------------------------------------------------------------------------------------
# THE REGISTRY -- hand-built, money-path, every entry verified to resolve against real artifacts
# --------------------------------------------------------------------------------------------

_GATE0 = "data/gate0_readiness.json"
_GUARD = "data/live_guard.json"

#: The five mechanical Gate-0 criteria. Both organs call the SAME function
#: (``libs/execution/staging.py:s1_entry_met``) and build its ``evidence`` dict from DIFFERENT
#: sources, which is precisely the defect no single-artifact instrument can see. Because they
#: feed one function, the gate's own contract requires them to agree; where their ``measures``
#: differ, the CONTRACT is the defect, not either reading.
_S1_CRITERIA: tuple[tuple[str, str, str, str, bool], ...] = (
    # REPAIRED 2026-08-19 (R0536/R0537): the two rows below used to read `from_absent_input=True`
    # because each side built this criterion from its own source and the guard's source did not
    # exist. Both organs now call ONE reader (libs/execution/gate0_evidence.py), so the divergence
    # is closed at the input exactly as this fence prescribed -- REPAIR THE INPUT, NOT THE VERDICT.
    # The registry follows the code and never the other way round: these flags are read from the
    # producer, so leaving them True after the repair would make the fence accuse a measurement.
    ("principal_signoff", "Has the principal recorded Gate-0 consent?",
     "gate0_evidence.principal_signoff -- data/gate0_signoff.json exists "
     "(the file IS the consent; deleting it revokes)",
     "gate0_evidence.principal_signoff -- THE SAME READER (was: "
     "data/stage_state.json['principal_signoff'], a key no code anywhere writes)", False),
    ("capital_fraction_le_010", "Is the configured capital <=10% of desk equity?",
     "cashcarry_config.capital / _desk_equity_usd()",
     "the guard's own computed size_fraction", False),
    ("symbol_count_4_5", "Are 4-5 concurrent carries configured?",
     "gate0_evidence.symbol_count -- cashcarry_config['top']",
     "gate0_evidence.symbol_count -- THE SAME READER (was: only the ramp_state.json evidence "
     "spread, absent, so int(...) defaulted to 0)", False),
    ("keys_present", "Are live-venue credentials present?",
     "credential FILES present in data/secrets/",
     "the venue CONNECTOR OBJECT was constructed (venue is not None)", False),
    ("connector_verified", "Has a real venue round-trip been recorded?",
     "531 fills recorded in the execution tape",
     "a CANARY PROBE succeeded recently (can.last_ok_ts is not None)", False),
)

CLAIMS: tuple[Claim, ...] = (
    *(
        Claim(
            name=f"gate0.{crit}",
            question=q,
            law="L1.6/L1.23 -- Gate 0 is the only path to live capital",
            publishers=(
                Publisher("check_gate0_ready", _GATE0, _gate0_criterion(crit), measures=board),
                Publisher("run_live_guard", _GUARD,
                          _guard_criterion(crit, from_absent_input=absent), measures=guard),
            ),
        )
        for crit, q, board, guard, absent in _S1_CRITERIA
    ),
    Claim(
        name="staging.stage",
        question="Which staged-arming stage is the desk in?",
        kind="string",
        law="L1.23 -- stage governs whether capital may move at all",
        publishers=(
            Publisher("run_live_guard", _GUARD, _plain_key("stage")),
            Publisher("staging._save", "data/stage_state.json", _plain_key("stage")),
        ),
    ),
)


# --------------------------------------------------------------------------------------------
# the engine
# --------------------------------------------------------------------------------------------

@dataclass
class _Load:
    doc: Any = None
    ok: bool = False
    why: str = ""


def _load(root: Path, rel: str) -> _Load:
    p = root / rel
    if not p.exists():
        return _Load(why="ABSENT")
    try:
        return _Load(doc=json.loads(p.read_text()), ok=True)
    except (OSError, ValueError) as exc:  # attrition is COUNTED, never silent (L1.60)
        return _Load(why=f"UNREADABLE: {type(exc).__name__}")


def _agree(values: list[Any], kind: str, tol: float) -> bool:
    first = values[0]
    if kind == "number":
        try:
            nums = [float(v) for v in values]
        except (TypeError, ValueError):
            return False
        return all(abs(n - nums[0]) <= tol for n in nums)
    # A bool claim compared against a non-bool is NOT agreement -- that is the `ready` collision
    # (bool in one artifact, a count in another) and it must never read as a match.
    if kind == "bool" and not all(isinstance(v, bool) for v in values):
        return False
    return all(v == first for v in values)


def reconcile(root: Path | None = None,
              claims: tuple[Claim, ...] | None = None) -> dict[str, Any]:
    """Compare every registered claim across its publishers.

    Returns a report whose ``scanned`` is the number of claims ACTUALLY COMPARED -- never
    ``len(CLAIMS)``, which would be a count of what the author wrote down rather than of what the
    run found (L1.57).
    """
    root = root or _ROOT
    claims = CLAIMS if claims is None else claims
    cache: dict[str, _Load] = {}
    rows: list[dict[str, Any]] = []
    unreadable: dict[str, str] = {}

    for c in claims:
        sides: list[dict[str, Any]] = []
        for pub in c.publishers:
            if pub.artifact not in cache:
                cache[pub.artifact] = _load(root, pub.artifact)
            ld = cache[pub.artifact]
            if not ld.ok:
                unreadable[pub.artifact] = ld.why
                sides.append({"organ": pub.organ, "artifact": pub.artifact, "resolved": False,
                              "value": None, "detail": ld.why, "fabricated": False})
                continue
            try:
                res = pub.extract(ld.doc)
            except (KeyError, TypeError, ValueError, AttributeError) as exc:
                res = Resolution(None, False, f"extractor failed: {type(exc).__name__}")
            sides.append({"organ": pub.organ, "artifact": pub.artifact,
                          "resolved": res.resolved, "value": res.value,
                          "detail": res.detail, "fabricated": res.fabricated,
                          "measures": pub.measures})

        got = [s for s in sides if s["resolved"]]
        if len(got) < 2:
            status = UNRESOLVED
        else:
            status = AGREED if _agree([s["value"] for s in got], c.kind, c.tolerance) \
                else CONTRADICTED

        row: dict[str, Any] = {"claim": c.name, "question": c.question, "status": status,
                               "law": c.law, "sides": sides}
        if status == CONTRADICTED:
            fab = [s for s in got if s["fabricated"]]
            real = [s for s in got if not s["fabricated"]]
            measures = {s["measures"] for s in got if s["measures"]}
            if len(fab) == 1 and real:
                row["kind"] = "FABRICATED-SIDE"
                row["repair"] = (
                    f"{fab[0]['organ']} published {fab[0]['value']!r} from a declared-absent "
                    f"input ({fab[0]['measures']}), while {real[0]['organ']} measured "
                    f"{real[0]['value']!r}. REPAIR THE INPUT, NOT THE VERDICT.")
            elif len(measures) > 1:
                # Both sides measured honestly and got different answers because they are
                # answering different questions. The names feed ONE gate function, so the
                # ambiguous CONTRACT is the defect -- neither reading is wrong on its own terms.
                row["kind"] = "SAME-NAME-DIFFERENT-QUESTION"
                row["repair"] = (
                    "both sides measured honestly and disagree because they measure DIFFERENT "
                    "THINGS under one name: "
                    + " vs ".join(f"{s['organ']} = {s['measures']}" for s in got)
                    + ". Both feed one gate, so the gate's evidence CONTRACT is the defect.")
            else:
                row["kind"] = "GENUINE-DISAGREEMENT"
                row["repair"] = ("both sides claim to be measured over the same question -- the "
                                 "disagreement is real and one of them is wrong")
        rows.append(row)

    n_compared = sum(1 for r in rows if r["status"] in {AGREED, CONTRADICTED})
    n_contra = sum(1 for r in rows if r["status"] == CONTRADICTED)
    n_unres = sum(1 for r in rows if r["status"] == UNRESOLVED)

    if n_compared == 0:
        status = "UNMEASURED"
    elif n_contra:
        status = "CONTRADICTED"
    elif n_unres:
        status = "PARTIAL"
    else:
        status = "OK"

    return {
        "status": status,
        "n_claims_registered": len(claims),
        "n_compared": n_compared,
        "n_contradicted": n_contra,
        "n_unresolved": n_unres,
        "unreadable_artifacts": unreadable,
        "rows": rows,
    }


def summarise(report: dict[str, Any]) -> list[str]:
    """One line per claim that a reader must act on. Agreement is not reported per-row."""
    out: list[str] = []
    for r in report.get("rows", []):
        if r["status"] == AGREED:
            continue
        kind = f"  [{r['kind']}]" if r.get("kind") else ""
        out.append(f"  {r['status']:13s} {r['claim']}{kind}")
        for s in r["sides"]:
            mark = "  " if s["resolved"] else "??"
            fab = " [DEFAULTED]" if s.get("fabricated") else ""
            out.append(f"      {mark} {s['organ']:20s} {s['detail']}{fab}")
        if r.get("repair"):
            out.append(f"      -> {r['repair']}")
    return out


__all__ = [
    "AGREED",
    "CLAIMS",
    "CONTRADICTED",
    "UNRESOLVED",
    "Claim",
    "Publisher",
    "Resolution",
    "reconcile",
    "summarise",
]
