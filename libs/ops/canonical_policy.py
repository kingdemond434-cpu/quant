"""CANONICAL POLICY RESOLUTION -- the mandate's own II-B/II-D, made mechanical.

WHY THIS EXISTS. The PRE-DEEPSEEK master mandate (docs/policy/PRE_DEEPSEEK_MASTER_MANDATE.md)
rules that a policy is NOT authoritative until persisted, hashed and version-controlled, and that
every agent resolves the same (version, hash) or the mismatch FAILS VISIBLE. Persisting the file
satisfies none of that on its own -- II-H: markdown alone is not implementation. This module is
the LOAD half: one function every agent calls, one verdict shape, and a hash comparison that
cannot be satisfied by a stale copy.

WHAT IT DELIBERATELY IS NOT. Not a second policy authority (the mandate forbids one): it holds no
policy content, only the mechanics of reading the state record and checking the bytes on disk
against it. Not a prompt injector: II-F rules the mandate is never pasted into inference calls,
so `resolve()` returns metadata -- version, hash, verdict -- and the caller loads sections of the
file on demand if it needs the text.

THE FAIL-VISIBLE CONTRACT. Three verdicts, and only one is a pass:
    RESOLVED       -- state record read, policy file present, hash matches byte-for-byte.
    HASH_MISMATCH  -- the file was edited without regenerating the state record (II-D names this
                      exact class). The policy on disk is UNVERIFIED and consequential work must
                      not proceed on it.
    MISSING_POLICY -- state record or policy file absent/unreadable. UNKNOWN, never a pass.
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

__all__ = ["POLICY_STATE", "policy_duty", "resolve"]

_ROOT = Path(__file__).resolve().parents[2]
POLICY_STATE = "docs/policy/POLICY_STATE.json"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve(root: Path | None = None) -> dict[str, Any]:
    """Resolve canonical policy state. Never raises -- a resolver that dies reads as silence, and
    silence is the failure mode II-D exists to prevent. The verdict carries the failure instead."""
    base = root or _ROOT
    out: dict[str, Any] = {
        "resolved_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "verdict": "MISSING_POLICY",
    }
    try:
        state = json.loads((base / POLICY_STATE).read_text("utf-8"))
    except (OSError, ValueError) as exc:
        out["why"] = f"policy state unreadable: {type(exc).__name__}: {str(exc)[:120]}"
        return out

    out["canonical_policy_version"] = state.get("canonical_policy_version")

    # MULTI-POLICY STATE (2026-08-11): the DeepSeek second-flywheel mandate landed as a second
    # canonical file, so the state record now carries a `policies` list and the verdict is the
    # CONJUNCTION -- one stale mandate poisons the whole resolution, because an agent that reads
    # "RESOLVED" must be entitled to trust every mandate it will consult, not just the first.
    # The legacy single-file fields are kept as a fallback so an older state record still
    # resolves; both shapes go through the same hash comparison.
    entries = state.get("policies")
    if not isinstance(entries, list) or not entries:
        entries = [{"policy_file": state.get("policy_file"),
                    "policy_hash": state.get("canonical_policy_hash")}]

    checked: list[dict[str, Any]] = []
    failures: list[str] = []
    for e in entries:
        rel = str((e or {}).get("policy_file", ""))
        declared = str((e or {}).get("policy_hash", "")).removeprefix("sha256:")
        row: dict[str, Any] = {"policy_file": rel}
        try:
            actual = _sha256(base / rel)
        except OSError as exc:
            row["verdict"] = "MISSING_POLICY"
            failures.append(f"{rel}: unreadable ({type(exc).__name__}: {str(exc)[:80]})")
            checked.append(row)
            continue
        row["policy_hash"] = f"sha256:{actual}"
        if actual == declared and declared:
            row["verdict"] = "RESOLVED"
        else:
            row["verdict"] = "HASH_MISMATCH"
            failures.append(f"{rel}: declared={declared[:16]}... actual={actual[:16]}...")
        checked.append(row)
    out["policies"] = checked
    out["policy_file"] = checked[0].get("policy_file")
    out["canonical_policy_hash"] = checked[0].get("policy_hash")

    if not failures:
        out["verdict"] = "RESOLVED"
    elif any(r["verdict"] == "HASH_MISMATCH" for r in checked):
        out["verdict"] = "HASH_MISMATCH"
        out["why"] = (
            "a policy file on disk does not match the recorded hash -- it was edited without "
            "regenerating POLICY_STATE.json in the same commit, or the state record is stale: "
            + "; ".join(failures)[:300]
            + ". The policy is UNVERIFIED and consequential work must not proceed on it "
            "(mandate II-D: FAIL VISIBLE)")
    else:
        out["verdict"] = "MISSING_POLICY"
        out["why"] = "policy file unreadable: " + "; ".join(failures)[:300]
    return out


def policy_duty(root: Path | None = None) -> str:
    """The injectable block for organ spawn -- II-B/II-C made to actually reach every organ.

    THE GAP THIS CLOSES (R0438, 2026-08-13). resolve() implements the mandate's fail-visible
    contract correctly and is called by libs.ops.deepseek_cycle.policy_gate() -- but that call
    only reaches the DeepSeek cycle specifically. II-B requires EVERY agent to resolve canonical
    policy before consequential work, and grep for "canonical_policy" across ops/brain_env.sh --
    the one file every organ of any kind sources -- returned zero hits. The hard requirement was
    real, tested, and reached exactly one caller out of dozens of organs.

    MIRRORS libs.ops.repair_mode's injection exactly, because that module already solved the
    identical shape of problem (a remedy legislated, fenced, and never wired to reach an organ)
    for the conversion backlog, and libs.research.edge_intake's next_batch() duty (R0437) is the
    same fix again for a third law. Same fix, same reason each time (L1.36): a duty that never
    reaches an organ cannot change behaviour however well it is fenced.

    PAGES, NEVER KILLS -- deliberately non-blocking here, matching libs.ops.lawful.guard()'s own
    established split for organ-spawn-time governance checks (guard() vs guard(strict=True) for
    the money path only): "a governance fault must not silently stop the desk's research or its
    collectors... that trades a real outage for a paperwork fault, and the outage is the larger
    loss." A stale policy hash is exactly a governance fault, not a reason to stop every collector
    and screen on the desk; it is a loud, dated, unmissable line every organ now carries, and the
    caller decides what to do about it. The money path already has its own strict gate elsewhere
    (deepseek_cycle.policy_gate(), ok=False on anything but RESOLVED) and this does not weaken it.

    STEADY (empty string) on RESOLVED -- adds a duty, removes none.
    """
    res = resolve(root)
    verdict = str(res.get("verdict", "MISSING_POLICY"))
    if verdict == "RESOLVED":
        return ""
    if verdict == "HASH_MISMATCH":
        bad = "; ".join(
            f"{r.get('policy_file')}" for r in (res.get("policies") or [])
            if r.get("verdict") == "HASH_MISMATCH"
        ) or res.get("policy_file", "?")
        return (
            f"[II-D] CANONICAL POLICY HASH MISMATCH -- {bad} does not match "
            f"{POLICY_STATE}'s recorded hash. The policy on disk is UNVERIFIED: it was edited "
            f"without regenerating the state record, or the record is stale.\n"
            f"  Do not treat this file's contents as canonical until resolved. Regenerate "
            f"{POLICY_STATE}'s hash for the changed file(s) in the SAME commit as the edit, "
            f"or revert the edit.")
    return (
        f"[II-B] CANONICAL POLICY UNRESOLVED -- {res.get('why', verdict)}\n"
        f"  {POLICY_STATE} or a policy file it names is missing/unreadable. UNKNOWN is not a "
        f"pass (mandate II-D): treat consequential work this window as running under unverified "
        f"rules until this resolves.")


def main() -> int:
    """Print the injectable duty block. Exit 0 always -- a prompt producer, not a gate.

    Wired into ops/brain_env.sh's _DOCTRINE exactly like libs.ops.repair_mode and
    libs.research.edge_intake (L1.37: PAGES, never KILLS).
    """
    from libs.ops.lawful import guard as _law_guard  # L1.42: no act exempt

    _law_guard()
    print(policy_duty(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
