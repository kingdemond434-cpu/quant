#!/usr/bin/env python3
"""IMMUTABLE EVALUATOR (portable fence) -- research agents may not modify the test they failed.

autoresearch-trading's split, made a law here: the files that JUDGE a hypothesis -- the
gauntlet, the multiplicity charge, the cost engine, the lockbox access, the promotion law, the
heat law and the growth governance fences -- are hashed into `data/IMMUTABLE_MANIFEST.json`.
Any change to one of them must arrive with a re-signed manifest (a human commit that runs
`--sign`), otherwise the gate is red. An organ that dislikes a verdict can change the
hypothesis; it cannot change the judge.

    python scripts/check_immutable_evaluator.py          # verify (rc=1 on drift)
    python scripts/check_immutable_evaluator.py --sign   # re-sign after a deliberate change

The MUTABLE side -- hypotheses, strategies, models, factors, proposers -- is everything else.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "desks" / "mt5" / "data" / "IMMUTABLE_MANIFEST.json"

IMMUTABLE: tuple[str, ...] = (
    "desks/mt5/scripts/external_gauntlet.py",
    "desks/mt5/research/universal_gate.py",
    "desks/mt5/research/multiplicity.py",
    "desks/mt5/research/gate_policy.py",
    "desks/mt5/research/heat_policy.py",
    "desks/mt5/research/promoter.py",
    "desks/mt5/mt5desk/gateway_config_fallback.py",
    "libs/portfolio/allocator_proof.py",
    "libs/portfolio/rails.py",
    "libs/portfolio/capital_modifiers.py",
    "libs/validation/redteam.py",
    "libs/validation/replay2.py",
    "libs/validation/calibration.py",
    "libs/regime/state_admission.py",
    "scripts/check_growth_governance.py",
    "scripts/check_heat_floor_wiring.py",
    "scripts/check_immutable_evaluator.py",
    "scripts/run_deadman_switch.py",
)


def _hashes() -> dict[str, str]:
    """SHA-256 of each guarded file, over LINE-ENDING-NORMALISED bytes.

    WHY NORMALISED, measured 2026-09-12 on the Windows trading box. A signature is a claim about
    CONTENT. Hashing raw bytes made it a claim about content AND about how the checkout happened
    to write newlines, and those two came apart:

        working tree  desks/mt5/research/promoter.py  ->  766a1119abcd663a   (CRLF)
        HEAD blob     desks/mt5/research/promoter.py  ->  8e1f39e3f4a6905f   (LF)

    Identical code, byte-different files. `run_law_gate` judges HEAD in a DETACHED WORKTREE
    whenever the tree is dirty -- and this box's tree is permanently dirty, because live state
    files (gateway_state.json and friends) are tracked and rewritten every pass. So the fence
    always hashed the LF checkout while `--sign` always hashed the CRLF working copy, and the two
    could never agree. The fence reported a BREACH on a file nobody had touched, on every run, and
    since a failing law fence refuses the push, the trading box could not reach origin at all.

    That is the worst shape a constitutional fence can take: permanently red, red about nothing,
    and blocking. A fence that cannot be satisfied by correct code stops being read as evidence
    and starts being read as an obstacle -- and then the day it fires on a REAL tamper, it looks
    exactly like the eleven days it fired on newlines.

    Normalising CRLF -> LF makes the hash mean what it always claimed to mean. It does not weaken
    the guard: any change to a byte that is not a carriage return still changes the digest, so
    every tamper this caught before it still catches.
    """
    out = {}
    for rel in IMMUTABLE:
        p = ROOT / rel
        if not p.exists():
            out[rel] = "<absent>"
            continue
        raw = p.read_bytes().replace(b"\r\n", b"\n")
        out[rel] = hashlib.sha256(raw).hexdigest()[:16]
    return out


def sign(by: str) -> dict[str, object]:
    doc = {"signed_utc": datetime.now(tz=UTC).isoformat(), "signed_by": by,
           "files": _hashes(),
           "rule": ("these files judge hypotheses; a change must arrive with a re-signed "
                    "manifest -- research organs may change the hypothesis, never the judge")}
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(doc, indent=1), "utf-8")
    return doc


def check() -> list[dict[str, str]]:
    try:
        rec = json.loads(MANIFEST.read_text("utf-8")).get("files") or {}
    except (OSError, ValueError):
        return [{"file": str(MANIFEST), "why": "no IMMUTABLE_MANIFEST.json; run --sign once"}]
    now = _hashes()
    out = []
    for rel, h in now.items():
        if rel not in rec:
            out.append({"file": rel, "why": "immutable file not in the signed manifest"})
        elif rec[rel] != h:
            out.append({"file": rel, "why": f"changed since signing ({rec[rel]} -> {h})"})
    for rel in rec:
        if rel not in now:
            out.append({"file": rel, "why": "in the manifest but no longer declared immutable"})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sign", action="store_true")
    ap.add_argument("--by", default="principal")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.sign:
        d = sign(a.by)
        print(f"immutable manifest signed by {a.by}: {len(d['files'])} files")  # type: ignore[arg-type]
        return 0
    findings = check()
    if a.json:
        print(json.dumps({"ok": not findings, "findings": findings}, indent=1))
    else:
        print(f"immutable evaluator: {'OK' if not findings else f'{len(findings)} breach(es)'}")
        for f in findings:
            print(f"  BREACH {f['file']}: {f['why']}")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
