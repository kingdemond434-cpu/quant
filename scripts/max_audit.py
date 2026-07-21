#!/usr/bin/env python3
"""DAILY MAXIMIZATION SWEEP (principal standing order 2026-07-21).

The principal kept discovering -- only by personally pressuring the system -- that organs were
quietly below potential: audits seeing 1% of the code, prompts carrying 40x-stale budget
figures, quotas behaving as ceilings, credits sitting idle, miners dying silently on quota.
This script institutionalizes that pressure as a DAILY MECHANICAL SWEEP: pure filesystem
reads, no LLM cost, run by cron and at every brain-cycle start.

Layers above it: every 3-day panel carries a full-system recommendations sweep, and the
zero-based MAXIMIZATION panel mission re-derives each organ's ceiling from scratch on rotation.

Rules of the sweep:
 - a below-max state is a DEFECT unless acknowledged with a reason AND an expiry (max 30d) in
   data/max_audit_acks.json -- no permanent burial, ever
 - defects persisting >48h un-acked ESCALATE to the principal page (PRINCIPAL_ACTION.md):
   nothing can sit below max for more than two days without either being fixed or him knowing
 - one broken check must never kill the sweep (every check is fenced)
"""
from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOGS = ROOT / "data/cro_ai_logs"
REPORT = ROOT / "data/max_audit_report.json"
ACKS = ROOT / "data/max_audit_acks.json"
PA = ROOT / "data/PRINCIPAL_ACTION.md"

ESCALATE_H = 48.0
NOW = time.time()

# organ -> (glob, min_bytes_for_success, max_age_hours)
ORGANS = {
    "brain-cycle":      ("2026*_*.log",              2000, 8.0),
    "frontier-en":      ("frontier_en_*.log",        1500, 36.0),
    "frontier-cn":      ("frontier_cn_*.log",        1500, 36.0),
    "frontier-ru":      ("frontier_ru_*.log",        1500, 36.0),
    "frontier-kr":      ("frontier_kr_*.log",        1500, 36.0),
    "frontier-jp":      ("frontier_jp_*.log",        1500, 36.0),
    "frontier-ar":      ("frontier_ar_*.log",        1500, 36.0),
    "frontier-br":      ("frontier_br_*.log",        1500, 36.0),
    "dataaxis-dig":     ("dataaxis_*.log",           1500, 96.0),
    "litminer-dig":     ("litminer_*.log",           1500, 216.0),
    "prospector-dig":   ("prospector_*.log",         1500, 216.0),
    "blindrediscovery": ("blindrediscovery_*.log",   1500, 840.0),
}


def _j(path: Path, default):
    try:
        return json.loads(path.read_text("utf-8"))
    except Exception:
        return default


def _fenced(fn, defects, label):
    try:
        fn(defects)
    except Exception as e:
        defects.append((f"sweep-broken-{label}", f"max_audit check '{label}' itself failed: "
                        f"{e!r} -- a blind checker is a defect"))


def check_organs(defects) -> None:
    for organ, (pat, min_b, max_h) in ORGANS.items():
        ok = [p for p in LOGS.glob(pat) if p.stat().st_size >= min_b]
        if not ok:
            defects.append((f"organ-never-{organ}",
                            f"{organ}: NO successful run on record (pattern {pat}, "
                            f"success >= {min_b}b) -- organ has never fired or always dies"))
            continue
        age_h = (NOW - max(p.stat().st_mtime for p in ok)) / 3600
        if age_h > max_h:
            defects.append((f"organ-stale-{organ}",
                            f"{organ}: last SUCCESSFUL run {age_h:.0f}h ago "
                            f"(cadence expects <= {max_h:.0f}h) -- silently degraded"))


def check_stub_deaths(defects) -> None:
    stubs = [p for p in LOGS.glob("*.log")
             if p.stat().st_size < 600 and (NOW - p.stat().st_mtime) < 48 * 3600]
    if len(stubs) >= 3:
        defects.append(("stub-deaths",
                        f"{len(stubs)} organ runs died at birth in 48h (<600b logs -- "
                        f"auth/quota deaths): {', '.join(p.name for p in stubs[:6])}"))


def check_panel(defects) -> None:
    log = ROOT / "data/external_panel_log.jsonl"
    if not log.exists():
        defects.append(("panel-never", "external panel has never logged a run"))
        return
    last = ""
    with log.open() as f:
        for line in f:
            last = line
    ts = json.loads(last).get("ts", "")
    age_h = (datetime.now(tz=UTC) - datetime.fromisoformat(ts)).total_seconds() / 3600
    if age_h > 96:
        defects.append(("panel-stale",
                        f"external panel last ran {age_h:.0f}h ago (3d cadence + slack = 96h) "
                        "-- review capability is down (credits? crash?)"))


def check_coverage(defects) -> None:
    m = _j(ROOT / "data/audit_coverage.json", {})
    if not m:
        defects.append(("coverage-missing", "audit_coverage.json absent -- coverage untracked"))
        return
    files = m.get("files", {})
    stale_risk = 0
    for rec in files.values():
        if rec.get("review_class") == 1:
            la = rec.get("last_audited")
            if not la or (datetime.now(tz=UTC) - datetime.fromisoformat(la)).days > 14:
                stale_risk += 1
    if stale_risk:
        defects.append(("coverage-risk-stale",
                        f"{stale_risk} RISK-class (money path) files past their 14d review "
                        "floor -- the exact class that must never go stale"))
    if int(m.get("code_budget_chars", 999999)) <= 40000:
        defects.append(("coverage-budget-floor",
                        "adaptive review payload pinned at its 40k floor -- seats are blanking "
                        "repeatedly; coverage is crawling"))
    for seat, n in (m.get("seat_blanks") or {}).items():
        if int(n) >= 3:
            defects.append((f"seat-chronic-{seat.split('/')[-1]}",
                            f"panel seat {seat} blanked {n}x -- chronic capacity failure, "
                            "swap-candidate with evidence"))


def check_findings(defects) -> None:
    d = _j(ROOT / "data/findings_ledger.json", {})
    old = [f for f in d.get("findings", [])
           if f.get("ruling") == "accepted" and not f.get("fixed")
           and (datetime.now(tz=UTC) - datetime.fromisoformat(f["raised"])).days > 14]
    if old:
        ids = ", ".join(f["id"] for f in old[:5])
        defects.append(("findings-rotting",
                        f"{len(old)} ACCEPTED panel findings unfixed >14d ({ids}) -- the loop "
                        "the audit system exists for is open"))


def check_idle_capability(defects) -> None:
    if (ROOT / "data/secrets/databento.json").exists():
        cme = ROOT / "data/lake/bronze/cme"
        pulled = list(cme.glob("*.csv")) if cme.exists() else []
        if not pulled:
            defects.append(("idle-databento",
                            "Databento key verified but ZERO CME data pulled to Bronze -- "
                            "one-time credits idling"))
    vl = ROOT / "docs/research/video_locked_log.md"
    if vl.exists():
        stale_rows = 0
        for line in vl.read_text("utf-8").splitlines():
            if line.startswith("| 2026"):
                try:
                    d = datetime.fromisoformat(line.split("|")[1].strip())
                    if (datetime.now(tz=UTC) - d.replace(tzinfo=UTC)).days > 7:
                        stale_rows += 1
                except Exception:
                    pass
        if stale_rows:
            defects.append(("video-locked-unactioned",
                            f"{stale_rows} video-locked mechanisms logged >7d with no unlock "
                            "decision -- evidence gate met but purchase page never made?"))


def check_directives(defects) -> None:
    """Time-boxed work orders: registered with a due date; past-due = defect. This is how
    'the brain will do it next cycle' gets teeth instead of drifting forever."""
    for d in _j(ROOT / "data/max_audit_directives.json", []):
        if d.get("due", "9999") < datetime.now(tz=UTC).isoformat():
            defects.append((f"directive-overdue-{d['id']}",
                            f"work order '{d['id']}' past due {d['due'][:10]}: {d['msg']}"))


def check_verify_lag(defects) -> None:
    """The verify pass audits the CRO's own triage -- and the CRO fires it. If triage-bearing
    panels keep running without a verify run following, the auditee is skipping his auditor."""
    log = ROOT / "data/external_panel_log.jsonl"
    if not log.exists():
        return
    last_triage, last_verify = None, None
    with log.open() as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("mission") == "verify":
                last_verify = r.get("ts")
            elif r.get("mission") in ("audit", "tier1", "premortem", "maximization"):
                last_triage = r.get("ts")
    if last_triage and (not last_verify or last_verify < last_triage):
        age_h = (datetime.now(tz=UTC) - datetime.fromisoformat(last_triage)
                 ).total_seconds() / 3600
        if age_h > 48:
            defects.append(("verify-pass-skipped",
                            f"last triage-bearing panel ({last_triage[:16]}) has had NO verify "
                            "pass after it for >48h -- the auditee is skipping his auditor"))


def check_blind_trigger(defects) -> None:
    """Blind Rediscovery is state-driven, not clock-driven: fire it early when the desk has
    materially new internal raw material (data axes / graveyard entries) since its last run."""
    state = _j(ROOT / "data/cadence_state.json", {})
    last = state.get("last_blind_rediscovery")
    seen = _j(ROOT / "data/blind_trigger_baseline.json", {})

    umap = _j(ROOT / "data/data_universe_map.json", {})
    srcs = umap.get("sources", {})
    n_sources = len(srcs) if isinstance(srcs, (dict, list)) else 0
    gy = ROOT / "docs/graveyard.md"
    n_grave = sum(1 for l in gy.read_text("utf-8").splitlines() if l.startswith("| ")) if gy.exists() else 0

    base_src = int(seen.get("sources", 0))
    base_grave = int(seen.get("graveyard", 0))
    d_src, d_grave = n_sources - base_src, n_grave - base_grave

    # thresholds: enough NEW material that first-principles invention has fresh ground
    if d_src >= 5 or d_grave >= 10:
        defects.append(("blind-rediscovery-due-by-state",
                        f"internal state changed materially since last blind-rediscovery "
                        f"({last or 'never'}): +{d_src} data sources, +{d_grave} graveyard "
                        "entries. Fire ops/run_blindrediscovery_dig.sh -- fresh-eyes invention "
                        "has new raw material; do not wait for the monthly floor."))


def main() -> None:
    defects: list[tuple[str, str]] = []
    for label, fn in [("organs", check_organs), ("stubs", check_stub_deaths),
                      ("panel", check_panel), ("coverage", check_coverage),
                      ("findings", check_findings), ("idle", check_idle_capability),
                      ("directives", check_directives), ("verify", check_verify_lag),
                      ("blind", check_blind_trigger)]:
        _fenced(fn, defects, label)

    acks = _j(ACKS, {})
    live, acked = [], []
    for did, msg in defects:
        a = acks.get(did)
        if a and a.get("until", "") > datetime.now(tz=UTC).isoformat():
            acked.append((did, a.get("reason", "")))
        else:
            live.append((did, msg))

    prev = _j(REPORT, {})
    first_seen = prev.get("first_seen", {})
    now_iso = datetime.now(tz=UTC).isoformat()
    first_seen = {d: t for d, t in first_seen.items() if d in {x for x, _ in live}}
    for did, _ in live:
        first_seen.setdefault(did, now_iso)
    REPORT.write_text(json.dumps(
        {"ran": now_iso, "live": [{"id": d, "msg": m} for d, m in live],
         "acked": [d for d, _ in acked], "first_seen": first_seen}, indent=1), "utf-8")

    print(f"MAX-AUDIT {now_iso[:16]}  live defects: {len(live)}  acked: {len(acked)}")
    for did, msg in live:
        age_h = (datetime.now(tz=UTC) - datetime.fromisoformat(first_seen[did])
                 ).total_seconds() / 3600
        print(f"  [{age_h:>5.1f}h] {did}: {msg}")
    for did, reason in acked:
        print(f"  [ acked] {did}: {reason}")

    overdue = [(d, m) for d, m in live
               if (datetime.now(tz=UTC) - datetime.fromisoformat(first_seen[d])
                   ).total_seconds() / 3600 > ESCALATE_H]
    if overdue:
        existing = PA.read_text("utf-8") if PA.exists() else ""
        if "MAX-AUDIT ESCALATION" not in existing:
            block = ("\nMAX-AUDIT ESCALATION: the following below-max states persisted >48h "
                     "without fix or acknowledged reason -- the desk is running under "
                     "potential and self-healing has not resolved it:\n" +
                     "".join(f"  - {d}: {m}\n" for d, m in overdue[:8]))
            PA.write_text(existing + block, "utf-8")
            print(f"ESCALATED to principal page: {len(overdue)} defect(s) >48h")


if __name__ == "__main__":
    main()
