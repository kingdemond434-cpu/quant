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

import contextlib
import json
import re
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
    n_grave = (sum(1 for ln in gy.read_text("utf-8").splitlines() if ln.startswith("| "))
               if gy.exists() else 0)

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


def check_self_application(defects) -> None:
    """Each of these encodes a max-fix the principal forced this session, as a REGRESSION guard.
    His pressure, made permanent: a future edit that undoes any becomes a same-day defect."""
    orgs = ["run_cro_ai.sh", "run_frontier_miner.sh", "run_prospector_dig.sh",
            "run_litminer_dig.sh", "run_dataaxis_dig.sh", "run_blindrediscovery_dig.sh"]
    for name in orgs:
        fp = ROOT / "ops" / name
        if not fp.exists():
            defects.append((f"organ-missing-{name}", f"organ script {name} vanished"))
            continue
        txt = fp.read_text("utf-8", errors="ignore")
        if "claude" in txt and "-p " in txt:
            if "--effort" not in txt:
                defects.append((f"effort-dropped-{name}",
                                f"{name}: claude call lost its --effort flag (max-reasoning "
                                "regressed to CLI default) -- re-add xhigh"))
            if "--append-system-prompt" not in txt and "_DOCTRINE" not in txt:
                defects.append((f"doctrine-dropped-{name}",
                                f"{name}: lost the principal-doctrine injection "
                                "(--append-system-prompt \"$_DOCTRINE\") -- the max-push stance "
                                "is no longer in this organ"))
    # cost-censorship must never creep back into the advisory layer
    for mp in (ROOT / "prompts/panel_missions").glob("*.txt"):
        if mp.stem == "maximization":
            continue  # legitimately quotes fossils as the anti-patterns it hunts
        t = mp.read_text("utf-8", errors="ignore").lower()
        for fossil in ("worthless", "$1/mo", "at most rare one-off cheap"):
            if fossil in t and "not worthless" not in t:
                # 'worthless' is allowed only in the sanctioned "a recommendation ignoring
                # STRUCTURAL constraints is worthless" phrasing; flag other reappearances
                if fossil == "worthless" and "structural" in t:
                    continue
                defects.append((f"cost-censorship-{mp.stem}",
                                f"panel mission {mp.name}: cost-self-censorship language "
                                f"'{fossil}' reappeared -- money-recs must stay proposable"))
    # recorder scope + liveness -- measure the GROUND-TRUTH tape, not the source code.
    # Until 2026-07-23 this regex-scanned run_recorder.py for a literal `_SYMBOLS = (...)`
    # tuple; gap #39 (2026-07-22) made _SYMBOLS a dynamic expression, so the regex matched
    # nothing, read 0, and FALSE-fired "dropped to 0" while 30 symbols were actively
    # recording. Counting the symbol directories that received a fresh write is the true
    # breadth measure AND catches a silent write-stall the source regex could never see --
    # the desk's own "heartbeat liveness != data liveness" lesson applied to the breadth
    # check (a stalled recorder keeps a fresh heartbeat but stops writing files).
    fut_root = ROOT / "data/moat/fut"
    if fut_root.exists():
        cutoff = time.time() - 1800.0   # a symbol counts only if written in the last 30 min
        live = sum(1 for d in fut_root.iterdir()
                   if d.is_dir() and any(f.stat().st_mtime > cutoff
                                         for f in d.glob("*.jsonl.gz")))
        if live < 20:
            defects.append(("recorder-scope-shrank",
                            f"recorder futures tape has {live} symbols written in the last "
                            "30min (expansion floor is 20) -- forward-tape breadth regressed "
                            "or the recorder stalled"))
    # bybit second-venue recorder must still exist
    if not (ROOT / "scripts/run_recorder_bybit.py").exists():
        defects.append(("bybit-recorder-gone", "second-venue (bybit) recorder script removed -- "
                        "cross-venue tape breadth lost"))
    # CI GATE must be GREEN -- a red desk-wide gate is the safety net down for everyone and
    # sat UNDETECTED for 81h (2026-07-22..23: a stale deadman test failed at HEAD while the
    # brain cycle that runs run_ci was quota-dead, so nothing surfaced the red). run_ci writes
    # data/.ci_last_run.json on every run; surface a red result mechanically so it enters the
    # 48h escalation path instead of hiding until a human notices.
    ci_marker = ROOT / "data/.ci_last_run.json"
    if ci_marker.exists():
        with contextlib.suppress(OSError, json.JSONDecodeError):
            ci = json.loads(ci_marker.read_text("utf-8"))
            if ci.get("ok") is False:
                defects.append(("ci-gate-red",
                                f"last CI run ({ci.get('ts')}) was RED -> {ci.get('failed')}; "
                                "the desk-wide safety gate is down. Run scripts/run_ci.py + fix"))


def check_dig_depth(defects) -> None:
    """Depth guard: a substantial dig log that shows NO depth markers (never mined a reply
    chain, followed a fork, or chased a citation) is breadth-theater -- flag it. Depth quality
    ultimately shows in output and is judged by red-team/maximization; this catches the gross
    wide-and-shallow case mechanically."""
    markers = ("repl", "comment", "thread", "fork", "citation", "issue", "discussion",
               ">=2", "deep", "exhaust", "debunk")
    for pat in ("frontier_*.log", "dataaxis_*.log", "prospector_*.log", "litminer_*.log"):
        logs = sorted(LOGS.glob(pat), key=lambda p: p.stat().st_mtime, reverse=True)
        if not logs:
            continue
        newest = logs[0]
        _mand = ROOT / "data/depth_mandate_baseline"
        if not _mand.exists():
            _mand.write_text(str(NOW))
        try:
            _base = float(_mand.read_text().strip())
        except Exception:
            _base = NOW
        if newest.stat().st_mtime < _base:
            continue                                  # pre-mandate dig -- not judged
        if (NOW - newest.stat().st_mtime) > 4 * 86400:
            continue                                  # stale digs handled by check_organs
        if newest.stat().st_size < 1500:
            continue                                  # stub/quota-death handled elsewhere
        txt = newest.read_text("utf-8", errors="ignore").lower()
        hits = sum(1 for m in markers if m in txt)
        if hits < 2:
            defects.append((f"dig-shallow-{newest.stem}",
                            f"{newest.name}: substantial dig with <2 depth markers "
                            f"({hits}) -- breadth-theater, no reply/fork/citation mining "
                            "evident. Depth mandate not honored."))


def check_interrogation(defects) -> None:
    """The last successful brain cycle must show evidence it ran the self-interrogation battery.
    A cycle that did not probe is a cycle that trusted itself -- the exact failure this catches.
    Only judged on cycles that ran AFTER the protocol existed."""
    base_f = ROOT / "data/interrogation_baseline"
    if not base_f.exists():
        base_f.write_text(str(NOW))
        return
    try:
        base = float(base_f.read_text().strip())
    except Exception:
        return
    cyc = [p for p in LOGS.glob("2026*_*.log")
           if p.stat().st_mtime >= base and p.stat().st_size >= 2000]
    if not cyc:
        return                                        # no post-protocol successful cycle yet
    newest = max(cyc, key=lambda p: p.stat().st_mtime)
    txt = newest.read_text("utf-8", errors="ignore").lower()
    if not any(k in txt for k in ("interrogat", "probe", "verified with a fresh read",
                                  "self-interrog", "angle")):
        defects.append(("cycle-skipped-interrogation",
                        f"{newest.name}: last successful cycle shows no self-interrogation "
                        "evidence -- it trusted itself instead of probing. Protocol not honored."))


def check_generation(defects) -> None:
    """Hypothesis testing is the primary output. If SUCCESSFUL brain cycles have run since a
    baseline but last_live_generate has not advanced, generation is being skipped -- escalate.
    Also flags the simple case: generation owed and long-stale."""
    cs = _j(ROOT / "data/cadence_state.json", {})
    last_gen = cs.get("last_live_generate") or cs.get("gen_done_fred_macro")
    # successful cycles since a fixed watch baseline
    base_f = ROOT / "data/generation_watch_baseline"
    if not base_f.exists():
        base_f.write_text(str(NOW))
    try:
        base = float(base_f.read_text().strip())
    except Exception:
        base = NOW
    good_cycles = [p for p in LOGS.glob("2026*_*.log")
                   if p.stat().st_mtime >= base and p.stat().st_size >= 2000]
    if not good_cycles:
        return                                        # no successful cycle yet -- quota, not skip
    newest_cycle = max(p.stat().st_mtime for p in good_cycles)
    gen_ts = 0.0
    if last_gen:
        with contextlib.suppress(Exception):
            gen_ts = datetime.fromisoformat(last_gen).timestamp()
    # a successful cycle ran AFTER the last generation -> generation was skipped
    if newest_cycle > gen_ts + 3600:
        defects.append(("generation-skipped",
                        f"a successful brain cycle ran but last_live_generate has not advanced "
                        f"(last gen {last_gen}) -- hypothesis testing, the desk's PRIMARY output, "
                        "is being crowded out by meta-duties. Generation-first duty not honored."))


def check_self_sufficiency(defects) -> None:
    """The meta-check: is the desk finding its own gaps, or is the principal still doing it?
    Reads the blind-spot ledger; if over the recent window the principal is the primary finder,
    the whole maximization apparatus is not yet working -- the top-level defect."""
    lg = ROOT / "data/blind_spot_ledger.jsonl"
    if not lg.exists():
        return
    rows = []
    for line in lg.read_text("utf-8").splitlines():
        with contextlib.suppress(Exception):
            rows.append(json.loads(line))
    live = [r for r in rows if not r.get("baseline")]  # judge post-baseline gaps only
    if len(live) < 8:
        return                                          # not enough signal yet
    by = {"self": 0, "guard": 0, "principal": 0}
    for r in live:
        by[r.get("origin", "principal")] = by.get(r.get("origin", "principal"), 0) + 1
    if by["principal"] > by["self"] + by["guard"]:
        defects.append(("system-not-self-sufficient",
                        f"blind-spot ledger: principal still the primary gap-finder "
                        f"({by['principal']} vs self {by['self']} + guard {by['guard']}) -- the "
                        "maximization system is not yet doing its job. TOP defect."))


def _blind_rows_window(days=7):
    lg = ROOT / "data/blind_spot_ledger.jsonl"
    if not lg.exists():
        return []
    cut = NOW - days * 86400
    out = []
    for line in lg.read_text("utf-8").splitlines():
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("baseline"):
            continue
        try:
            if datetime.fromisoformat(r["ts"]).timestamp() >= cut:
                out.append(r)
        except Exception:
            pass
    return out


def check_rubberstamp_detector(defects) -> None:
    """Signature: >=3 successful cycles CLAIMED interrogation, found ZERO gaps themselves, yet
    the principal found >=2 in the same window. That is probing theater. Auto-activate the
    enforcement, page, and log -- the desk deciding for itself that it needs the higher bar."""
    flag = ROOT / "data/ANTIRUBBERSTAMP_ACTIVE"
    if flag.exists():
        return                                        # already active
    cyc = [p for p in LOGS.glob("2026*_*.log") if p.stat().st_size >= 2000
           and (NOW - p.stat().st_mtime) < 7 * 86400]
    interrogated = 0
    for p in cyc:
        t = p.read_text("utf-8", errors="ignore").lower()
        if any(k in t for k in ("interrogat", "probe", "self-interrog")):
            interrogated += 1
    rows = _blind_rows_window(7)
    self_ct = sum(1 for r in rows if r.get("origin") == "self")
    princ_ct = sum(1 for r in rows if r.get("origin") == "principal")
    if interrogated >= 3 and self_ct == 0 and princ_ct >= 2:
        flag.write_text(f"auto-activated {datetime.now(tz=UTC).isoformat()}: {interrogated} "
                        f"cycles claimed interrogation, 0 self-gaps, {princ_ct} principal-gaps "
                        "-- rubber-stamp signature")
        defects.append(("rubberstamp-detected-ACTIVATED",
                        f"RUBBER-STAMP SIGNATURE: {interrogated} cycles claimed to interrogate but "
                        f"found 0 gaps while the principal found {princ_ct}. Anti-rubber-stamp "
                        "enforcement AUTO-ACTIVATED -- cycles must cite named reads per angle."))
        try:
            import subprocess
            subprocess.run(["python", "scripts/blind_spot.py", "log", "--origin", "guard",
                            "--summary", "auto-activated anti-rubber-stamp: interrogation was "
                            "probing theater (claimed, found nothing, principal found real gaps)"],
                           cwd=str(ROOT), timeout=20)
        except Exception:
            pass


def check_rubberstamp_enforcement(defects) -> None:
    """Active only when the flag exists: the newest successful cycle must show NAMED VERIFIED
    READS (file-path citations proving it actually looked), not bare 'verified' prose."""
    flag = ROOT / "data/ANTIRUBBERSTAMP_ACTIVE"
    if not flag.exists():
        return
    cyc = [p for p in LOGS.glob("2026*_*.log")
           if p.stat().st_size >= 2000 and (NOW - p.stat().st_mtime) < 2 * 86400]
    if not cyc:
        return
    newest = max(cyc, key=lambda p: p.stat().st_mtime)
    t = newest.read_text("utf-8", errors="ignore")
    cites = len(set(re.findall(r"[\w/]+\.(?:py|json|md|sh|txt)", t)))
    if cites < 5:
        defects.append(("rubberstamp-enforced",
                        f"{newest.name}: anti-rubber-stamp ACTIVE but the cycle cites only {cites} "
                        "named reads -- interrogation lacks verified-read evidence. Cite the "
                        "specific file+value per probe angle, do not rubber-stamp."))


def check_clock_saturation(defects) -> None:
    """OBJECTIVE #2 CLOCK-SATURATION DUTY (principal 2026-07-23), made mechanical.

    Every VERIFIED data axis must have a pre-registered hypothesis ACCRUING within 7 days. An
    empty forward-validation slot is idle capital's research twin: the axis was ingested (real
    cost paid) but is generating zero evidence, so the discovery objective is silently stalled.

    This duty shipped as prompt text only -- and prompt-only duties are aspirations. The desk's
    recursion rule is that every manual probe becomes a standing automatic check, so it is fenced
    here. Axes are read from the Bronze lake (what was actually ingested, not what a doc claims);
    clocks are read from cadence_state gen_done_* (what actually ran)."""
    bronze = ROOT / "data/lake/bronze"
    cad_p = ROOT / "data/cadence_state.json"
    if not bronze.exists() or not cad_p.exists():
        return
    try:
        cad = json.loads(cad_p.read_text("utf-8"))
    except Exception:
        return
    # INPUT STORES are not axes: raw price/metrics lakes feed constructions but cannot carry
    # a hypothesis themselves (the constructions built FROM them do). Excluding them keeps this
    # check pointed at genuinely idle research axes instead of manufacturing false defects.
    _input_stores = {"futclose_daily", "oi_ls_daily", "fx", "index", "crypto", "binance_metrics"}
    axes = sorted(d.name for d in bronze.iterdir() if d.is_dir() and d.name not in _input_stores)
    if not axes:
        return
    stale = []
    for ax in axes:
        ts = cad.get(f"gen_done_{ax}") or cad.get(f"gen_done_{ax}_family")
        if not ts:
            stale.append(f"{ax}(never)")
            continue
        try:
            age_d = (NOW - datetime.fromisoformat(ts).timestamp()) / 86400.0
            if age_d > 7:
                stale.append(f"{ax}({age_d:.0f}d)")
        except Exception:
            stale.append(f"{ax}(unparsable)")
    if stale:
        defects.append((
            "clock-saturation",
            f"OBJECTIVE #2 breach: {len(stale)}/{len(axes)} verified axes have NO hypothesis "
            f"accruing within 7d -- {', '.join(stale[:8])}"
            f"{' ...' if len(stale) > 8 else ''}. An empty forward clock is idle research "
            "capital: pre-register a hypothesis on each, or ledger why the axis is not yet "
            "testable (e.g. forward history under the gauntlet minimum)."))


def check_vendor_replacement(defects) -> None:
    """FREE-ALTERNATIVES-TO-PAID enforcement (principal 2026-07-24). The dataaxis dig's pillar 6
    mandates decomposing every paid vendor into a free reconstruction with a ground-truth diff;
    this check makes that output rot-proof: entries must be complete, UNVERIFIED grades must not
    sit while a daily dig runs, and the free-hunt itself must keep landing updates."""
    ump = ROOT / "data/data_universe_map.json"
    if not ump.exists():
        defects.append(("vendor-replacement", "data_universe_map.json MISSING"))
        return
    try:
        d = json.loads(ump.read_text("utf-8"))
    except Exception as e:
        defects.append(("vendor-replacement", f"universe map unreadable: {e!r}"))
        return
    vr = (d.get("sources") or {}).get("vendor_replacement") or []
    if not isinstance(vr, list) or not vr:
        defects.append(("vendor-replacement",
                        "no vendor_replacement entries -- the free-alternatives hunt has "
                        "recorded zero paid-vendor decompositions"))
        return
    for e in vr:
        v = str(e.get("vendor", "?"))[:40]
        if not e.get("free_path"):
            defects.append(("vendor-replacement",
                            f"{v}: NO free_path -- a paid product with no owned reconstruction"))
        if not e.get("ground_truth_for_diff"):
            defects.append(("vendor-replacement",
                            f"{v}: NO ground_truth_for_diff -- verify-don't-trust is impossible; "
                            "find a free sample/reference to diff the reconstruction against"))
        g = str(e.get("grade", "")).lower()
        if "unverified" in g:
            defects.append(("vendor-replacement",
                            f"{v}: grade UNVERIFIED while the free-data dig runs DAILY -- "
                            "verify the free path this cycle or ledger why it cannot be"))
    # the hunt itself must keep landing: daily dig -> map bookkeeping must move
    try:
        lfd = datetime.fromisoformat(str(d.get("last_free_dig")))
        age_d = (NOW - lfd.timestamp()) / 86400.0
        if age_d > 3:
            defects.append(("vendor-replacement",
                            f"last_free_dig {age_d:.1f}d old while the data-axis dig is DAILY -- "
                            "the free-alternatives hunt is not landing updates to the map"))
    except Exception:
        defects.append(("vendor-replacement", "last_free_dig missing/unparsable in universe map"))


def main() -> None:
    defects: list[tuple[str, str]] = []
    for label, fn in [("organs", check_organs), ("stubs", check_stub_deaths),
                      ("panel", check_panel), ("coverage", check_coverage),
                      ("findings", check_findings), ("idle", check_idle_capability),
                      ("directives", check_directives), ("verify", check_verify_lag),
                      ("blind", check_blind_trigger),
                      ("self-application", check_self_application),
                      ("dig-depth", check_dig_depth),
                      ("interrogation", check_interrogation),
                      ("generation", check_generation),
                      ("clock-saturation", check_clock_saturation),
                      ("vendor-replacement", check_vendor_replacement),
                      ("self-sufficiency", check_self_sufficiency),
                      ("rs-detect", check_rubberstamp_detector),
                      ("rs-enforce", check_rubberstamp_enforcement)]:
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
