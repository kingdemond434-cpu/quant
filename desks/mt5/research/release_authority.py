"""B1 -- THE ONE BIT: may THIS code create new exposure?

THE BLUEPRINT ITEM: "canonical release / capital authority: one bit answering 'may this code
create new exposure'". Three organs each held a PIECE of the answer and none of them held the
answer: `libs/ops/release.py` seals a commit, `scripts/gate_attestation.py` records whether the
gates passed, and `mt5desk/release_identity.py` checks at runtime whether the running tree drifted
from the seal. The bit itself -- sealed AND tested AND undrifted -- was never computed anywhere,
so `tested_sha` read UNMEASURED on the box for weeks while the gates were green.

WHY THE CODE TREE AND NOT THE COMMIT. This box commits its own ledgers, reports and logs on top
of the code it is running, so HEAD moves every few minutes without a line of code changing.
Measured 2026-09-23: the attestation named 16eca3ca, the gateway ran b794c18a, the seal named
1eba9793 -- three different commits, ONE code tree. A bit defined on commit equality is therefore
false whenever the desk is doing its job, which is the definition of a check nobody can use.
`scripts/gate_attestation.code_hash` hashes every tracked non-state blob at a ref, so two commits
that differ only in state carry the same hash and the bit fails exactly when code moves.

WHAT IT DOES NOT DO, DELIBERATELY. It does not gate the gateway, refuse a seal, or narrow the
book. A bit that halted new risk whenever a gate was slow, red on an unrelated lint, or simply
not yet run would reduce the desk's aggressiveness by fiat -- forbidden by the principal's
standing order (2026-09-08) and by GROWTH_GOVERNANCE Rule 1, which asks any risk reduction to
prove it raises robust forward E[log W] first. So the bit is MEASURED AND PUBLISHED, next to the
evidence for each of its three clauses, and `scripts/check_closed_loop.py` reads it. Turning it
into a veto is a principal decision, not a session's.

    python desks/mt5/research/release_authority.py [--once] [--budget-s N]
        -> desks/mt5/reports/RELEASE_AUTHORITY.json
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
OUT = DESK / "reports" / "RELEASE_AUTHORITY.json"
ATTESTATION = ROOT / "data" / "gate_attestation.json"
IDENTITY = DESK / "data" / "release_identity.json"
RELEASE = DESK / "data" / "RELEASE.json"

#: An attestation older than this describes a gate run whose subject may no longer be the tree in
#: front of us even when the hash matches by luck; it is reported with its age, never hidden.
MAX_ATTESTATION_AGE_H = 26.0


def _read(p: Path) -> dict[str, Any]:
    try:
        doc = json.loads(p.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _git(*args: str) -> str:
    try:
        r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=60, check=False)
    except (OSError, subprocess.SubprocessError):
        return ""
    return r.stdout.rstrip("\n") if r.returncode == 0 else ""


def _code_hash(ref: str) -> str:
    """The code-tree hash of `ref`, through the attestation's own definition so the two can
    never drift apart. A missing script or an unknown ref reads as "" -- UNMEASURED."""
    if not ref:
        return ""
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        from gate_attestation import code_hash  # type: ignore[import-not-found]
    except Exception:
        return ""
    try:
        return str(code_hash(ref) or "")
    except Exception:
        return ""


def _age_h(p: Path, now: datetime) -> float | None:
    try:
        return (now.timestamp() - p.stat().st_mtime) / 3600.0
    except OSError:
        return None


def measure(now: datetime | None = None) -> dict[str, Any]:
    """The bit and every clause behind it. Pure over the artifacts; never raises."""
    now = now or datetime.now(tz=UTC)
    att, ident, rel = _read(ATTESTATION), _read(IDENTITY), _read(RELEASE)

    running_sha = str(ident.get("running_sha") or "") or _git("rev-parse", "HEAD")
    sealed_sha = str(rel.get("code_sha") or rel.get("sha") or "")
    running_code = _code_hash(running_sha or "HEAD")
    sealed_code = _code_hash(sealed_sha)
    tested_code = str(att.get("tested_code_hash") or "")
    tested_sha = str(att.get("tested_sha") or "")
    att_age = _age_h(ATTESTATION, now)

    # CLAUSE 1 -- TESTED. The gates passed on THIS code tree. An attestation that predates the
    # code_hash field carries none, and falls back to the commit it named: measured, weaker, and
    # labelled, because a silent fallback is how UNMEASURED becomes a pass.
    if att.get("result") != "pass":
        tested, tested_why = False, (f"gate attestation result={att.get('result') or 'absent'}"
                                     + (f" on {tested_sha[:12]}" if tested_sha else ""))
    elif tested_code and running_code:
        tested = tested_code == running_code
        tested_why = ("the gates passed on this exact code tree "
                      f"({tested_code[:12]})" if tested else
                      f"the gates passed on code tree {tested_code[:12]}, this tree is "
                      f"{running_code[:12]}")
    elif tested_sha and running_sha:
        tested = tested_sha == running_sha
        tested_why = (f"attestation carries no code hash; commit match={tested} "
                      f"({tested_sha[:12]} vs {running_sha[:12]})")
    else:
        tested, tested_why = False, "no attestation and no running sha: UNMEASURED"
    if tested and att_age is not None and att_age > MAX_ATTESTATION_AGE_H:
        tested_why += f"; attestation is {att_age:.1f}h old"

    # CLAUSE 2 -- SEALED. A seal exists and names the same code tree the box is running. State
    # commits ride on top of a seal by design, so the comparison is on code, never on commits.
    if not sealed_sha:
        sealed, sealed_why = False, "no RELEASE.json: nothing is sealed on this box"
    elif sealed_code and running_code:
        sealed = sealed_code == running_code
        sealed_why = (f"the sealed commit {sealed_sha[:12]} carries this code tree"
                      if sealed else
                      f"the sealed commit {sealed_sha[:12]} carries code tree "
                      f"{sealed_code[:12]}; this tree is {running_code[:12]}")
    else:
        sealed, sealed_why = False, f"code tree of {sealed_sha[:12]} unreadable: UNMEASURED"

    # CLAUSE 3 -- UNDRIFTED. The runtime check the desk already runs: did the money path change
    # on disk since the seal? `release_identity` owns this and its verdict is read, not redone.
    verdict = str(ident.get("verdict") or ("OK" if ident.get("ok") else "")).upper()
    undrifted = verdict == "OK"
    undrifted_why = (f"release_identity verdict={verdict or 'ABSENT'}"
                     + (f": {str(ident.get('reason'))[:180]}" if not undrifted and
                        ident.get("reason") else ""))

    bit = bool(tested and sealed and undrifted)
    return {
        "at": now.isoformat(timespec="seconds"),
        "may_create_exposure": bit,
        "clauses": {
            "tested": {"ok": tested, "why": tested_why, "attestation_age_h": att_age,
                       "tested_sha": tested_sha or None, "tested_code_hash": tested_code or None,
                       "gates": att.get("gates")},
            "sealed": {"ok": sealed, "why": sealed_why, "sealed_sha": sealed_sha or None,
                       "sealed_code_hash": sealed_code or None},
            "undrifted": {"ok": undrifted, "why": undrifted_why, "verdict": verdict or None},
        },
        "running_sha": running_sha or None,
        "running_code_hash": running_code or None,
        "why": ("sealed, tested green on this code tree, and undrifted" if bit else
                "; ".join(w for ok, w in ((tested, tested_why), (sealed, sealed_why),
                                          (undrifted, undrifted_why)) if not ok)),
        "authority": ("PUBLISHED, NOT ENFORCED. This bit gates nothing: a release check that "
                      "halted new risk on a slow or red gate would reduce the book by fiat, "
                      "which the principal's standing order (2026-09-08) and GROWTH_GOVERNANCE "
                      "Rule 1 both forbid without a proof that E[log W] rises. The gateway's own "
                      "release gate is unchanged; consumers read this bit as evidence."),
        "consumers": ["scripts/check_closed_loop.py::release_authority",
                      "desks/mt5/scripts/Adopt-And-Seal.ps1 (logged at seal time)"],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true", help="one pass (the only mode)")
    ap.add_argument("--budget-s", type=float, default=60.0,
                    help="advisory; the pass reads four artifacts and two git trees")
    ap.parse_args(argv)
    doc = measure()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    print(f"release authority: may_create_exposure={doc['may_create_exposure']} -- {doc['why']}")
    for name, c in doc["clauses"].items():
        print(f"  {name:<10} {c['ok']!s:<5} {str(c['why'])[:140]}")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
