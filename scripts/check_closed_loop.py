"""The closed-loop attestation: is the desk's compute / information / capital loop closed?

THE ARTIFACT IS GENERATED FROM EVIDENCE, NEVER SET BY HAND (principal's blueprint, item 28). Each
boolean below is derived from an artifact another organ writes; a boolean whose artifact does not
exist, or does not carry the field, is `null` with the reason -- UNMEASURED, which is a verdict
(L1.28a) and never a pass. `complete` is true only when every boolean is true, so the desk cannot
declare itself closed by omission. Written hourly to
`desks/mt5/data/architecture/closed_loop_attestation.json` (leg `closed_loop`); exit 0 always --
this is a report, and a report that stops the cycle would be worse than an open loop.

What each block reads:
  release_authority  release_identity.json (running vs tested sha, verdict), data/RELEASE.json
                     (sealed sha), reports/ALLOCATOR_PROOF.json (passed, age), the fast-gate
                     attestation (green on the running sha)
  truth              PIT census (scripts/check_pit.py artifact), candidate conservation
  forward            shadow_health.json (silent / churned clocks), forward reconciliation
  research           whether the frontier and EVIG organs are AUTHORITATIVE (they schedule
                     compute) or advisory (they write reports) -- read from their own artifacts
  meta               the controller's last completed epoch and whether each budget moved
                     because of an outcome (generator weights, research bandit, allocator proof)
"""
from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
OUT = DESK / "data" / "architecture" / "closed_loop_attestation.json"
FRESH_S = 26 * 3600


def _read(p: Path) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _age_s(p: Path) -> float | None:
    try:
        return time.time() - p.stat().st_mtime
    except OSError:
        return None


def _first_existing(*paths: Path) -> Path | None:
    for p in paths:
        if p.exists():
            return p
    return None


def release_authority() -> dict[str, Any]:
    out: dict[str, Any] = {}
    ident = _read(DESK / "data" / "release_identity.json") or {}
    running = str(ident.get("running_sha") or "")
    tested = str(ident.get("tested_sha") or "")
    out["running_sha_matches"] = (str(ident.get("verdict")) == "OK") if ident else None
    out["tested_sha_matches"] = (bool(running) and tested == running) if ident else None
    # A FRESH GATE ATTESTATION ON THE RUNNING SHA IS THE TESTED SHA (scripts/gate_attestation.py
    # writes it after the gates ran green on the box's own HEAD). The seal itself is written
    # unattended without the suite; the attestation is the measurement the seal lacks.
    if ident and running and not out["tested_sha_matches"]:
        ga = _first_existing(ROOT / "data" / "gate_attestation.json",
                             DESK / "data" / "gate_attestation.json")
        gdoc = _read(ga) if ga else None
        if isinstance(gdoc, dict):
            gsha = str(gdoc.get("sha") or gdoc.get("tested_sha") or gdoc.get("head") or "")
            gres = str(gdoc.get("result") or gdoc.get("verdict") or gdoc.get("status") or "").lower()
            gage = _age_s(ga) if ga else None
            if gsha == running and gres in ("pass", "green", "ok") and gage is not None and gage < FRESH_S:
                out["tested_sha_matches"] = True
                out["tested_sha_why"] = f"gate attestation {gres} on the running sha, {gage / 3600:.1f}h old"
    if ident and tested.upper() == "UNMEASURED":
        out["tested_sha_why"] = "release_identity reports tested_sha UNMEASURED: no suite attestation is bound to the seal"
    rel = _read(DESK / "data" / "RELEASE.json") or _read(ROOT / "RELEASE.json") or {}
    sealed = str(rel.get("code_sha") or rel.get("sha") or "")
    # THE BOX COMMITS STATE ON TOP OF THE SEALED CODE (Adopt-And-Seal: "plus seal/state commits
    # only"), so its HEAD is never the sealed sha itself. The sealed code is running when the
    # sealed sha is an ancestor of the running HEAD and nothing on the code paths differs --
    # which is what `running_sha_matches` (release_identity's own verdict) already attests.
    out["sealed_sha_matches"] = (bool(sealed) and bool(running) and sealed == running) if (rel and ident) else None
    if rel and ident and sealed and running and sealed != running:
        try:
            import subprocess
            anc = subprocess.run(["git", "merge-base", "--is-ancestor", sealed, running],
                                 capture_output=True, text=True, cwd=str(ROOT), timeout=60)
            out["sealed_sha_matches"] = (anc.returncode == 0
                                         and str(ident.get("verdict")) == "OK")
            out["sealed_sha_why"] = ("sealed code is an ancestor of the running HEAD and the "
                                     "identity verdict is OK (state commits ride on top of a seal)"
                                     if out["sealed_sha_matches"] else
                                     f"sealed {sealed[:12]} is not an ancestor of running {running[:12]}")
        except Exception as exc:
            out["sealed_sha_why"] = f"ancestry unmeasured ({type(exc).__name__})"
    proof = _read(ROOT / "reports" / "ALLOCATOR_PROOF.json") or _read(DESK / "reports" / "ALLOCATOR_PROOF.json") or {}
    if proof:
        try:
            at = datetime.fromisoformat(str(proof.get("at")).replace("Z", "+00:00"))
            fresh = (datetime.now(tz=UTC) - at).total_seconds() < float(proof.get("max_age_s") or FRESH_S)
        except ValueError:
            fresh = False
        out["allocator_certificate_valid"] = bool(proof.get("passed")) and fresh
    else:
        out["allocator_certificate_valid"] = None
    att = _first_existing(ROOT / "data" / "gate_attestation.json", ROOT / "reports" / "GATE_ATTESTATION.json",
                          DESK / "data" / "gate_attestation.json")
    if att is not None:
        doc = _read(att) or {}
        sha = str(doc.get("sha") or doc.get("tested_sha") or doc.get("head") or "")
        out["ci_green"] = (str(doc.get("result") or doc.get("verdict") or doc.get("status")).lower() in ("pass", "green", "ok")
                           and (not running or sha.startswith(running[:12]) or running.startswith(sha[:12])))
    else:
        out["ci_green"] = None
        out["ci_green_why"] = "no gate attestation artifact on this box"
    return out


def truth() -> dict[str, Any]:
    out: dict[str, Any] = {}
    pit = _first_existing(DESK / "reports" / "PIT_CENSUS.json", ROOT / "reports" / "PIT_CENSUS.json",
                          DESK / "reports" / "pit_census.json")
    doc = _read(pit) if pit else None
    if isinstance(doc, dict):
        can = doc.get("canaries") or doc.get("canary")
        out["pit_canaries_green"] = (bool(can.get("green")) if isinstance(can, dict) else None)
        if out["pit_canaries_green"] is None:
            out["pit_canaries_why"] = "PIT census carries no planted-canary block"
    else:
        out["pit_canaries_green"] = None
        out["pit_canaries_why"] = "no PIT census artifact"
    cons = _first_existing(DESK / "reports" / "CANDIDATE_CONSERVATION.json",
                           DESK / "reports" / "candidate_conservation.json",
                           DESK / "data" / "hypotheses" / "conservation.json")
    cdoc = _read(cons) if cons else None
    if isinstance(cdoc, dict):
        lost = cdoc.get("lost") if isinstance(cdoc.get("lost"), (int, float)) else cdoc.get("n_lost")
        out["lost_candidates"] = int(lost) if isinstance(lost, (int, float)) else None
        out["provenance_conservation"] = (out["lost_candidates"] == 0) if out["lost_candidates"] is not None else None
    else:
        out["provenance_conservation"] = None
        out["lost_candidates"] = None
        out["provenance_why"] = "no candidate-conservation artifact; conservation is derived from counts, not an event ledger"
    return out


def forward() -> dict[str, Any]:
    out: dict[str, Any] = {}
    sh = _read(DESK / "reports" / "shadow" / "shadow_health.json") or {}
    if sh:
        counts = sh.get("counts") or sh.get("by_status") or {}
        silent = counts.get("SILENT") if isinstance(counts, dict) else None
        churned = counts.get("CHURNED") if isinstance(counts, dict) else None
        if silent is None:
            silent = sh.get("silent_clocks") if isinstance(sh.get("silent_clocks"), (int, float)) else None
        if churned is None:
            churned = sh.get("churned_clocks") if isinstance(sh.get("churned_clocks"), (int, float)) else None
        out["silent_clocks"] = int(silent) if isinstance(silent, (int, float)) else None
        out["churned_clocks"] = int(churned) if isinstance(churned, (int, float)) else None
        # The lane's own vocabulary is OPERATING; silent clocks are the sleeves it cannot
        # represent or evidence, in its own counts.
        out["lane_health"] = (str(sh.get("verdict") or sh.get("status") or "").upper() in ("OK", "HEALTHY", "OPERATING")) if (sh.get("verdict") or sh.get("status")) else None
        if out["silent_clocks"] is None:
            miss = sh.get("missing_sleeves")
            blocked = sh.get("evidence_blocked_sleeves")
            if isinstance(miss, (int, float)) or isinstance(blocked, (int, float)):
                out["silent_clocks"] = int(miss or 0) + int(blocked or 0)
    else:
        out.update({"silent_clocks": None, "churned_clocks": None, "lane_health": None,
                    "why": "no shadow_health.json"})
    rec = _first_existing(DESK / "reports" / "FORWARD_RECONCILE.json", DESK / "reports" / "forward_reconcile.json",
                          DESK / "data" / "forward_reconcile.json")
    rdoc = _read(rec) if rec else None
    out["identity_reconciliation"] = (bool(rdoc.get("identities_ok", rdoc.get("ok"))) if isinstance(rdoc, dict) else None)
    out["clock_reconciliation"] = (bool(rdoc.get("clocks_ok", rdoc.get("ok"))) if isinstance(rdoc, dict) else None)
    if isinstance(rdoc, dict) and "identities_ok" not in rdoc and "ok" not in rdoc:
        # research/forward_reconcile.py's own shape: what it could not read or reach, by name.
        def _n(v: Any) -> int | None:
            if isinstance(v, bool):
                return None
            if isinstance(v, (int, float)):
                return int(v)
            if isinstance(v, dict):
                # forward_reconcile's dict shape carries its own count under `n`.
                return int(v["n"]) if isinstance(v.get("n"), (int, float)) else len(v)
            if isinstance(v, list):
                return len(v)
            return None
        unfrozen, unreachable = _n(rdoc.get("identity_unfrozen")), _n(rdoc.get("unreachable_certified"))
        readable = rdoc.get("enrolment_readable")
        if unfrozen is not None:
            out["identity_reconciliation"] = (unfrozen == 0) and (readable is not False)
            out["churned_clocks"] = unfrozen if out.get("churned_clocks") is None else out["churned_clocks"]
        if unreachable is not None:
            out["clock_reconciliation"] = (unreachable == 0) and (readable is not False)
        out["reconcile_why"] = (f"forward_reconcile.json: identity_unfrozen={unfrozen}, "
                                f"unreachable_certified={unreachable}, enrolment_readable={readable}")
    if rdoc is None:
        out["reconcile_why"] = "no forward reconciliation artifact"
    return out


def research() -> dict[str, Any]:
    out: dict[str, Any] = {}
    ceo = _read(DESK / "reports" / "CEO_DOCKET.json") or {}
    # The frontier map is AUTHORITATIVE only if the queue it writes is what the gauntlet consumes
    # and nothing else feeds that queue; the CEO docket says so itself or it is advisory.
    out["frontier_scheduler_authoritative"] = (bool(ceo.get("authoritative")) if "authoritative" in ceo else False)
    if "authoritative" not in ceo:
        out["frontier_why"] = "CEO_DOCKET.json carries no `authoritative` claim: the docket proposes; the gauntlet's own queue decides"
    bandit = _read(DESK / "reports" / "RESEARCH_BANDIT.json") or {}
    out["evig_controller_authoritative"] = (bool(bandit.get("authoritative")) if "authoritative" in bandit else False)
    if "authoritative" not in bandit:
        out["evig_why"] = "RESEARCH_BANDIT.json prices arms but does not schedule them: advisory"
    gw = _read(DESK / "data" / "generator_weights.json") or {}
    rc = bandit.get("realised_credit") if isinstance(bandit.get("realised_credit"), dict) else {}
    gw_credit = gw.get("_realised_credit") if isinstance(gw.get("_realised_credit"), dict) else {}
    if rc.get("applied") and str(rc.get("basis")) == "live":
        out["delayed_truth_credit_live"] = True
        out["credit_why"] = (f"realised LIVE credit multiplies the bandit's worth on {len(rc.get('by_arm') or {})} arm(s)"
                             f" and the generator weights on {len(gw_credit)} generator(s) (bounded)")
    elif rc.get("applied"):
        out["delayed_truth_credit_live"] = False
        out["credit_why"] = (f"realised credit flows on {rc.get('basis')} evidence (live ledger has "
                             f"{rc.get('n_live_deals')} deals; live basis needs the credit organ's floor)")
    else:
        out["delayed_truth_credit_live"] = False
        out["credit_why"] = (str(rc.get("why")) if rc else
                             ("generator weights move on certification fate only; the bandit carries no "
                              "realised_credit block yet" if gw else "no generator_weights.json"))
    return out


def meta() -> dict[str, Any]:
    out: dict[str, Any] = {}
    mc = _first_existing(DESK / "reports" / "META_CONTROLLER.json", DESK / "reports" / "meta_controller.json",
                         DESK / "data" / "meta_controller_state.json")
    mdoc = _read(mc) if mc else None
    out["controller_completed_epoch"] = (bool(mdoc.get("epoch_complete", mdoc.get("completed"))) if isinstance(mdoc, dict) else None)
    if mdoc is None:
        out["controller_why"] = "no meta-controller artifact"
    gw_age = _age_s(DESK / "data" / "generator_weights.json")
    out["compute_reallocated_from_outcomes"] = (gw_age is not None and gw_age < FRESH_S)
    rb_age = _age_s(DESK / "reports" / "RESEARCH_BANDIT.json")
    out["information_budget_reallocated_from_outcomes"] = (rb_age is not None and rb_age < FRESH_S)
    proof = _read(ROOT / "reports" / "ALLOCATOR_PROOF.json") or _read(DESK / "reports" / "ALLOCATOR_PROOF.json") or {}
    out["capital_reallocated_from_outcomes"] = bool(proof.get("passed")) if proof else None
    return out


#: The control plane's invariants that OVERLAP this attestation's own guesses, and the flag each
#: one replaces. Where the reconciler has measured, its verdict wins: it reads leases, watermarks
#: and acknowledgements, where the blocks above read file ages and booleans.
_CP_OVERLAPS: dict[str, tuple[str, str]] = {
    "candidate_conservation": ("truth", "provenance_conservation"),
    "controller": ("meta", "controller_completed_epoch"),
    "release": ("release_authority", "sealed_sha_matches"),
}


def control_plane() -> dict[str, Any]:
    """THE RECONCILER'S REPORT, CONSUMED (LAWS 7). Twelve invariants and the one bit,
    DESK_CLOSED_AND_HEALTHY; absent, every one is UNMEASURED and this attestation cannot be
    `complete` -- a closed loop nobody has observed is not closed."""
    doc = _read(DESK / "reports" / "CONTROL_PLANE.json")
    out: dict[str, Any] = {}
    if not isinstance(doc, dict):
        out["desk_closed_and_healthy"] = None
        out["control_plane_why"] = "no CONTROL_PLANE.json: the reconciler has not published"
        return out
    inv = doc.get("invariants") if isinstance(doc.get("invariants"), dict) else {}
    for name, row in inv.items():
        out[f"invariant_{name}"] = row.get("ok") if isinstance(row, dict) else None
    out["desk_closed_and_healthy"] = bool(doc.get("DESK_CLOSED_AND_HEALTHY"))
    out["epoch_id"] = doc.get("epoch_id")
    out["first_broken_invariant"] = doc.get("first_broken_invariant")
    return out


def measure() -> dict[str, Any]:
    blocks = {"release_authority": release_authority(), "truth": truth(), "forward": forward(),
              "research": research(), "meta": meta(), "control_plane": control_plane()}
    cp = blocks["control_plane"]
    for inv_name, (block, flag) in _CP_OVERLAPS.items():
        verdict = cp.get(f"invariant_{inv_name}")
        if verdict is not None and flag in blocks[block]:
            blocks[block][flag] = bool(verdict)
            blocks[block][f"{flag}_basis"] = f"control plane invariant {inv_name}"
    flags: list[tuple[str, Any]] = []
    for b, d in blocks.items():
        for k, v in d.items():
            if isinstance(v, bool) or v is None:
                flags.append((f"{b}.{k}", v))
            elif k in ("silent_clocks", "churned_clocks", "lost_candidates"):
                flags.append((f"{b}.{k}", (v == 0) if v is not None else None))
    n_true = sum(1 for _, v in flags if v is True)
    n_false = sum(1 for _, v in flags if v is False)
    n_unm = sum(1 for _, v in flags if v is None)
    ledger = _read(ROOT / "docs" / "research" / "tier1_program.json") or {}
    items = [i for i in ledger.get("items", []) if str(i.get("phase")) == "B"]
    landed = sum(1 for i in items if i.get("status") in ("LANDED", "EXISTS-LIT"))
    doc = {
        "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "architecture_28_implemented": bool(items) and landed == len(items),
        "architecture_28_census": {"items": len(items), "landed_or_lit": landed,
                                   "by_status": {s: sum(1 for i in items if i.get("status") == s)
                                                 for s in sorted({str(i.get("status")) for i in items})}},
        **blocks,
        "summary": {"true": n_true, "false": n_false, "unmeasured": n_unm,
                    "open": [k for k, v in flags if v is not True]},
        "complete": bool(items) and landed == len(items) and n_false == 0 and n_unm == 0,
        "rule": ("every flag is derived from another organ's artifact; null is UNMEASURED and never "
                 "a pass; complete requires all 28 blueprint items LANDED/EXISTS-LIT and every flag true"),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1), "utf-8")
    return doc


def main() -> int:
    doc = measure()
    s = doc["summary"]
    print(f"closed loop: complete={doc['complete']} | flags true={s['true']} false={s['false']} "
          f"unmeasured={s['unmeasured']} | blueprint {doc['architecture_28_census']} -> {OUT}")
    for k in s["open"][:40]:
        print("   open:", k)
    return 0


if __name__ == "__main__":
    sys.exit(main())
