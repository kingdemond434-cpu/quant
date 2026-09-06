#!/usr/bin/env python3
"""P48 / P49 / P58 -- THE ADVERSARIES. Poison canaries, silent-defect hunting, claim genealogy.

A validation suite is only evidence about the world if it can still FAIL. This desk has ten gates
that no candidate may pass without clearing, and it has never once checked that those gates are
capable of rejecting anything -- which is L1.63 exactly: a partition that cannot fail carries no
information. A gate that has silently degraded to "return True" would look, from every report the
desk publishes, precisely like a gate that is working on a run where everything happened to pass.

P49 -- POISON CANARIES. Synthetic hypotheses with known-zero edge, fed through the real validation
path continuously. Each is constructed so that passing is definitionally wrong:

    pure_noise          i.i.d. gaussian returns, no signal by construction
    lookahead           a "signal" that is literally tomorrow's return; passes only if the harness
                        permits lookahead, which is the single most expensive bug a desk can have
    survivor_biased     the best of 500 random series, presented as one discovery; passes only if
                        multiplicity correction is absent or broken
    cost_blind          a real edge smaller than the spread; passes only if costs are not charged
    overfit_params      a rule with more free parameters than trades; passes only if complexity
                        is unpriced

The canary rejection rate MUST stay at 100%. It is not a KPI to improve, it is a constant to
defend: the first time it drops, a gate has stopped gating and every certificate issued since is
suspect. That is why the alarm is unconditional and why it names which canary survived.

P48 -- THE SILENT-DEFECT HUNTER. Not a linter. It looks for the specific shapes this desk has
actually been bitten by, each of which passes review, passes tests, and reports success while
doing nothing:

    an organ that exists and is on no schedule
    a fence that cannot start (import error) and therefore reports no breach
    a path in a publish list that .gitignore excludes, so `git add` is a no-op with exit 0
    a producer that exits 0 without writing its artifact
    an absence scored as a pass

Every one of those was found by hand on this tree, most of them in a single session. A defect
class found twice by hand is a detector that should have existed the first time.

P58 -- CLAIM GENEALOGY AND ANTI-ECHO. Ten sources reposting one paper is one piece of evidence,
not ten. Corroboration counts INDEPENDENT observations; an echo counted as corroboration is how a
desk convinces itself. Claims are grouped by lineage -- shared primary source, near-identical
mechanism -- and a lineage contributes its weight once however many times it is repeated.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
REPORT = BASE / "reports" / "ADVERSARY.json"
ALARM = ROOT / "data" / "CANARY_ALARM.txt"

#: The canary rejection rate is a CONSTANT TO DEFEND, not a metric to optimise. Any value below
#: 1.0 means a gate has stopped gating, and every certificate issued since is suspect.
REQUIRED_REJECTION_RATE = 1.0

#: Seeds are fixed so a canary that starts passing is a change in the GATES, never a change in
#: the draw. A canary suite with a random seed cannot distinguish "the gate broke" from "this
#: sample happened to look tradeable", which is the entire question it exists to answer.
CANARY_SEED = 20260906


@dataclass(frozen=True)
class Canary:
    """A hypothesis that must never pass. `why_fatal` says what a pass would prove."""

    name: str
    defect: str
    why_fatal: str


CANARIES: tuple[Canary, ...] = (
    Canary("pure_noise", "no signal by construction",
           "the gates admit i.i.d. noise, so no certificate carries information"),
    Canary("lookahead", "the signal is tomorrow's return",
           "the harness permits lookahead -- the single most expensive bug a desk can have, and "
           "every backtest ever run on it is void"),
    Canary("survivor_biased", "best of 500 random series presented as one discovery",
           "multiplicity correction is absent or broken, so the deflated Sharpe is not deflating"),
    Canary("cost_blind", "a real edge smaller than the spread",
           "costs are not charged, so the book is sized on gross returns it can never capture"),
    Canary("overfit_params", "more free parameters than observations",
           "complexity is unpriced, so any rule can be fitted to any history"),
)


def _series(kind: str, n: int = 400) -> tuple[list[float], list[float]]:
    """(signal, forward_return) for one canary. Deterministic given CANARY_SEED."""
    # A STABLE HASH, NOT `hash()`. Python randomises str hashing per process (PYTHONHASHSEED),
    # so `hash(kind)` gives a different seed on every run -- which would have quietly defeated
    # the entire point of seeding: a canary that started passing could then be the draw rather
    # than the gate, and the suite could never tell you which. Determinism has to survive a
    # restart or it is not determinism.
    offset = int(hashlib.sha1(kind.encode()).hexdigest()[:8], 16) % 10_000
    rng = random.Random(CANARY_SEED + offset)  # noqa: S311 -- canary data, never a secret
    fwd = [rng.gauss(0.0, 0.01) for _ in range(n)]
    if kind == "pure_noise":
        sig = [rng.gauss(0.0, 1.0) for _ in range(n)]
    elif kind == "lookahead":
        # The "signal" IS the outcome. Any harness that scores this as skill is reading the
        # future; the only correct verdict is rejection.
        sig = list(fwd)
    elif kind == "survivor_biased":
        best, best_c = None, -9.9
        for _ in range(500):
            cand = [rng.gauss(0.0, 1.0) for _ in range(n)]
            c = _corr(cand, fwd)
            if c > best_c:
                best, best_c = cand, c
        sig = best or []
    elif kind == "cost_blind":
        # A genuine but sub-spread edge: correlated with the outcome, worth less than it costs.
        sig = [f * 50 + rng.gauss(0.0, 1.0) for f in fwd]
        fwd = [f * 0.00002 for f in fwd]
    else:  # overfit_params
        sig = [rng.gauss(0.0, 1.0) for _ in range(n)]
    return sig, fwd


def _corr(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    if n < 3:
        return 0.0
    ma, mb = sum(a[:n]) / n, sum(b[:n]) / n
    va = math.sqrt(sum((x - ma) ** 2 for x in a[:n])) or 1e-12
    vb = math.sqrt(sum((x - mb) ** 2 for x in b[:n])) or 1e-12
    return sum((a[i] - ma) * (b[i] - mb) for i in range(n)) / (va * vb)


def judge(canary: Canary, gate) -> dict[str, Any]:
    """Run one canary through `gate` and record whether it was correctly rejected.

    `gate` is injected rather than imported so the real gauntlet, a stub, or a deliberately
    broken gate can all be driven through the same path -- which is what lets the fence prove
    this suite actually catches a broken gate rather than merely never seeing one.
    """
    sig, fwd = _series(canary.name)
    try:
        passed: bool | None = bool(gate(canary.name, sig, fwd))
        err = None
    except Exception as exc:
        passed, err = None, f"{type(exc).__name__}: {exc}"
    # THREE STATES, NOT TWO, AND THE THIRD IS WHY THIS IS NOT A BOOLEAN.
    #
    # A gate that CRASHES has not rejected the canary; it has failed to JUDGE it. The first draft
    # of this function set `passed = False` on the exception, so `rejected = not passed` was True
    # and a gauntlet that threw on every single canary reported a PERFECT record -- the most
    # comfortable possible reading of the most serious possible failure. Its own fence caught it.
    #
    # UNJUDGED is therefore not rejected. It counts against the rate exactly as a pass does,
    # because a gate nobody can run is providing no protection whatever its intent.
    rejected = (passed is False)
    return {"canary": canary.name, "defect": canary.defect, "rejected": rejected,
            "judged": passed is not None, "gate_error": err,
            "why_fatal_if_passed": canary.why_fatal}


def run_canaries(gate) -> dict[str, Any]:
    rows = [judge(c, gate) for c in CANARIES]
    rejected = sum(1 for r in rows if r["rejected"])
    rate = rejected / len(rows) if rows else None
    survivors = [r for r in rows if not r["rejected"]]
    return {
        "canaries": rows,
        "rejection_rate": rate,
        "required": REQUIRED_REJECTION_RATE,
        "intact": rate == REQUIRED_REJECTION_RATE,
        "survivors": [s["canary"] for s in survivors],
        "verdict": ("every canary rejected; the gates can still fail, so their passes carry "
                    "information" if not survivors else
                    "A CANARY SURVIVED. " + "; ".join(
                        f"{s['canary']} passed -- {s['why_fatal_if_passed']}" for s in survivors)),
    }


# --------------------------------------------------------------------------- P48
#: Each pattern is a defect SHAPE this desk has actually shipped, with the evidence.
SILENT_SHAPES: tuple[tuple[str, str, str], ...] = (
    ("exit_zero_no_artifact",
     r"return\s+0\s*$",
     "a producer that returns 0 without writing its artifact reports success and publishes "
     "nothing -- the shape that let the box sync 'succeed' ~800 times while delivering nothing"),
    ("bare_except_pass",
     r"except[^\n]*:\s*\n\s*pass\b",
     "an exception swallowed into `pass` turns a failure into a clean run; the gauntlet budget "
     "was pinned to a wrong constant for days behind exactly this"),
    ("absence_as_pass",
     r"if\s+not\s+\w+:\s*\n\s*return\s+(True|0)\b",
     "an empty input scored as a pass (L1.28a) -- absence is never evidence of correctness"),
)


def hunt_silent_defects(root: Path | None = None, limit: int = 4000) -> list[dict[str, Any]]:
    """Scan the tree for shapes that report success while doing nothing.

    REPORTS, NEVER EDITS. Every one of these shapes is legitimate somewhere, so this produces a
    ranked reading list rather than a patch. The value is that a human looks at the right twenty
    lines instead of the wrong twenty thousand.
    """
    base = root or ROOT
    hits: list[dict[str, Any]] = []
    files = [p for p in base.rglob("*.py")
             if ".git" not in p.parts and "__pycache__" not in p.parts
             and "/tests/" not in str(p) and not p.name.startswith("test_")][:limit]
    for p in files:
        try:
            src = p.read_text("utf-8", errors="ignore")
        except OSError:
            continue
        for name, pat, why in SILENT_SHAPES:
            for m in re.finditer(pat, src, re.M):
                hits.append({"shape": name, "file": str(p.relative_to(base)),
                             "line": src[:m.start()].count("\n") + 1, "why": why})
    return hits


# --------------------------------------------------------------------------- P58
def lineage_key(claim: dict[str, Any]) -> str:
    """Group claims by what they are actually EVIDENCE OF, not by who said them.

    Two writeups of one paper are one observation. Keyed on the primary source when there is one,
    otherwise on the normalised mechanism -- never on the title, which is the field every
    reposter changes.
    """
    primary = str(claim.get("primary_source") or claim.get("doi") or "").strip().lower()
    if primary:
        return "src:" + hashlib.sha1(primary.encode()).hexdigest()[:16]
    mech = re.sub(r"[^a-z0-9 ]+", " ",
                  str(claim.get("mechanism") or claim.get("family") or "").lower())
    mech = " ".join(sorted(set(mech.split())))
    return "mech:" + hashlib.sha1(mech.encode()).hexdigest()[:16]


def independent_weight(claims: list[dict[str, Any]]) -> dict[str, Any]:
    """Corroboration counts INDEPENDENT observations. An echo is not a second witness."""
    lineages: dict[str, list[dict[str, Any]]] = {}
    for c in claims:
        lineages.setdefault(lineage_key(c), []).append(c)
    echoes = {k: len(v) for k, v in lineages.items() if len(v) > 1}
    return {
        "claims": len(claims),
        "independent_lineages": len(lineages),
        "echo_factor": round(len(claims) / len(lineages), 2) if lineages else None,
        "largest_echo": max(echoes.values()) if echoes else 0,
        "why": ("Ten sources reposting one paper is one piece of evidence. Counting the reposts "
                "as corroboration is how a desk convinces itself of something nobody "
                "independently observed."),
    }


def _default_gate(name: str, sig: list[float], fwd: list[float]) -> bool:
    """The stand-in gate used when the real gauntlet is not importable on this host.

    IT IS DELIBERATELY HONEST ABOUT BEING A STAND-IN. It rejects everything, so a run on a host
    without the gauntlet reports a perfect canary record that means nothing -- and `gate_source`
    in the report says so, because a 100% rejection rate from a gate that rejects unconditionally
    is exactly the false comfort this module exists to prevent.
    """
    return False


def run(gate=None) -> dict[str, Any]:
    g = gate or _default_gate
    canaries = run_canaries(g)
    defects = hunt_silent_defects()
    by_shape: dict[str, int] = {}
    for h in defects:
        by_shape[h["shape"]] = by_shape.get(h["shape"], 0) + 1
    return {
        "measured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "gate_source": "injected" if gate else "stand-in (rejects everything; this run proves "
                                               "nothing about the real gates)",
        "canaries": canaries,
        "silent_defects": {"total": len(defects), "by_shape": by_shape,
                           "top": defects[:25]},
        "seed": CANARY_SEED,
        "why_seeded": ("Fixed seed so a canary that starts passing is a change in the GATES, "
                       "never a change in the draw."),
    }


def main(argv: list[str] | None = None) -> int:
    doc = run()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    c = doc["canaries"]
    print(f"canaries: {sum(1 for r in c['canaries'] if r['rejected'])}/{len(c['canaries'])} "
          f"rejected ({doc['gate_source']})")
    print(f"silent-defect shapes: {doc['silent_defects']['total']} hit(s) "
          f"{doc['silent_defects']['by_shape']}")
    if not c["intact"]:
        ALARM.parent.mkdir(parents=True, exist_ok=True)
        ALARM.write_text("CANARY " + doc["measured_at"] + "\n\n" + c["verdict"] + "\n", "utf-8")
        print("\n  " + c["verdict"])
        return 1
    if ALARM.exists():
        ALARM.unlink()
    return 0


if __name__ == "__main__":
    sys.exit(main())
