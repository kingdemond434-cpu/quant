"""Findings and blocks become work. Nothing rests as "unmeasurable".

WHY THIS EXISTS (principal, 2026-08-30)

    "make sure all of the openrouter recommendations, criticisms etc get implemented daily"
    "unmeasured is a flaw, a data block is a flaw -- it is a law, it should never be there and
     always fixed, no cope, always a way around, 24/7"

Two defects, one shape.

FIRST: `data/deep_audit.json` was read by ZERO scripts. Four lenses of million-token audit ran
every day, found real things, and wrote them to a file nobody opened. The desk's own law calls
this out -- UNWIRED OR IDLE IS A DEFECT (III.16) -- and an audit is the worst place to break it,
because the artifact looks like diligence. Today's run named the exact seven sleeves that were
blocked, and the desk would never have read it.

SECOND: a block was a resting state. `UNAVAILABLE`, `DATA_UNAVAILABLE`, `no adapter registered`,
`BLOCKED_INPUTS_UNAVAILABLE` -- all recorded honestly, all correct, and all permanent. Honest
recording was treated as the end of the work rather than the start of it.

THE TWO LAWS THAT LOOK LIKE THEY CONFLICT, AND DO NOT:

    L1.28a   UNMEASURED is a real answer; absence never resolves to a clean verdict.
    THIS     UNMEASURED is never a resting STATE; it must generate work until it is gone.

The first governs what may be REPORTED, the second what may be LEFT ALONE. A block keeps its
honest label AND gets a route, every cycle, forever. Neither is relaxed to satisfy the other:
the fix for "cannot measure" is never to relabel it measured, it is to find the route.

THE ROUTE LADDER IS THE ENFORCEMENT. Every block kind has an ordered list of ways around, from
cheapest to most expensive. A block that matches NO route is not accepted as unmeasurable -- it
is escalated as UNROUTED at top priority and this script exits non-zero, because "we found no way
around" is a statement about how hard the desk looked, and that is a defect to fix rather than a
fact to file.

CRITICAL THINKING STILL APPLIES. Every finding passes `compile_proposals._roi_refusal` before it
becomes work: a recommendation that regresses a gate, adds a quota, needs paid data or names no
path to geometric growth is refused BY NAME. Automatic execution without that filter is how a
research loop spends its budget implementing its own audit's bad ideas.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
DESK = ROOT / "desks" / "mt5"

AUDIT = ROOT / "data" / "deep_audit.json"
QUEUE = ROOT / "data" / "hypothesis_queue.jsonl"
SYNC = ROOT / "data" / "research_ledger_sync.json"
SHADOW_STATE = DESK / "reports" / "shadow" / "shadow_state.json"
OUT = ROOT / "data" / "findings_docket.json"

#: Lens -> what its findings BECOME. Each lens answers a different question, so routing them all
#: to "a proposal" would file a structural defect as a trading idea and lose it.
_LENS_ACTION: dict[str, str] = {
    "blind_spot": "queue_hypothesis",     # a mechanism nobody named -> a testable candidate
    "survivor_hunt": "unmask_candidate",  # value being wasted -> the cheapest test that settles it
    "weakness": "fix_defect",             # structural -> a desk change, not a trade
    "assumption": "cheap_check",          # load-bearing belief -> a check that could falsify it
}

#: Block kind -> ordered ways around, cheapest first. THIS TABLE IS THE LAW MADE EXECUTABLE: as
#: long as a kind appears here, no instance of it can be left without a next step.
_ROUTES: dict[str, tuple[str, ...]] = {
    "no_adapter": (
        "write an adapter for this mechanism's own observable",
        "probe the free data plane for the observable (scripts/fetch_free_observables.py)",
        "if the family names a RULE rather than a mechanism, reclassify it -- that is a "
        "resolution, not an excuse, and it stops the family claiming mechanism evidence",
    ),
    "measurement_unavailable": (
        "resolve through a different registered adapter for the same mechanism",
        "fetch the missing observable free (CBOE / CFTC / Treasury / Fed all answer without a key)",
        "mutate the observable: breed a child measured attributably (libs/research_os/mutation.py)",
    ),
    "data_unavailable": (
        "probe the free data plane for this exact observable",
        "substitute an ATTRIBUTABLE proxy and label it as one -- never a heuristic in disguise",
        "if genuinely unobtainable, park the candidate against the observable and record the "
        "data need so it revives the moment the data arrives",
    ),
    "forward_blocked": (
        "read last_error and fix the named cause -- most have been import or wiring faults",
        "re-run the forward engine for the affected keys and confirm last_attempt_at advances",
        "if the input is genuinely absent, retire the sleeve by NAME rather than leaving it "
        "blocked, so it stops advertising a clock it is not running",
    ),
}


def _load(p: Path, default: Any = None) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _fid(*parts: str) -> str:
    """Stable id for a finding, so a repeat across days is recognised and not re-queued."""
    return hashlib.blake2b("|".join(parts).encode("utf-8"), digest_size=8).hexdigest()


def _is_echo(a: str, b: str, c: str) -> bool:
    """Reuse the audit's own echo test rather than writing a second, divergent one."""
    try:
        import importlib.util as ilu
        spec = ilu.spec_from_file_location(
            "_deep_audit_echo", Path(__file__).resolve().parent / "run_deep_audit.py")
        if spec is None or spec.loader is None:
            return False
        mod = ilu.module_from_spec(spec)
        sys.modules.setdefault("_deep_audit_echo", mod)
        spec.loader.exec_module(mod)
        return bool(mod._is_echo(a, b, c))
    except Exception:
        return False


def _findings() -> list[dict[str, Any]]:
    blob = _load(AUDIT, {}) or {}
    out = []
    for lens, res in (blob.get("results") or {}).items():
        for f in (res.get("findings") or []):
            a, b, c = str(f.get("a", "")), str(f.get("b", "")), str(f.get("c", ""))
            if not a or not b:
                continue
            # DEFENCE IN DEPTH. The audit's own parser rejects template echoes, but a stale
            # artifact written before that fix still carries them, and a consumer that trusts its
            # input inherits every defect its producer ever had. Re-checking here costs nothing
            # and means a garbage finding cannot become queued work on a replay of old data.
            if _is_echo(a, b, c):
                continue
            out.append({"lens": lens, "action": _LENS_ACTION.get(lens, "review"),
                        "subject": a, "why": b, "do": c,
                        "id": _fid(lens, a), "model": res.get("model", ""),
                        "audit_ran_at": blob.get("ran_at", "")})
    return out


def _blocks() -> list[dict[str, Any]]:
    """Every block the desk is currently carrying, from every source that can hold one."""
    out: list[dict[str, Any]] = []

    sync = _load(SYNC, {}) or {}
    for fam in sync.get("families_without_adapter") or []:
        out.append({"kind": "no_adapter", "subject": str(fam),
                    "detail": "results in this family cannot speak about their own mechanism"})

    state = _load(SHADOW_STATE, {}) or {}
    sleeves = state.get("sleeves") or state
    if isinstance(sleeves, dict):
        for key, v in sleeves.items():
            if not isinstance(v, dict):
                continue
            status = str(v.get("status") or "")
            if status.startswith("BLOCKED"):
                out.append({"kind": "forward_blocked", "subject": str(key),
                            "detail": str(v.get("last_error") or status)[:160],
                            "last_error_at": str(v.get("last_error_at") or "")})

    try:
        from libs.research_os import store
        with store.connect() as conn:
            for mech, n in conn.execute(
                    "SELECT mechanism, COUNT(*) FROM measurements WHERE status='UNAVAILABLE' "
                    "GROUP BY mechanism").fetchall():
                out.append({"kind": "measurement_unavailable", "subject": str(mech),
                            "detail": f"{n} measurement(s) resolved UNAVAILABLE"})
            for obs, n in conn.execute(
                    "SELECT observable, COUNT(*) FROM data_needs GROUP BY observable").fetchall():
                out.append({"kind": "data_unavailable", "subject": str(obs),
                            "detail": f"blocking {n} recorded need(s)"})
    except Exception as exc:
        out.append({"kind": "measurement_unavailable", "subject": "research store unreadable",
                    "detail": f"{type(exc).__name__}: {str(exc)[:90]}"})
    return out


def _queued_names() -> set[str]:
    names = set()
    if QUEUE.exists():
        for line in QUEUE.read_text("utf-8").splitlines():
            try:
                names.add(str(json.loads(line).get("name") or "").upper())
            except json.JSONDecodeError:
                continue
    return names


def main() -> int:
    from compile_proposals import _roi_refusal, _saturation_map

    now = datetime.now(tz=UTC)
    print(f"ACT ON FINDINGS {now.isoformat(timespec='seconds')}")

    findings = _findings()
    blocks = _blocks()
    saturation = _saturation_map()
    already = _queued_names()

    # --- FINDINGS BECOME WORK -------------------------------------------------------------
    queued, refused, docket = [], [], []
    for f in findings:
        text = f"{f['subject']} {f['why']} {f['do']}"
        rec = {"name": f["subject"][:60]}
        ref = _roi_refusal(rec, text, f"{f['lens']}|{f['subject'][:40]}", saturation, set())
        if ref is not None:
            refused.append({**f, "refused_for": ref.get("refused_for"), "why_refused": ref["why"]})
            continue
        if f["action"] == "queue_hypothesis":
            # THE ONE ACTION THAT EXECUTES ITSELF. A blind-spot mechanism becomes a queue record,
            # which compile_proposals turns into docket cells on its next run -- so an audit
            # finding reaches the gauntlet without a human touching it. Every other action names
            # desk work that a person or another job performs, and is listed rather than faked.
            key = f["subject"][:60].upper()
            if key in already:
                docket.append({**f, "status": "already_queued"})
                continue
            with QUEUE.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({
                    "name": f["subject"][:60], "mechanism": f["subject"],
                    "payer": f["why"], "test": f["do"],
                    "data_source": "named by deep audit; capability checked at compile",
                    "lens": f["lens"], "origin": "deep_audit",
                    "queued_at": now.isoformat(timespec="seconds")}) + "\n")
            already.add(key)
            queued.append(f)
        else:
            docket.append({**f, "status": "open"})

    # --- BLOCKS GET ROUTES, ALWAYS ---------------------------------------------------------
    routed, unrouted = [], []
    for b in blocks:
        ways = _ROUTES.get(b["kind"])
        if not ways:
            # NOT ACCEPTED AS UNMEASURABLE. An unknown block kind means the ladder is incomplete,
            # which is a defect in this file -- not a property of the world.
            unrouted.append(b)
            continue
        routed.append({**b, "routes": list(ways), "next": ways[0]})

    print(f"  findings: {len(findings)}  -> {len(queued)} queued as hypotheses, "
          f"{len(docket)} on the docket, {len(refused)} refused by the ROI filter")
    for f in queued:
        print(f"    QUEUED   {f['subject'][:56]}")
    for f in docket[:6]:
        print(f"    {str(f['action']).upper():16s} {f['subject'][:44]}  -> {str(f['do'])[:52]}")
    for f in refused:
        print(f"    REFUSED  {f['subject'][:40]} ({f['refused_for']})")

    print(f"  blocks: {len(blocks)}  -> {len(routed)} routed, {len(unrouted)} UNROUTED")
    by_kind: dict[str, int] = {}
    for b in routed:
        by_kind[b["kind"]] = by_kind.get(b["kind"], 0) + 1
    for kind, n in sorted(by_kind.items()):
        ex = next(b for b in routed if b["kind"] == kind)
        print(f"    {kind:26s} {n:3d}  next: {ex['next'][:64]}")
    for b in unrouted:
        print(f"    UNROUTED {b['kind']}: {b['subject'][:50]} -- no way around is DEFINED, which "
              f"is a gap in the route table, not a property of the world")

    OUT.write_text(json.dumps({
        "ran_at": now.isoformat(timespec="seconds"),
        "findings": len(findings), "queued": queued, "docket": docket, "refused": refused,
        "blocks": len(blocks), "routed": routed, "unrouted": unrouted,
        "law": ("UNMEASURED stays an honest label (L1.28a) and is never a resting state. Every "
                "block carries a route every cycle; an unrouted block is a defect in the route "
                "table, never a verdict that something cannot be measured."),
    }, indent=1, default=str), "utf-8")
    print(f"  -> {OUT}")

    # NON-ZERO ON UNROUTED. The timer surfaces it, so an undefined block kind cannot sit quietly.
    return 1 if unrouted else 0


if __name__ == "__main__":
    raise SystemExit(main())
