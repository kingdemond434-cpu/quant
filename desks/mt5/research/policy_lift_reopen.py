"""RE-OPEN THE SLEEVES THE LIVE SYMBOL WHITELIST RETIRED, ON VERIFIED NET-OF-COST EVIDENCE ONLY.

The principal, 2026-11-13: lifted the live symbol whitelist (decision card 19:17:59Z), "All the
promoted ones can we put them all on live accounts now I didn't mean to white list" (19:18Z),
and the condition (19:23Z): "make sure all r actual edges post costs n everything proper like we
planned if they aren't all real the 170 we wont put them live only if they are n ones which are".

WHY A SEPARATE ORGAN. `research/promoter.py` is sealed (data/IMMUTABLE_MANIFEST.json). It skips any
clock whose name already has a row in data/sleeves.json, so the 170 rows `_apply_live_policy`
retired would block their own clocks forever even with the policy lifted. This organ runs as the
hourly leg `policy_lift_reopen`, immediately BEFORE `promoter`, and only RENAMES a verified row
so the sealed promoter re-judges the clock through every one of its own doors. It never writes
LIVE, never sizes, never touches a row retired on its own evidence, and writes
reports/REOPEN_VERIFICATION.json with every candidate's verdict and reasons.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SLEEVES_FILE = BASE / "data" / "sleeves.json"
SHADOW_DIR = BASE / "reports" / "shadow"
RECERT_AUDIT = BASE / "reports" / "recertification_audit.json"
#: The promoter's own freshness for the re-grade audit (promoter.RECERT_FRESH_H).
RECERT_FRESH_H = 72.0
RENAME_SUFFIX = "~retired_live_policy"
LOG = BASE / "logs" / "policy_lift_reopen.log"


def plog(msg: str) -> None:
    line = f"{datetime.now(tz=UTC).isoformat(timespec='seconds')} {msg}"
    print(line)
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


#: The status a policy-retired row takes when the policy that retired it no longer refuses it and
#: its clock is still a candidate: it stays in sleeves.json as the record, and the clock is judged
#: again through every promotion door on the same pass.
POLICY_REOPENED = "SUPERSEDED_POLICY_LIFTED"


#: THE PRINCIPAL'S CONDITION ON THE LIFT (zuck 2026-11-13 19:23Z): "make sure all r actual edges
#: post costs n everything proper ... if they aren't all real the 170 we wont put them live only if
#: they are". A policy-retired row comes back ONLY on POSITIVE evidence, every clause required:
#:   * a FRESH cost re-grade (scripts/recertify_canon.py, <= RECERT_FRESH_H) whose row for THIS
#:     certificate reads STILL_PASSES: the ten gates re-run at today's spread, commission and swap.
#:     Absent, stale, UNMEASURED or unmatched is NOT a pass -- unlike `regrade_failures`, which
#:     only binds on a fresh FAIL, this needs a fresh PASS;
#:   * forward t >= EDGE_MIN_T and n >= EDGE_MIN_N on the clock's own net-of-cost R;
#:   * the clock's certificate is still in the authority set (no `certificate_drift`);
#:   * the forward evidence came from the venue's own bars (`evidence_venue` FusionMarkets);
#:   * the forward max drawdown clears the promotion bar (PROMOTE_MIN_DD).
#: Then the ordinary doors run on top (blind review, Tier S, executor, allocator).
EDGE_MIN_T = 2.0
EDGE_MIN_N = 30
EDGE_MIN_DD = -25.0
EDGE_VENUE = "FusionMarkets"
REOPEN_REPORT = BASE / "reports" / "REOPEN_VERIFICATION.json"


def clock_certificates() -> dict[str, str]:
    """clock key -> the canon certificate name that enrolled it, rebuilt exactly as
    `shadow_forward.certified_sleeves` keys a run. Empty on any failure (fail closed: an
    unmapped clock has no certificate to verify, so it is not reopened)."""
    try:
        import shadow_forward as sf
        from shadow_admission import authorized_runs
        out: dict[str, str] = {}
        for run in authorized_runs(BASE):
            fam = run["family"]
            if fam == "session_range_breakout":
                if run["selector"] not in sf.WINDOWS:
                    continue
                params = dict(sf.WINDOWS[run["selector"]])
                params.update(run["params"])
            else:
                params = dict(run["params"] or {})
            side = sf._runnable_side(run, fam)
            if side is None:
                continue
            key = sf.sleeve_key(run["symbol"], run["selector"], params, fam, side)
            out[key] = str(run.get("certificate") or "")
        return out
    except Exception as exc:
        plog(f"clock certificates unavailable ({type(exc).__name__}: {exc}); nothing reopens")
        return {}


def recert_rows(now: datetime | None = None) -> tuple[dict[str, dict], str]:
    """(certificate -> re-grade row, why-not) from a FRESH recertification audit only."""
    try:
        doc = json.loads(RECERT_AUDIT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, f"{RECERT_AUDIT.name} absent: no cost re-grade at today's costs"
    try:
        age_h = ((now or datetime.now(tz=UTC)) - datetime.fromisoformat(
            str(doc.get("audited_at")))).total_seconds() / 3600.0
    except ValueError:
        age_h = float("inf")
    if age_h > RECERT_FRESH_H:
        return {}, f"{RECERT_AUDIT.name} is {age_h:.0f}h old (> {RECERT_FRESH_H:.0f}h)"
    return ({str(r.get("certificate")): r for r in (doc.get("rows") or [])
             if isinstance(r, dict)}, "")


def edge_verdict(key: str, st: dict, cert: str, recert: dict[str, dict],
                 recert_why: str) -> list[str]:
    """Every reason this clock is NOT a verified net-of-cost edge (empty = verified)."""
    why: list[str] = []
    if not cert:
        why.append("NO_CERTIFICATE: the clock maps to no certificate in the authority set")
    row = recert.get(cert) if cert else None
    if row is None:
        why.append(f"NO_FRESH_COST_REGRADE: {recert_why or 'this certificate is not in the audit'}")
    elif row.get("status") != "STILL_PASSES":
        why.append(f"{row.get('status') or 'UNMEASURED'}: re-grade at today's costs "
                   f"{row.get('gates_failing_now') or row.get('why') or ''}")
    try:
        t, n = float(st.get("forward_t") or 0.0), int(float(st.get("n") or 0))
        dd = float(st.get("max_dd_r") or 0.0)
    except (TypeError, ValueError):
        t, n, dd = 0.0, 0, float("-inf")
    if t < EDGE_MIN_T:
        why.append(f"FORWARD_T {t:.2f} < {EDGE_MIN_T}")
    if n < EDGE_MIN_N:
        why.append(f"FORWARD_N {n} < {EDGE_MIN_N}")
    if dd <= EDGE_MIN_DD:
        why.append(f"FORWARD_MAXDD {dd:.1f}R <= {EDGE_MIN_DD}R")
    if st.get("certificate_drift"):
        why.append("CERTIFICATE_DRIFT: the certificate left the authority set")
    if EDGE_VENUE not in str(st.get("evidence_venue") or ""):
        why.append(f"NON_VENUE_EVIDENCE: {st.get('evidence_venue')!r}")
    return why


def reopen_policy_retirements(sleeves: list[dict], lane_states: list[dict],
                              verify: bool = True) -> set[str]:
    """RE-OPEN every row the LIVE POLICY retired whose policy now admits it (2026-11-13).

    The principal lifted the live symbol whitelist (zuck 2026-11-13 19:17:59Z decision card,
    and 19:18Z: "All the promoted ones can we put them all on live accounts now I didn't mean to
    white list"). Measured that day: all 170 shadow PROMOTION CANDIDATEs had been written LIVE and
    RETIRED on the same pass by `_apply_live_policy` (retired_by live_policy, "SYM is outside the
    live sleeve universe"). A retired name stays in `existing`, so lifting the policy alone would
    never bring one back.

    ONLY rows `_apply_live_policy` retired, ONLY when `live_policy.refuse` now returns None, and
    ONLY when a lane still holds that clock as a promotion candidate. Such a row is marked
    POLICY_REOPENED and RENAMED `<name>~retired_live_policy` (kept as the record, `original_name`
    holds the clock key), so the promoter -- which runs next, in the same hourly pass -- no longer
    finds the name in `existing` and its ordinary lane loop re-promotes the clock through EVERY
    door: banned family, cost re-grade, blind review,
    Tier S, executor and the allocator's capital verdict. A row retired on its own forward
    evidence (retired_by absent) is never touched: the one-way door stays one-way."""
    try:
        from mt5desk.live_policy import policy, refuse
    except ImportError:                                    # pragma: no cover - box path only
        return set()
    candidates: dict[str, dict] = {}
    for st in lane_states:
        rows = st.get("sleeves") if isinstance(st.get("sleeves"), dict) else st
        for k, v in (rows or {}).items():
            if isinstance(v, dict) and str(v.get("status") or "").replace("_", " ") \
                    == "PROMOTION CANDIDATE":
                candidates[str(k)] = v
    certs = clock_certificates() if verify else {}
    recert, recert_why = recert_rows() if verify else ({}, "")
    report: dict[str, dict] = {}
    pol = policy()
    stamp = datetime.now(tz=UTC).isoformat(timespec="seconds")
    reopened: set[str] = set()
    for row in sleeves:
        name = str(row.get("name") or "")
        if (str(row.get("status") or "").upper() != "RETIRED"
                or row.get("retired_by") != "live_policy" or name not in candidates):
            continue
        # Another row already answers to this name (LIVE, STANDBY or a later retirement): the
        # promoter would not re-promote it anyway, so nothing is renamed.
        if sum(1 for r in sleeves if r.get("name") == name) > 1:
            continue
        why_refused = refuse(row, pol)
        if why_refused:
            if verify:
                report[name] = {"certificate": None, "verified": False,
                                "why_not": [f"LIVE_POLICY: {why_refused}"]}
            continue
        if verify:
            cert = certs.get(name) or (name if name in recert else "")
            failed = edge_verdict(name, candidates[name], cert, recert, recert_why)
            report[name] = {"certificate": cert or None, "verified": not failed,
                            "why_not": failed}
            if failed:
                continue
        row["status"] = POLICY_REOPENED
        row["original_name"] = name
        row["name"] = f"{name}{RENAME_SUFFIX}"
        row["reopened_at"] = stamp
        row["reopened_why"] = ("the live policy that retired this row admits it now; the clock "
                               "is re-judged through every promotion door")
        reopened.add(name)
        plog(f"LIVE POLICY lifted for {name}: retired row superseded, clock re-judged this pass")
    if verify:
        _write_reopen_report(report, recert_why)
    return reopened


def _write_reopen_report(report: dict[str, dict], recert_why: str) -> None:
    """reports/REOPEN_VERIFICATION.json: every policy-retired candidate, verified or not, why."""
    reasons: dict[str, int] = {}
    for r in report.values():
        for w in r["why_not"]:
            head = w.split(":", 1)[0].split(" ", 1)[0]
            reasons[head] = reasons.get(head, 0) + 1
    doc = {"at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
           "rule": ("principal 2026-11-13 19:23Z: only real edges net of all costs go live; a "
                    "policy-retired candidate returns only on a fresh STILL_PASSES cost re-grade, "
                    f"forward t >= {EDGE_MIN_T}, n >= {EDGE_MIN_N}, max DD > {EDGE_MIN_DD}R, no "
                    "certificate drift and venue-native forward bars"),
           "recert_status": recert_why or "FRESH",
           "n_candidates": len(report),
           "n_verified": sum(1 for r in report.values() if r["verified"]),
           "fail_reasons": reasons, "rows": report}
    try:
        REOPEN_REPORT.parent.mkdir(parents=True, exist_ok=True)
        tmp = REOPEN_REPORT.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
        os.replace(tmp, REOPEN_REPORT)
    except OSError as exc:
        plog(f"REOPEN_VERIFICATION.json not written ({type(exc).__name__}: {exc})")


def _read(path: Path) -> dict:
    try:
        doc = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def main() -> int:
    doc = _read(SLEEVES_FILE)
    sleeves = doc.get("sleeves")
    if not isinstance(sleeves, list):
        plog("sleeves.json absent or unreadable -- nothing to reopen")
        return 0
    lanes = [_read(SHADOW_DIR / n) for n in ("shadow_state.json", "qquant_shadow_state.json",
                                             "scalp_shadow_state.json")]
    # THE STRICT EXOTIC COST BAR FIRST (principal 2026-11-13 19:46Z): its verdict is what
    # `live_policy.refuse` reads for every exotic row, here, in the promoter that runs next and in
    # the gateway. Written every pass so it is never stale while this leg runs.
    try:
        import exotic_cost_bar as ecb
        bar = ecb.build(lanes, _read(ecb.UNIVERSE), _read(ecb.SURFACE))
        ecb.write(bar)
        plog(f"exotic cost bar: {bar['counts']} of {bar['n_exotic_clocks']} exotic clocks")
    except Exception as exc:                       # the policy then refuses exotics: fail closed
        plog(f"exotic cost bar not written ({type(exc).__name__}: {exc}); exotics refused")
    reopened = reopen_policy_retirements(sleeves, lanes)
    if reopened:
        doc["sleeves"] = sleeves
        tmp = SLEEVES_FILE.with_suffix(".json.reopen.tmp")
        tmp.write_text(json.dumps(doc, indent=2), encoding="utf-8")
        os.replace(tmp, SLEEVES_FILE)
    plog(f"policy_lift_reopen: {len(reopened)} verified row(s) handed back to the promoter")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
