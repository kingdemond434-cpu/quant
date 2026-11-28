"""THE 10-POINT AUTONOMY SPEC, MEASURED -- never claimed (zuck 2026-11-13 16:21Z and 20:14Z).

    python scripts/autonomy_conformance.py            # writes the report
    python scripts/autonomy_conformance.py --print    # stdout only

Writes desks/mt5/reports/AUTONOMY_CONFORMANCE.json (box state, published). Run with the merge
watch (scripts/merge_pipeline_watch.py, Quant-WorkflowGate), so it adds no scheduled task.

zuck's spec ends: "Do not claim full autonomy merely because the configuration has changed ...
Report the remaining blockers with their exact technical causes ... Do not simply batch approval
requests or hide failures." So each point is scored ONLY from an artifact the box or the gate
already publishes, and each score is one of:

    MET          the artifact is fresh and shows the point holds
    NOT_MET      the artifact is fresh and shows it does not (the `blocker` says which signal)
    UNMEASURED   no artifact, or one older than its freshness bound: never a pass (L1.28a)

`autonomous` is true only when all ten are MET. The report carries enums, numbers and times only
(the repository is public): every source is named by its path, never quoted.

    1  stuck checks           MERGE_PIPELINE.json: no CI_QUEUED / LIVE_CI_QUEUED / WATCH_BLIND
    2  no APPROVE MERGES      RELEASE_PIPELINE_PROOF.json: no APPROVE_MERGES touch in 24 h, and
                              AUTHORITY_REPLAY.json: no PR whose only path is zuck's ROOT merge
    3  dependencies audited   the three readers above are fresh and process_health is read
    4  unattended permissions process_health.json claude_settings.status == OK
    5  narrow automation      BOX_ACTIONS.json (the box execution service) fresh and not failing
    6  diagnosis & recovery   RELEASE_PIPELINE_PROOF.json: no ADOPTION_BLOCKED/IDENTITY_STALE and
                              the box identity ok
    7  survives session end   BOX_ACTIONS.json shows persisted done-state AND the Remote Control
                              watchdog publishes boot_start PROVEN (BRIDGE_STATUS.json); either
                              missing is UNMEASURED
    8  one scheduler          ARCH_HEALTH.json (arch_health, #1102): no duplicate workers
    9  dev != trading         the release authority's ROOT_POLICY keeps the risk ceilings and the
                              live-money envelope ROOT (read from this checkout)
    10 24 h acceptance        RELEASE_PIPELINE_PROOF.json autonomy_proof.verdict == PROVEN
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "desks" / "mt5" / "reports"
OUT = REPORTS / "AUTONOMY_CONFORMANCE.json"
ROOT_POLICY = ROOT / "ops" / "release" / "authority" / "ROOT_POLICY.json"
#: Hours after which a source is too old to score from.
FRESH_H = {
    "MERGE_PIPELINE.json": 2.0,
    "RELEASE_PIPELINE_PROOF.json": 3.0,
    "AUTHORITY_REPLAY.json": 12.0,
    "process_health.json": 3.0,
    "BOX_ACTIONS.json": 2.0,
    "BRIDGE_STATUS.json": 2.0,
    "ARCH_HEALTH.json": 3.0,
}
ASKS = {
    1: "resolve stuck GitHub checks blocking deployment",
    2: "no custom APPROVE MERGES requirement",
    3: "audit every prompt, blocked action, stalled job, human dependency",
    4: "supported unattended permissions configured",
    5: "narrowly scoped audited automation for server operations",
    6: "automatic diagnosis, bounded retries, escalation, rollback, recovery",
    7: "session end never stops the workflow; persisted state, resume",
    8: "one canonical scheduler, dedup, no competing workers",
    9: "development autonomy separate from trading authority",
    10: "24 h unattended acceptance test",
}


def _ts(s: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def read(name: str, reports: Path, now: datetime) -> tuple[dict[str, Any] | None, float | None]:
    """(document, age in hours); a document older than its bound is returned as None."""
    try:
        doc = json.loads((reports / name).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None, None
    if not isinstance(doc, dict):
        return None, None
    at = _ts(doc.get("at") or doc.get("measured_at") or doc.get("generated_utc"))
    age = None if at is None else round((now - at).total_seconds() / 3600.0, 2)
    if age is None or age > FRESH_H.get(name, 3.0):
        return None, age
    return doc, age


def _red_has(doc: Mapping[str, Any], *prefixes: str) -> list[str]:
    return [p for p in prefixes if any(str(r).startswith(p) for r in doc.get("red") or [])]


def score(
    now: datetime, reports: Path = REPORTS, root_policy: Path = ROOT_POLICY
) -> dict[str, Any]:
    docs: dict[str, tuple[dict[str, Any] | None, float | None]] = {
        n: read(n, reports, now) for n in FRESH_H
    }

    def d(n: str) -> dict[str, Any] | None:
        return docs[n][0]

    rows: list[dict[str, Any]] = []

    def put(point: int, status: str, sources: list[str], blocker: str | None = None,
            **evidence: Any) -> None:  # fmt: skip
        rows.append(
            {
                "point": point,
                "ask": ASKS[point],
                "status": status,
                "blocker": blocker,
                "sources": {s: docs[s][1] for s in sources if s in docs},
                "evidence": evidence,
            }
        )

    # 1 stuck checks
    mp = d("MERGE_PIPELINE.json")
    if mp is None:
        put(1, "UNMEASURED", ["MERGE_PIPELINE.json"], "SOURCE_STALE_OR_ABSENT")
    else:
        hit = _red_has(mp, "CI_QUEUED", "LIVE_CI_QUEUED", "WATCH_BLIND")
        put(1, "NOT_MET" if hit else "MET", ["MERGE_PIPELINE.json"], hit[0] if hit else None,
            red_signals=hit)  # fmt: skip

    # 2 no APPROVE MERGES
    rp, ar = d("RELEASE_PIPELINE_PROOF.json"), d("AUTHORITY_REPLAY.json")
    if rp is None or ar is None:
        put(2, "UNMEASURED", ["RELEASE_PIPELINE_PROOF.json", "AUTHORITY_REPLAY.json"],
            "SOURCE_STALE_OR_ABSENT")  # fmt: skip
    else:
        cutoff = now.timestamp() - 24 * 3600
        approvals = [
            t
            for t in rp.get("human_touches") or []
            if t.get("kind") == "APPROVE_MERGES" and (_ts(t.get("at")) or now).timestamp() >= cutoff
        ]
        root = list((ar.get("summary") or {}).get("need_zuck_root") or [])
        blocker = "APPROVE_MERGES_TYPED" if approvals else "ROOT_PRS_NEED_OWNER" if root else None
        put(2, "NOT_MET" if blocker else "MET",
            ["RELEASE_PIPELINE_PROOF.json", "AUTHORITY_REPLAY.json"], blocker,
            approve_merges_24h=len(approvals), prs_needing_owner_root=len(root))  # fmt: skip

    # 3 dependencies audited (the readers exist and are fresh)
    need = ["MERGE_PIPELINE.json", "RELEASE_PIPELINE_PROOF.json", "AUTHORITY_REPLAY.json",
            "process_health.json"]  # fmt: skip
    stale = [n for n in need if d(n) is None]
    ph = d("process_health.json")
    put(3, "UNMEASURED" if stale else "MET", need,
        "SOURCE_STALE_OR_ABSENT" if stale else None, stale_sources=len(stale),
        attention=(ph or {}).get("n_needing_attention"))  # fmt: skip

    # 4 unattended permissions
    cs = (ph or {}).get("claude_settings") if ph else None
    st = (cs or {}).get("status")
    if ph is None or st in (None, "UNMEASURED", "NOT_APPLICABLE"):
        put(4, "UNMEASURED", ["process_health.json"], "SETTINGS_UNREAD")
    else:
        put(4, "MET" if st == "OK" else "NOT_MET", ["process_health.json"],
            None if st == "OK" else f"SETTINGS_{st}", settings_status=st)  # fmt: skip

    # 5 narrow automation service
    ba = d("BOX_ACTIONS.json")
    if ba is None:
        put(5, "UNMEASURED", ["BOX_ACTIONS.json"], "BOX_ACTIONS_NOT_RUNNING")
    else:
        failing = int(ba.get("failed") or ba.get("n_failed") or 0)
        put(5, "NOT_MET" if failing else "MET", ["BOX_ACTIONS.json"],
            "BOX_ACTIONS_FAILING" if failing else None, failed=failing)  # fmt: skip

    # 6 diagnosis & recovery
    if rp is None:
        put(6, "UNMEASURED", ["RELEASE_PIPELINE_PROOF.json"], "SOURCE_STALE_OR_ABSENT")
    else:
        hit = _red_has(rp, "ADOPTION_BLOCKED", "IDENTITY_STALE", "IDENTITY_UNREAD")
        ok = bool((rp.get("box") or {}).get("ok"))
        put(6, "MET" if ok and not hit else "NOT_MET", ["RELEASE_PIPELINE_PROOF.json"],
            hit[0] if hit else None if ok else "BOX_IDENTITY_NOT_OK", red_signals=hit)  # fmt: skip

    # 7 survives session end
    bs = d("BRIDGE_STATUS.json")
    if ba is None or bs is None:
        put(7, "UNMEASURED", ["BOX_ACTIONS.json", "BRIDGE_STATUS.json"],
            "BOX_ACTIONS_NOT_RUNNING" if ba is None else "BRIDGE_STATUS_NOT_PUBLISHED")  # fmt: skip
    else:
        boot = bs.get("boot_start")
        persisted = bool(ba.get("done_rows") or ba.get("n_done"))
        good = boot == "PROVEN" and persisted
        put(7, "MET" if good else "NOT_MET", ["BOX_ACTIONS.json", "BRIDGE_STATUS.json"],
            None if good else "BOOT_START_UNPROVEN" if boot != "PROVEN" else "NO_PERSISTED_STATE",
            boot_start=boot)  # fmt: skip

    # 8 one scheduler
    ah = d("ARCH_HEALTH.json")
    if ah is None:
        put(8, "UNMEASURED", ["ARCH_HEALTH.json"], "ARCH_HEALTH_NOT_RUNNING")
    else:
        dup = int(ah.get("duplicate_workers") or len(ah.get("duplicates") or []) or 0)
        put(8, "NOT_MET" if dup else "MET", ["ARCH_HEALTH.json"],
            "DUPLICATE_WORKERS" if dup else None, duplicates=dup)  # fmt: skip

    # 9 dev autonomy != trading authority: risk ceilings move only inside the pre-delegated
    # envelope (each raisable knob bounded by a hard max), and the authority itself stays ROOT
    try:
        pol = json.loads(root_policy.read_text(encoding="utf-8"))
        roots = [str(x) for x in pol.get("root_files") or []]
        env = pol.get("envelope") or {}
        raisable = env.get("raisable") or {}
        # {file: {knob: {hard_max, max_step_frac}}}
        knobs = [
            k for f in (raisable.values() if isinstance(raisable, dict) else []) if isinstance(f, dict)
            for k in f.values()
        ]  # fmt: skip
        bounded = bool(knobs) and all(
            isinstance(k, dict) and k.get("hard_max") is not None and k.get("max_step_frac")
            for k in knobs
        )
        self_root = any(r.startswith("ops/release/authority") for r in roots)
        good = bool(env) and bounded and self_root
        put(9, "MET" if good else "NOT_MET", [], None if good else "RISK_ENVELOPE_UNBOUNDED",
            envelope=bool(env), raisable_knobs=len(knobs),
            authority_is_root=self_root)  # fmt: skip
    except (OSError, ValueError, AttributeError):
        put(9, "UNMEASURED", [], "ROOT_POLICY_UNREAD")

    # 10 24 h acceptance
    if rp is None:
        put(10, "UNMEASURED", ["RELEASE_PIPELINE_PROOF.json"], "SOURCE_STALE_OR_ABSENT")
    else:
        proof = rp.get("autonomy_proof") or {}
        v = proof.get("verdict")
        put(10, "MET" if v == "PROVEN" else "UNMEASURED" if v in (None, "UNMEASURED")
            else "NOT_MET", ["RELEASE_PIPELINE_PROOF.json"],
            None if v == "PROVEN" else f"ACCEPTANCE_{v}",
            consecutive_automatic=proof.get("consecutive_automatic_deployments"),
            hours_since_human_touch=proof.get("hours_since_human_touch"))  # fmt: skip

    rows.sort(key=lambda r: r["point"])
    counts = {s: sum(r["status"] == s for r in rows) for s in ("MET", "NOT_MET", "UNMEASURED")}
    return {
        "at": now.isoformat(timespec="seconds"),
        "autonomous": counts["MET"] == 10,
        "counts": counts,
        "blockers": [{"point": r["point"], "blocker": r["blocker"]} for r in rows if r["blocker"]],
        "points": rows,
    }


def main(argv: list[str] | None = None, clock: Callable[[], datetime] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--reports", type=Path, default=REPORTS)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--print", action="store_true")
    a = ap.parse_args(argv)
    rep = score((clock or (lambda: datetime.now(UTC)))(), a.reports)
    text = json.dumps(rep, indent=1)
    if a.print:
        print(text)
        return 0
    out = a.out or a.reports / OUT.name
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    tmp.write_text(text + "\n", encoding="utf-8")
    tmp.replace(out)
    c = rep["counts"]
    print(
        f"autonomy conformance: {c['MET']}/10 MET, {c['NOT_MET']} NOT_MET, {c['UNMEASURED']} UNMEASURED"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
