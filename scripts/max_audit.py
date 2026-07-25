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
import sys
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


def _acquired_axes() -> list[str]:
    """The ingested-data surface as NAMES (not a count): bronze lake stores + forward clocks."""
    names: list[str] = []
    lake = ROOT / "data/lake/bronze"
    if lake.exists():
        names += [p.name for p in lake.iterdir() if p.is_dir()]
    for pat in ("data/*_premium.jsonl", "data/*_supply.jsonl", "data/*_activity.jsonl"):
        names += [p.stem for p in ROOT.glob(pat)]
    return list(dict.fromkeys(names))  # de-dup, preserve order


def _converted_axes() -> list[str]:
    """Every axis the desk has actually CONVERTED, from the real conversion artifacts.

    An axis is 'converted' (covered) if a tested-hypothesis artifact exists for it -- regardless of
    outcome (tested-and-rejected is still converted; the graveyard is coverage). Three sources, all
    the desk's real conversion record, so the coverage metric credits work that genuinely happened
    instead of only the new --axis tag: (1) forward-clock shadows (web/axis_shadows.json), (2)
    reconstructed held-out OOS reports (reports/reconstructed_oos/*.json), (3) research_memory
    hypotheses tagged with --axis. Lowercased for tolerant matching against acquired-axis names.
    """
    tags: set[str] = set()
    # (1) forward-clock shadow registry -- each axis under a live forward clock
    shadows = _j(ROOT / "web/axis_shadows.json", {})
    for rec in (shadows.get("axes", []) if isinstance(shadows, dict) else []):
        ax = rec.get("axis") if isinstance(rec, dict) else None
        if isinstance(ax, str) and ax.strip():
            tags.add(ax.strip().lower())
    # (2) reconstructed held-out OOS reports -- each backfilled + diff-verified axis
    oos_dir = ROOT / "reports/reconstructed_oos"
    if oos_dir.exists():
        for rep in oos_dir.glob("*.json"):
            tags.add(rep.stem.lower())
            d = _j(rep, {})
            for r in (d.get("results", []) if isinstance(d, dict) else []):
                s = r.get("sleeve") if isinstance(r, dict) else None
                if isinstance(s, str) and s.strip():
                    tags.add(s.strip().lower())
    # (3) research_memory hypotheses tagged with the axis they screen (the --axis flag)
    try:
        import sqlite3
        con = sqlite3.connect(str(ROOT / "data/sor_research.sqlite"))
        for (mj,) in con.execute(
            "SELECT metrics_json FROM research_memory WHERE category != 'method' "
            "AND metrics_json IS NOT NULL"
        ):
            try:
                axis = (json.loads(mj) or {}).get("axis")
            except Exception:
                axis = None
            if isinstance(axis, str) and axis.strip():
                tags.add(axis.strip().lower())
        con.close()
    except Exception:
        pass
    return sorted(tags)


def _trial_mechanisms() -> list[str]:
    """The trials-ledger ``family`` column (the mechanism key) across candidate runtime DBs.

    Feeds the effective (independence-clustered) trial count. Robust to the ledger living in any of
    the sor databases; returns [] if unreachable so the monitor degrades to its prior behavior.
    """
    import sqlite3
    for name in ("sor_research.sqlite", "sor.sqlite", "sor_demo.sqlite", "sor_live.sqlite"):
        db = ROOT / "data" / name
        if not db.exists():
            continue
        try:
            con = sqlite3.connect(str(db))
            rows = con.execute("SELECT family FROM trials_ledger").fetchall()
            con.close()
            if rows:
                return [str(r[0]) for r in rows if r[0] is not None]
        except Exception:
            continue
    return []


def _fenced(fn, defects, label):
    try:
        fn(defects)
    except Exception as e:
        defects.append((f"sweep-broken-{label}", f"max_audit check '{label}' itself failed: "
                        f"{e!r} -- a blind checker is a defect"))


# ARTIFACT PARITY (2026-07-25): claude writes deliverables via FILE TOOLS, so a SUCCESSFUL organ
# run can leave only the shell's ~58-byte start/exit header in its log. Judging production by log
# size alone made this sweep report 'organ never fired' on demonstrably working organs (the 07-25
# frontier dig wrote prospector_coverage.md at 13:37 while its log stayed 58b). An organ counts as
# having produced when its log is substantial OR a declared artifact advanced. Keep in sync with
# libs/ops/organ_catchup.py ORGANS.
ORGAN_ARTIFACTS: dict[str, tuple[str, ...]] = {
    "brain-cycle": ("data/decision_ledger.json", "docs/research/cadence_duties.md"),
    "dataaxis-dig": ("docs/research/data_axis_watchlist.md", "data/data_universe_map.json"),
    "prospector-dig": ("docs/research/prospector_watchlist.md",
                       "docs/research/prospector_coverage.md"),
    "litminer-dig": ("docs/research/improvement_inbox.md",),
    "frontier-en": ("docs/research/prospector_coverage.md",
                    "docs/research/search_operator_library.md"),
    "frontier-cn": ("docs/research/prospector_coverage.md",),
    "frontier-ru": ("docs/research/prospector_coverage.md",),
    "frontier-kr": ("docs/research/prospector_coverage.md",),
    "frontier-jp": ("docs/research/prospector_coverage.md",),
    "frontier-ar": ("docs/research/prospector_coverage.md",),
    "frontier-br": ("docs/research/prospector_coverage.md",),
}


def _artifact_age_h(organ: str) -> float:
    """Hours since this organ's freshest declared artifact advanced (inf if none)."""
    best = 0.0
    for rel in ORGAN_ARTIFACTS.get(organ, ()):
        try:
            best = max(best, (ROOT / rel).stat().st_mtime)
        except OSError:
            continue
    return (NOW - best) / 3600 if best else float("inf")


def check_organs(defects) -> None:
    for organ, (pat, min_b, max_h) in ORGANS.items():
        ok = [p for p in LOGS.glob(pat) if p.stat().st_size >= min_b]
        art_h = _artifact_age_h(organ)
        if not ok and art_h > max_h:
            defects.append((f"organ-never-{organ}",
                            f"{organ}: no substantial log (pattern {pat}, >= {min_b}b) AND no "
                            f"declared artifact written in {max_h}h -- organ has never fired or "
                            "always dies"))
            continue
        if not ok:
            continue                      # artifacts prove production; stub log is expected
        age_h = min((NOW - max(p.stat().st_mtime for p in ok)) / 3600, art_h)
        if age_h > max_h:
            defects.append((f"organ-stale-{organ}",
                            f"{organ}: last SUCCESSFUL run {age_h:.0f}h ago "
                            f"(cadence expects <= {max_h:.0f}h) -- silently degraded"))


# A real death SAYS so. A ~58b log is the normal signature of a SUCCESSFUL claude organ (it writes
# deliverables via file tools, so only the shell's start/exit header reaches the log) -- the old
# size-only rule reported 22 'deaths' in 48h while those organs were writing real artifacts.
_DEATH_MARKERS = ("out of usage credits", "session limit", "hit your limit",
                  "issue with the selected model", "auth", "not found", "traceback",
                  "permission denied", "refusing to send")


def check_stub_deaths(defects) -> None:
    dead = []
    for p in LOGS.glob("*.log"):
        try:
            if p.stat().st_size >= 600 or (NOW - p.stat().st_mtime) >= 48 * 3600:
                continue
            txt = p.read_text("utf-8", errors="ignore").lower()
        except OSError:
            continue
        if any(m in txt for m in _DEATH_MARKERS):
            dead.append(p)
    if len(dead) >= 3:
        defects.append(("stub-deaths",
                        f"{len(dead)} organ runs died at birth in 48h (log CONTENT names a quota/"
                        f"auth/model failure): {', '.join(p.name for p in dead[:6])}"))


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


def check_forensics_fresh(defects) -> None:
    """DAILY PnL/churn/loss analysis is GUARANTEED, not assumed (principal 2026-07-24): the
    trade-forensics probe (the mechanical version of the probes that found gaps #42/#43/#34)
    must have produced a fresh verdict within 26h, or the desk is flying without its daily
    bleed detection -- the exact silent-leak failure mode the integrity watch exists to kill."""
    fj = ROOT / "web/trade_forensics.json"
    if not fj.exists():
        defects.append(("forensics-stale", "web/trade_forensics.json MISSING -- daily "
                        "trade-class bleed analysis has never produced output"))
        return
    age_h = (NOW - fj.stat().st_mtime) / 3600.0
    if age_h > 26:
        defects.append(("forensics-stale",
                        f"trade_forensics.json {age_h:.0f}h old (>26h) -- the daily churn/"
                        "bleed/PnL analysis is not landing; check daily_research_cycle"))


def check_memory_hygiene(defects) -> None:
    """MEMORY layer fences (principal 2026-07-24): institutional memory must be written, fresh,
    and retrievable -- a memory system nobody writes to or that outgrows retrieval is theater.
    Found at audit time: research_memory had 0 rows ever while mission directives claim to write
    it; the brain memory index was a week stale and used the principal old name."""
    # (a) the brain's own memory index must stay fresh (it is the first thing cycles read)
    mi = ROOT / "ops/memory/MEMORY.md"
    if mi.exists():
        age_d = (NOW - mi.stat().st_mtime) / 86400.0
        if age_d > 7:
            defects.append(("memory-index-stale",
                            f"ops/memory/MEMORY.md {age_d:.0f}d old -- the brain memory index "
                            "must be refreshed weekly with current desk state (cycle duty)"))
    # (b) research_memory must actually be written by the analyst missions that cite it
    try:
        import sqlite3
        n = sqlite3.connect(str(ROOT / "data/sor_research.sqlite")).execute(
            "SELECT COUNT(*) FROM research_memory").fetchone()[0]
        if n == 0:
            defects.append(("research-memory-unused",
                            "research_memory has 0 rows EVER while mission directives claim "
                            "every analyst pass writes to it -- either write it (hypothesis ID + "
                            "economic logic + EV score per mission) or remove the claim"))
    except Exception:
        pass
    # (c) ledger bloat: append-only is sacred, but retrieval must survive growth
    lp = ROOT / "data/decision_ledger.json"
    if lp.exists() and lp.stat().st_size > 1_500_000:
        defects.append(("ledger-bloat",
                        f"decision_ledger.json {lp.stat().st_size/1e6:.1f}MB -- run the memory-"
                        "consolidation duty (archive-never-delete, index the archive) before "
                        "tail-reads go lossy"))


def check_prompt_layer(defects) -> None:
    """PROMPT-LAYER hygiene (principal 2026-07-24 prompt audit): the prompts are organs too.
    (a) Doctrine bloat: the doctrine is prepended to EVERY organ call; past ~16k chars the
    stacked supreme-blocks start diluting mission instructions -- consolidate, never just stack.
    (b) State-triggered prompt review: the 28d review cadence is calendar-based, but when the
    contract/doctrine change materially the review is due by STATE (the blind-rediscovery
    precedent) -- a week of unreviewed prompt mutations is how contradictions accrete."""
    doc = ROOT / "ops/principal_doctrine.txt"
    if doc.exists() and doc.stat().st_size > 16000:
        defects.append(("prompt-doctrine-bloat",
                        f"principal_doctrine.txt {doc.stat().st_size/1000:.1f}k chars (>16k) -- "
                        "consolidate the stacked axiom blocks into tighter prose (preserve every "
                        "commitment, cut the repetition); every organ pays this context"))
    try:
        cad = json.loads((ROOT / "data/cadence_state.json").read_text("utf-8"))
        last_rev = datetime.fromisoformat(cad["last_prompt_review"]).timestamp()
        contract = (ROOT / "ops/run_cro_ai.sh").stat().st_mtime
        doc_m = doc.stat().st_mtime if doc.exists() else 0
        newest_change = max(contract, doc_m)
        if newest_change > last_rev and (NOW - newest_change) / 86400.0 > 7:
            defects.append(("prompt-review-due-by-state",
                            "contract/doctrine changed materially since the last prompt review "
                            f"({cad['last_prompt_review'][:10]}) and the newest change is >7d "
                            "old -- run the prompt-review duty NOW (check for duty collisions, "
                            "stale numbers, contradictions), do not wait for the 28d floor"))
    except Exception:
        pass


def check_bnb_funded(defects) -> None:
    """BNB fee-burn is enabled (feeBurn:True) but only DISCOUNTS when BNB is held. Audit 2026-07-24:
    balance 0 -> the whole commission line was paid at rack rate while the desk believed the ~25%
    discount was active. feeBurn:True is STATE; a funded BNB balance is the OUTCOME that matters."""
    try:
        from libs.execution import binance_testnet as _fut
        bal = 0.0
        for b in _fut._signed("/fapi/v2/balance", {}):
            if b.get("asset") == "BNB":
                bal = float(b.get("balance", 0.0))
        if bal <= 0.0:
            defects.append(("bnb-burn-unfunded",
                            "fee-burn is ON (feeBurn:True) but BNB balance is 0 -- the ~25% "
                            "discount is INERT and commissions are paid at rack rate. Fund a small "
                            "BNB balance (or accept it as a testnet limitation and ledger why)."))
    except Exception:
        pass


def check_production(defects) -> None:
    """OUTCOME-LEVEL fence (principal 2026-07-24): does each scheduled organ actually PRODUCE its
    output artifact within cadence? State-freshness checks miss the class where a scheduler fires
    but nothing is produced (cron self-match), an organ runs but refuses to emit (panel
    sanitizer), or a duty is claimed but writes nothing (research_memory). Product artifacts, not
    state files -- state can be touched without producing."""
    import glob as _glob
    # (label, product glob, max_age_h, min_bytes). Products, not state files.
    manifest = [
        ("cron-cycle", "data/cro_ai_logs/2026*_????.log", 26, 2000),
        ("panel-verdicts", "data/panel_verdicts.jsonl", 96, 100),
        ("dataaxis-product", "docs/research/data_axis_watchlist.md", 30, 100),
        ("prospector-product", "docs/research/prospector_watchlist.md", 30, 100),
        ("litminer-product", "docs/research/*iterature*coverage*.md", 30, 50),
        ("frontier-product", "docs/research/prospector_coverage.md", 30, 100),
        ("crypto-factory", "web/autodiscovery_crypto.json", 30, 100),
        ("forensics", "web/trade_forensics.json", 30, 50),
    ]
    for label, pat, max_h, min_b in manifest:
        hits = [Path(q) for q in _glob.glob(str(ROOT / pat))]
        if not hits:
            defects.append(("production-missing",
                            f"{label}: NO product artifact exists ({pat}) -- the organ has never "
                            "produced output, only (maybe) been scheduled"))
            continue
        newest = max(hits, key=lambda q: q.stat().st_mtime)
        age_h = (NOW - newest.stat().st_mtime) / 3600.0
        sz = newest.stat().st_size
        if age_h > max_h:
            defects.append(("production-stale",
                            f"{label}: {newest.name} {age_h:.0f}h old (cad {max_h}h) "
                            "-- scheduled but not PRODUCING; verify the organ actually runs end-to-"
                            "end, not just that its timer/cron fires (the cron-self-match class)"))
        elif sz < min_b:
            defects.append(("production-stub",
                            f"{label}: product {newest.name} is {sz}b (<{min_b}b) -- ran but "
                            "produced a stub, not real output (the quota-stub / refuse class)"))
    # research_memory must GROW, not just be non-zero (the null-pipe class)
    try:
        import sqlite3
        n = sqlite3.connect(str(ROOT / "data/sor_research.sqlite")).execute(
            "SELECT COUNT(*) FROM research_memory WHERE created_at >= datetime('now','-7 days') "
            "AND category != 'method'"   # exclude meta/seed rows -- a self-referential seed must
            "").fetchone()[0]             # not green the guard (2026-07-24 audit: 1 seed did)
        if n == 0:
            defects.append(("production-research-memory-flat",
                            "research_memory added 0 rows in 7d -- the conversion loop is not "
                            "recording experiments (writable via scripts/research_memory.py; the "
                            "duty exists, verify missions actually call it)"))
    except Exception:
        pass


def check_gate_optimality(defects) -> None:
    """GATE-OPTIMALITY MONITOR (principal 2026-07-24): the DSR/gauntlet bar must stay OPTIMAL --
    a gate that rejects ~100pct or accepts ~100pct of candidates carries ZERO information and is
    a defect (good alphas lost to an accidentally-too-high bar cost as much as false ones
    admitted). Reads the per-gate rejection histogram; flags any gate at >=98pct reject over a
    non-trivial sample as suspect (mis-applied campaign-level veto, mis-calibration, or a bar
    that has silently become unclearable)."""
    wf = ROOT / "web/autodiscovery_crypto.json"
    if not wf.exists():
        return
    try:
        d = json.loads(wf.read_text("utf-8"))
    except Exception:
        return
    tested = int(d.get("cumulative_tested", 0) or 0)
    hist = d.get("rejection_by_gate", {}) or {}
    if tested < 30 or not hist:
        return
    pegged = [g for g, n in hist.items() if tested and (int(n) / tested) >= 0.98]
    if pegged:
        # Reconciliation rule 3: COMPUTE effective-vs-raw n_trials instead of only asking a human
        # to "audit" it. A raw tally that inflates far past the independent-mechanism count sets
        # the DSR bar unclearable -- the concrete way a pegged gate becomes a survivor-killer.
        from libs.autodiscovery.extraction_parity import effective_trial_count
        eff = effective_trial_count(_trial_mechanisms())
        infl = (f" Effective-vs-raw n_trials: raw {eff.raw} vs {eff.effective} independent "
                f"mechanisms ({eff.inflation:.1f}x inflation) -- "
                + ("deflate DSR by the EFFECTIVE count." if eff.inflation > 1.5
                   else "count is not the cause here.")) if eff.raw else ""
        defects.append((
            "gate-optimality",
            f"gate(s) rejecting >=98pct of {tested} candidates: {', '.join(sorted(pegged))} -- "
            "a ~100pct-constant gate carries zero information. Verify it is genuinely "
            "discriminating, not a campaign-level statistic mis-applied per-candidate or a bar "
            f"risen unclearable; real alphas may be dying at it.{infl}"))
    if int(d.get("cumulative_survivors", 0) or 0) == 0 and tested >= 200:
        defects.append((
            "gate-optimality-zero-survivors",
            f"0 survivors across {tested} tested -- expected on picked-clean price space, but "
            "confirm the funnel can EVER promote: is any single gate the 100pct bottleneck, and "
            "is the walk-forward/per-candidate path able to pass a genuinely-good synthetic?"))


def check_data_utilization(defects) -> None:
    """DATA-UTILIZATION LAW, reconciled with the GATE-OPTIMALITY MONITOR (principal 2026-07-24).

    The naive law ("idle data is paralysis; scale extraction") conflicts with gate-optimality:
    mass combinatorial/genetic generation to clear the flag explodes the trial count and deflates
    the DSR bar unclearable (the 420->0 dynamic). Binding reconciliation (extraction_parity.py):
    paralysis is a COVERAGE gap, NOT a volume gap. It clears when every ingested axis carries >=1
    screened, economically-motivated hypothesis (~one mechanism-first trial per axis, ~20 trials),
    never on hypothesis count. So this check measures COVERAGE of the acquired surface, and its
    remedy is mechanism-first coverage of the idle axes -- explicitly NOT volume."""
    from libs.autodiscovery.extraction_parity import axis_coverage

    acquired = _acquired_axes()
    if len(acquired) < 8:
        return  # too small a surface to judge parity
    tags = _converted_axes()
    # tolerant match: an acquired axis is 'covered' if any converted-axis name shares its normalized
    # name (handles collector-store vs axis-name drift, e.g. cny_premium.jsonl <-> cny_premium)
    def _covered(axis: str) -> bool:
        a = axis.lower()
        return any(t == a or t in a or a in t for t in tags)
    covered = [a for a in acquired if _covered(a)]
    rep = axis_coverage(axes=acquired, screened_axes=covered)
    if not rep.cleared:
        shown = ", ".join(rep.idle[:8]) + (" ..." if len(rep.idle) > 8 else "")
        defects.append((
            "data-utilization-paralysis",
            f"{len(rep.idle)}/{rep.n_axes} ingested axes have 0 screened hypothesis "
            f"({rep.coverage_frac:.0%} coverage): {shown} -- DATA PARALYSIS is a COVERAGE gap. "
            "Convert each idle axis MECHANISM-FIRST: one screened, economically-motivated "
            "hypothesis per axis (tag it via research_memory.py --axis). Do NOT clear this by "
            "generating volume -- combinatorial/genetic expansion is EARNED per axis only after "
            "its single-axis screen shows signal (else it is pure DSR deflation)."))


def check_post_gate0_activation(defects) -> None:
    """POST-GATE-0 ACTIVATION INTERLOCK (enforces 'nothing deferred may be skipped').

    The freeze-exit is auto-detected by run_cadence and the POST_GATE0 manifest is flagged for
    activation -- but activation itself was a DIRECTIVE the brain cycle had to obey, with no check
    that it actually happened. This closes that: the moment Gate 0 is complete
    (``data/gate0_complete``) but the cadence state has not set ``post_gate0_activated``, the entire
    deferred queue (docs/POST_GATE0_MANIFEST.md) is sitting un-built -- a defect that escalates to
    the principal at 48h. So the automatic build is VERIFIED to fire, never silently missed."""
    if not (ROOT / "data/gate0_complete").exists():
        return  # pre-Gate-0: the freeze correctly holds, the manifest is not due yet
    state = _j(ROOT / "data/cadence_state.json", {})
    if not (isinstance(state, dict) and state.get("post_gate0_activated")):
        defects.append((
            "post-gate0-activation",
            "Gate 0 is COMPLETE (data/gate0_complete) but post_gate0_activated is NOT set -- the "
            "POST_GATE0 manifest has not activated, so every deferred item (data collectors, "
            "growth ramp, live organs, runtime-gated research completions) is sitting un-built. "
            "Activate docs/POST_GATE0_MANIFEST.md top-to-bottom in EV order THIS cycle; nothing "
            "deferred may be skipped."))


def check_rejection_shadow(defects) -> None:
    """REJECTION-SHADOW standing duty (gate-calibration, MAX_SURVIVORS Part 1.2): the gauntlet
    rejects most candidates -- correct on picked-clean price space -- but a gate that drifted
    over-strict silently LEAKS real edges. run_rejection_shadow.py shadow-tracks a sample of rejects
    forward and writes web/reject_shadow.json. This check surfaces its verdict every cycle: (a) an
    OVER-STRICT gate is a defect (recover the leaked edges); (b) rejects piling up with the audit
    never run / stale is itself a defect (the recovery loop is off). Pure recovery, no new data."""
    rf = ROOT / "web/reject_shadow.json"
    d = _j(rf, None)
    if not isinstance(d, dict):
        return  # runner has never produced output yet -- surfaced by production/organ checks
    audit = d.get("audit", {}) if isinstance(d.get("audit"), dict) else {}
    if audit.get("over_strict"):
        leak = audit.get("leak_frac", 0.0)
        n = audit.get("n_rejects", 0)
        defects.append((
            "rejection-shadow-overstrict",
            f"gate OVER-STRICT: {audit.get('n_would_have_paid', 0)}/{n} shadowed rejects "
            f"({float(leak):.0%}) would have paid out-of-sample -- the gate is leaking survivors. "
            "Re-calibrate (effective-trial count, per-gate bar) and re-examine the leaked ids; "
            "this is pure recovery, no new data."))
    n_elig = int(d.get("n_eligible", 0) or 0)
    n_pending = int(d.get("n_pending_rescore", 0) or 0)
    if n_elig >= 5 and n_pending == n_elig:
        defects.append((
            "rejection-shadow-unscored",
            f"{n_elig} rejects are old enough to judge but NONE are forward-scored -- the reject "
            "forward-evaluator is not feeding data/reject_forward_scores.json, so the gate-leak "
            "audit cannot run. Wire the re-score so wrongly-rejected edges can be recovered."))


def check_source_backlog(defects) -> None:
    """SOURCE-VERIFICATION BACKLOG DUTY: the catalogue (data_axis_watchlist.md) already grows
    faster than it gets verified -- prospector/litminer run daily and add candidate source cards;
    verifying one (real docs read, real endpoint test) is the actual bottleneck, not discovery.
    Flags a STALE backlog: pending cards exist but the watchlist file hasn't been touched (a card
    resolved/added) in a long time -- the verification loop has stopped, silently, while discovery
    keeps running. This is the coverage-not-volume discipline applied to sourcing: the fix is
    working scripts/source_backlog_next.py's queue, never cataloguing more."""
    from libs.research.source_backlog import backlog_from_file

    wf = ROOT / "docs/research/data_axis_watchlist.md"
    if not wf.exists():
        return
    rep = backlog_from_file(wf, limit=1)
    pending = rep.n_verification_pending + rep.n_legitimacy_pending
    if pending == 0:
        return
    stale_days = 14.0
    age_h = (NOW - wf.stat().st_mtime) / 3600.0
    if age_h / 24.0 > stale_days:
        defects.append((
            "source-backlog-stale",
            f"{pending} catalogued source(s) still pending (verification or legitimacy decision) "
            f"and the watchlist has not been touched in {age_h / 24.0:.0f}d -- discovery is "
            "outrunning verification. Run scripts/source_backlog_next.py and clear the next item, "
            "do not catalogue more."))


def check_depth_parity(defects) -> None:
    """DEPTH-BREADTH PARITY LAW enforcement (charter §32): depth must keep pace with breadth,
    never lag it. A forward-clock axis that sits SHALLOW (< DEEP_DAYS of history) while the desk
    keeps widening breadth is a defect -- a shallow axis waits weeks on the forward clock and
    cannot validate, so breadth without depth is unconverted potential (the utilisation-without-
    conversion trap). Flags shallow clock axes as backfill targets (reconstruct to archive depth,
    MAX_SURVIVORS Part 1 #1). An axis already backfilled (has a reconstructed_oos report) is deep;
    an archive-thin axis that has logged its measured depth ceiling is exempt -- depth is never
    faked to clear this flag."""
    # deep_days is evidence-adjustable within hard bounds (self-tuning, not a free knob)
    from libs.self_improvement.adaptive_thresholds import ThresholdBook
    deep_days = ThresholdBook(ROOT / "data/adaptive_thresholds.json").get("depth_deep_days")
    clocks: list[Path] = []
    for pat in ("data/*_premium.jsonl", "data/*_supply.jsonl", "data/*_activity.jsonl"):
        clocks += list(ROOT.glob(pat))
    if len(clocks) < 3:
        return  # too few series to judge depth-vs-breadth
    deep_names: set[str] = set()
    oos = ROOT / "reports/reconstructed_oos"
    if oos.exists():
        for r in oos.glob("*.json"):
            deep_names.add(r.stem.lower())
    # archive-relative exemption: an axis whose archive genuinely maxes out below deep_days logs its
    # measured ceiling here (axis -> max available days); at/above it, the axis is as deep as its
    # archive allows and is NOT flagged (§32: 'as deep as the archive legitimately allows').
    ceilings = _j(ROOT / "data/depth_ceilings.json", {})
    shallow: list[tuple[str, int]] = []
    for c in clocks:
        stem = c.stem.lower()
        if any(stem in d or d in stem for d in deep_names):
            continue  # already backfilled to archive depth
        try:
            with c.open("r", encoding="utf-8") as fh:
                n = sum(1 for _ in fh)
        except Exception:
            continue
        ceiling = ceilings.get(c.stem) if isinstance(ceilings, dict) else None
        if isinstance(ceiling, (int, float)) and n >= int(ceiling):
            continue  # as deep as its own archive allows -- exempt, never faked
        if n < deep_days:
            shallow.append((c.stem, n))
    if shallow:
        shown = ", ".join(f"{s}({n}d)" for s, n in sorted(shallow, key=lambda x: x[1])[:8])
        defects.append((
            "depth-parity",
            f"{len(shallow)} axis(es) shallow (<{int(deep_days)}d) while breadth widens: {shown} "
            "-- DEPTH LAGGING BREADTH (§32). A shallow axis waits weeks on the forward clock and "
            "cannot validate; breadth without depth is unconverted potential. Backfill each to its "
            "archive-depth ceiling and diff-verify (MAX_SURVIVORS Part 1 #1) -- never fake depth; "
            "an archive-thin axis logs its measured ceiling and is exempt."))


def check_ci_scope(defects) -> None:
    """MAP-vs-TERRITORY (audit 3.1): the CI gate must run the whole test tree, not a hardcoded
    subset. GAP #31's stated blocker (duplicate basenames) expired -- pyproject sets
    import-mode=importlib and the tree collects cleanly. A gate that runs a handful of named
    files certifies almost nothing: the ruin path (tests/risk) and the anti-false-positive path
    (tests/validation) are the largest ungated directories, and freshly-shipped tests land in
    ungated dirs by default. Parses the pytest ARGUMENT TOKENS (a comment mentioning the tree
    must not satisfy the check)."""
    ci = ROOT / "scripts/run_ci.py"
    tests_dir = ROOT / "tests"
    if not (ci.exists() and tests_dir.exists()):
        return
    body = ci.read_text("utf-8")
    named = re.findall(r'"(tests/[A-Za-z0-9_./-]*)"', body)
    if not named:
        return
    whole_tree = any(t.rstrip("/") == "tests" for t in named)
    if whole_tree:
        return
    total = sum(1 for _ in tests_dir.rglob("test_*.py"))
    gated_files = sum(1 for t in named if t.endswith(".py"))
    gated_dirs = [t for t in named if not t.endswith(".py")]
    defects.append((
        "ci-scope-partial",
        f"run_ci.py gates a HARDCODED subset -- {gated_files} named test files + "
        f"{len(gated_dirs)} dir(s) {gated_dirs} -- out of ~{total} test files in the tree. The "
        "ruin path (tests/risk) and anti-false-positive path (tests/validation) are ungated, and "
        "new tests land ungated by default. Replace the named paths with the tests/ tree: the "
        "importlib collection blocker (GAP #31) has expired. Freeze-legal, highest-ROI."))


def check_review_risks_tracked(defects) -> None:
    """MAP-vs-TERRITORY (audit 4.1): every risk NAMED in a review doc must inherit the
    GAP_REGISTER escalation loop (weekly re-rank, 7-day staleness). Nothing reconciles the two,
    so the desk's two largest structural risks (counterparty concentration, key-person) sit in a
    doc that is read but never re-ranked."""
    sr = ROOT / "docs/SYSTEM_REVIEW.md"
    gr = ROOT / "docs/GAP_REGISTER.md"
    if not (sr.exists() and gr.exists()):
        return
    reg = gr.read_text("utf-8").lower()
    # the named structural risks the audit flagged as untracked
    for key, label in (("counterparty", "counterparty/single-venue concentration"),
                       ("key-person", "principal key-person risk"),
                       ("per-venue", "per-venue exposure cap")):
        named_in_review = key in sr.read_text("utf-8").lower()
        tracked = key.replace("-", " ") in reg or key in reg
        if named_in_review and not tracked:
            defects.append(("review-risk-untracked",
                            f"'{label}' named in SYSTEM_REVIEW, NO GAP_REGISTER row -- "
                            "it never enters the weekly re-rank/staleness/escalation loop. Add a "
                            "tracked row so a named risk cannot silently escape the discipline."))


def check_orphan_code(defects) -> None:
    """MAP-vs-TERRITORY (audit 2.x): the desk flags idle DATA/capital/clocks but not idle CODE.
    Flags library packages that are almost entirely unreachable from any scripts/ entry point --
    e.g. libs/backtest (the independent cross-check engine) applied to zero strategies. Bounded:
    reports only near-fully-orphaned packages to stay cheap and low-noise."""
    libs = ROOT / "libs"
    scripts = ROOT / "scripts"
    if not (libs.exists() and scripts.exists()):
        return
    # cheap reachability proxy: a package is 'used' if any scripts/ file imports from it
    entry_text = "\n".join(f.read_text("utf-8", errors="ignore")
                            for f in scripts.glob("*.py"))
    suspicious = []
    for pkg in sorted(d for d in libs.iterdir() if d.is_dir() and (d / "__init__.py").exists()):
        name = pkg.name
        mods = [m.stem for m in pkg.glob("*.py") if m.stem != "__init__"]
        if len(mods) < 3:
            continue
        # imported from scripts at all?
        if f"libs.{name}" in entry_text or f"from libs.{name}" in entry_text:
            continue
        suspicious.append(f"{name}({len(mods)} modules)")
    if suspicious:
        defects.append(("orphan-code",
                        "library package(s) imported by NO scripts/ entry point (idle code -- "
                        f"the class never monitored): {', '.join(suspicious[:6])}. Wire the "
                        "safeguard (e.g. libs/backtest cross_engine) or retire on the record -- "
                        "verify against dynamic imports before deleting."))


#: Docs where mined finds ACCUMULATE UN-DISPOSITIONED -- the only place §33 inventory can rot.
#: Deliberately excluded, each for a reason (the check must flag rot, not paperwork):
#:   graveyard.md              -- a graveyard entry IS a disposition; terminal by construction
#:   negative_knowledge.md     -- own terminal schema (``[priority: ...] review-due: <date>``)
#:   search_operator_library.md-- own terminal schema (``[status: active|watch|archived]``)
#:   prospector_watchlist.md   -- prose STEP headers, not carded finds
_DIG_DOCS = (
    "docs/research/data_axis_watchlist.md",
    "docs/research/feed_inbox.md",
    "docs/research/discovery_hypotheses.md",
    "docs/research/literature_coverage.md",
)
#: Committed-state is checked over the whole research surface, including the excluded docs above:
#: a graveyard entry is self-dispositioning but still has to reach git to exist.
_DIG_TRACKED = ("docs/research", "docs/graveyard.md")
#: Written when the backlog is non-empty; every ops/run_*_dig.sh refuses to start while it exists.
MINING_SUSPENDED = ROOT / "data/mining_suspended"


def _conversion_artifacts() -> list[str]:
    """Names the desk can CORROBORATE on disk -- the artifact-only credit set for §33.

    Mirrors ``_converted_axes``: a conversion is credited from things that exist (a collector's
    output, a reconstructed-OOS report, a screened axis in research memory), never from a claim in
    a document. An organ does not grade its own homework.
    """
    names: set[str] = set()
    with contextlib.suppress(Exception):
        names.update(_converted_axes())
    for pat in ("data/*.jsonl", "data/batch_*.json", "reports/reconstructed_oos/*.json"):
        with contextlib.suppress(Exception):
            names.update(p.stem.lower() for p in ROOT.glob(pat))
    for pat in ("scripts/collect_*.py", "scripts/backfill_*.py"):
        with contextlib.suppress(Exception):
            names.update(p.stem.replace("collect_", "").replace("backfill_", "").lower()
                         for p in ROOT.glob(pat))
    return sorted(n for n in names if n)


MINE_LEDGER = ROOT / "data/mine_conversion_log.jsonl"
MINE_RATCHET = ROOT / "data/mine_conversion_ratchet.json"
MINE_PRIORS = ROOT / "data/mine_generation_priors.json"


def _mine_thresholds() -> dict:
    """§33 bars, evidence-adjustable within hard tighten-only bounds (the desk's ThresholdBook)."""
    out = {"kill": 0.60, "stale": 14.0, "regress": 1.5}
    try:
        from libs.self_improvement.adaptive_thresholds import ThresholdBook
        b = ThresholdBook(ROOT / "data/adaptive_thresholds.json")
        out = {"kill": b.get("mine_kill_share_bar"),
               "stale": b.get("mine_stale_owing_days"),
               "regress": b.get("mine_latency_regress_mult")}
    except Exception:
        pass
    return out


def _mine_items():
    """Parse every owing carded find, tiered against the axes the desk has ALREADY ingested."""
    from libs.research.mine_conversion import parse_dispositions
    from libs.research.source_backlog import parse_watchlist
    axes = []
    with contextlib.suppress(Exception):
        axes = _acquired_axes()
    items = []
    for rel in _DIG_DOCS:
        p = ROOT / rel
        if not p.exists():
            continue
        with contextlib.suppress(Exception):
            text = p.read_text("utf-8")
            found = parse_dispositions(text, source=rel, ingested_axes=axes)
            # A source card's OWN grade is already a disposition -- 'verified-clean' and
            # 'destroyed-at-source' are terminal in the existing taxonomy, so demanding a second
            # §33 tag would be paperwork, not conversion. Reuse the graded classifier the desk
            # already has rather than duplicating the grade rules here.
            with contextlib.suppress(Exception):
                resolved = {c.name.lower() for c in parse_watchlist(text)
                            if c.category == "resolved"}
                if resolved:
                    found = [i for i in found
                             if not any(r in i.name.lower() for r in resolved)]
            items += found
    return items


def _mine_backing() -> dict:
    """Artifact-only credit, per disposition. `killed` is backed by the GRAVEYARD -- which is what
    makes mass-killing the backlog cost more than converting it, rather than less."""
    arte = _conversion_artifacts()
    grave = []
    gp = ROOT / "docs/graveyard.md"
    if gp.exists():
        with contextlib.suppress(Exception):
            grave = [ln.strip(" #-*").lower() for ln in gp.read_text("utf-8").splitlines()
                     if ln.strip()]
    return {"wired": arte, "screened": arte, "killed": grave}


def check_mine_conversion(defects) -> None:
    """§33 MINED-TO-WIRED (stock + quality + value): no carded find sleeps twice, a backlog
    SUSPENDS mining, and the backlog is PRICED so it cannot be cleared by doing only easy work.

    Mined intelligence is inventory, and un-converted inventory depreciates. Mining is not the
    product; conversion is. This writes the gate file the digger shells refuse to start against,
    so an organ producing faster than the desk converts pays the cost itself -- flow control, not
    punishment. Three teeth beyond mere reporting: `killed` is corroborated against the graveyard
    (closing the mass-kill escape hatch), the backlog is TIER-WEIGHTED, and a priority inversion
    (cheap work finished while a Tier-1 defect-closer still owes) is its own defect.
    """
    from libs.research.mine_conversion import append_snapshot, conversion_report

    items = _mine_items()
    if not items:
        return  # nothing carded -- nothing owed (a fresh clone, not a defect)
    thr = _mine_thresholds()
    rep = conversion_report(items, as_of=datetime.now(UTC).date(),
                            backing=_mine_backing(), root=ROOT)
    with contextlib.suppress(OSError):
        append_snapshot(MINE_LEDGER, items)

    # the gate file IS the enforcement -- a reported backlog that stops nothing is a wish
    try:
        if rep.suspend_mining:
            MINING_SUSPENDED.parent.mkdir(parents=True, exist_ok=True)
            MINING_SUSPENDED.write_text(rep.verdict + "\n", "utf-8")
        elif MINING_SUSPENDED.exists():
            MINING_SUSPENDED.unlink()
    except OSError:
        pass  # a read-only checkout still reports; it just cannot gate

    if rep.n_backlog:
        defects.append((
            "mine-conversion-backlog",
            f"§33: {rep.n_backlog}/{rep.n_items} carded find(s) owe a disposition (weighted "
            f"{rep.weighted_backlog}, highest tier owing T{rep.top_tier_owing}) -- "
            f"{', '.join(rep.backlog_names)}. MINING IS SUSPENDED (data/mining_suspended): the "
            "whole dig slot reassigns to conversion, HIGHEST TIER FIRST, catalogue nothing new "
            "until it clears. Every item takes exactly one of wired / screened / killed / "
            "deferred(DATE) -- silence is the defect."))
    if rep.n_illegal:
        defects.append((
            "mine-conversion-illegal",
            f"§33: {rep.n_illegal} disposition(s) are not legal -- {', '.join(rep.illegal_names)}."
            " An UNDATED deferral is the hiding place every rotting backlog uses: name the blocker"
            " and give a date, or pick a terminal disposition."))
    if rep.n_unbacked:
        defects.append((
            "mine-conversion-unbacked",
            f"§33: {rep.n_unbacked} item(s) CLAIM a terminal disposition with no corroborating "
            f"artifact -- {', '.join(rep.unbacked_names)}. Conversion is credited from artifacts "
            "on disk, never from a report; a 'killed' needs its GRAVEYARD entry with the mechanism "
            "of death. Produce the artifact or downgrade the claim."))
    if rep.kill_share > thr["kill"] and (rep.n_killed + rep.n_wired + rep.n_screened) >= 4:
        defects.append((
            "mine-conversion-killspike",
            f"§33 quality: {rep.kill_share:.0%} of terminal dispositions are 'killed' (bar "
            f"{thr['kill']:.0%}) -- the backlog is being cleared by GRAVEYARD rather than by "
            "conversion. A disposition is not automatically a conversion; a bad batch is real but "
            "so is the cheap exit, and this is its signature. Justify each kill's mechanism."))
    if rep.n_fuzzy_credited and not rep.n_unbacked:
        defects.append((
            "mine-conversion-fuzzy",
            f"§33 evidence standard: {rep.n_fuzzy_credited} terminal claim(s) are credited by "
            "NAME MATCHING, not by a named artifact. Fuzzy credit breaks silently on a rename and "
            "grants silently on a coincidence. Use the exact form -- "
            "`[§33: wired -> data/upbit_1m.jsonl]` -- which must exist and be non-empty. Not a "
            "backlog defect; a standard the desk should be ratcheting up."))
    if rep.priority_inversion:
        defects.append((
            "mine-conversion-inversion",
            f"§33.6 priority inversion: a T{rep.top_tier_owing} item still owes while cheaper-tier "
            "work was completed. Defect-closers (a permanently-firing gate made satisfiable) "
            "outrank mechanism priors, which outrank new surfaces, which outrank operators. Work "
            "the expensive tier FIRST -- clearing the easy tail is how a backlog looks like "
            "progress while the valuable item rots."))


def check_mine_flow(defects) -> None:
    """§33 FLOW + FEEDBACK + RATCHET: is conversion getting FASTER, and does it steer generation?

    A stock check says whether inventory exists; only a flow check says whether the desk is
    improving. And conversion outcomes that dead-end in an audit report are a fence -- fed back as
    per-class priors they become a control system, which is what maximum utilisation actually
    means. The bar is the desk's OWN BEST-EVER performance: every record tightens it permanently
    and it never loosens, so there is no "good enough", only better-than-our-best or a regression.
    """
    from libs.research.mine_conversion import (
        class_priors,
        feedback_applied,
        flow_stats,
        load_ledger,
        load_ratchet,
        priors_payload,
        update_ratchet,
    )

    ledger = load_ledger(MINE_LEDGER)
    if len(ledger) < 2:
        return  # a single snapshot cannot measure flow -- not a defect, just no history yet
    thr = _mine_thresholds()
    flow = flow_stats(ledger)
    n_names = len({str(i.get("n", "")) for r in ledger for i in r["items"]})
    rate = (flow.n_converted / n_names) if n_names else 0.0

    priors = class_priors(ledger)
    if priors:
        with contextlib.suppress(OSError):
            MINE_PRIORS.parent.mkdir(parents=True, exist_ok=True)
            MINE_PRIORS.write_text(json.dumps(priors_payload(priors), indent=2), "utf-8")

    new_ratchet, verdict = update_ratchet(
        load_ratchet(MINE_RATCHET), flow, conversion_rate=rate, regress_mult=thr["regress"])
    with contextlib.suppress(OSError):
        MINE_RATCHET.write_text(new_ratchet.model_dump_json(indent=2), "utf-8")

    if flow.oldest_owing_days > thr["stale"]:
        defects.append((
            "mine-flow-rotting",
            f"§33: '{flow.oldest_owing_name}' has owed a disposition for "
            f"{flow.oldest_owing_days:.0f}d (bar {thr['stale']:.0f}d). Age IS the damage -- a "
            "finding depreciates while it waits, and the desk has been faster than this."))
    if verdict.regressed:
        defects.append((
            "mine-flow-regression",
            f"§33 RATCHET: {verdict.verdict} Next-cycle bar {verdict.next_bar_days:.1f}d. The "
            "standard is the desk's own record and it only moves down -- recover the pace or "
            "log the measured reason it is no longer achievable."))
    if flow.latency_worsening and not verdict.regressed:
        defects.append((
            "mine-flow-slowing",
            f"§33: conversion latency is TRENDING worse (median {flow.median_latency_days:.1f}d, "
            "recent half >1.5x the earlier half). Catch it as a trend, before it becomes a "
            "regression against the record."))
    ok, why = feedback_applied(ledger, priors)
    if not ok:
        defects.append((
            "mine-feedback-ignored",
            f"§33.4 closed loop: {why} data/mine_generation_priors.json is published every "
            "sweep -- generation MUST read it and reweight. A prior nothing acts on is the same "
            "failure as a law with no monitor."))


def check_mine_gate(defects) -> None:
    """The gate must be DERIVED, not a deletable flag -- and it must actually run.

    `data/mining_suspended` was a file, and a file is something `rm` defeats: deleting it would
    have restored mining without converting anything, making the law advisory again. The shells
    now RUN scripts/mine_gate.py, which recomputes the backlog from the docs. Two failure modes
    are checked here because the gate fails OPEN by design (a bug must never freeze the desk's
    entire research intake for a week): the script must exist, and it must execute cleanly.
    """
    import subprocess

    gate = ROOT / "scripts/mine_gate.py"
    if not gate.exists():
        defects.append(("mine-gate-missing",
                        "§33: scripts/mine_gate.py is absent -- the digger shells call it to "
                        "recompute the backlog, and without it the gate degrades to whatever the "
                        "shells do on a missing command. Restore it."))
        return
    shells = [*sorted(ROOT.glob("ops/run_*dig*.sh")), ROOT / "ops/run_frontier_miner.sh"]
    untrusting = [s.name for s in shells if s.exists() and "mine_gate.py" not in
                  s.read_text("utf-8", errors="ignore")]
    if untrusting:
        defects.append(("mine-gate-bypassed",
                        f"§33: digger shell(s) do NOT invoke the derived gate -- "
                        f"{', '.join(untrusting)}. A shell that skips mine_gate.py mines "
                        "regardless of the backlog; that is the law switched off for that organ."))
    try:
        r = subprocess.run([sys.executable, str(gate), "--explain"], cwd=ROOT,
                           capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        defects.append(("mine-gate-broken",
                        f"§33: the gate script could not be executed ({type(exc).__name__}). It "
                        "fails OPEN by design, so a broken gate silently authorises mining -- "
                        "this defect is the only thing that surfaces it. Fix before the next dig."))
        return
    if "GATE-ERROR" in (r.stdout + r.stderr):
        defects.append(("mine-gate-broken",
                        f"§33: the gate script raised and failed OPEN -- {r.stdout.strip()[:220]}. "
                        "Mining is currently UNGATED. Fix before the next dig."))


def check_dig_uncommitted(defects) -> None:
    """A dig finding not in git DID NOT HAPPEN -- VPS disk is not institutional memory.

    The best output of a cycle is one disk failure from never having existed, and an audit that
    reads only the repo cannot see it at all (the map-vs-territory failure, applied to the desk's
    own research). Compares each dig doc's mtime against the last commit that touched it.
    """
    import subprocess

    # Asked exactly, via git's own index -- NOT file mtimes. A fresh clone stamps every file with
    # the checkout time, so an mtime-vs-commit-time comparison reports the entire research surface
    # as uncommitted on any re-clone. `git status --porcelain` answers the real question.
    try:
        out = subprocess.run(["git", "status", "--porcelain", "--", *_DIG_TRACKED],
                             cwd=ROOT, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return  # no git available -- the check simply does not apply here
    if out.returncode != 0:
        return
    stale = []
    for line in out.stdout.splitlines():
        if len(line) > 3:
            code, path = line[:2].strip() or "??", line[3:].strip()
            stale.append(f"{Path(path).name}[{code}]")
    if stale:
        defects.append((
            "dig-output-uncommitted",
            f"§33: dig output UNCOMMITTED -- {', '.join(stale[:8])}. Output not "
            "committed and pushed by end of cycle DID NOT HAPPEN and earns zero credit: git is "
            "the institutional memory, VPS disk is not. Commit, push, and VERIFY the push."))


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
                      ("forensics-fresh", check_forensics_fresh),
                      ("memory-hygiene", check_memory_hygiene),
                      ("prompt-layer", check_prompt_layer),
                      ("gate-optimality", check_gate_optimality),
                      ("data-utilization", check_data_utilization),
                      ("ci-scope", check_ci_scope),
                      ("review-risks", check_review_risks_tracked),
                      ("orphan-code", check_orphan_code),
                      ("mine-conversion", check_mine_conversion),
                      ("mine-flow", check_mine_flow),
                      ("mine-gate", check_mine_gate),
                      ("dig-uncommitted", check_dig_uncommitted),
                      ("depth-parity", check_depth_parity),
                      ("source-backlog", check_source_backlog),
                      ("rejection-shadow", check_rejection_shadow),
                      ("post-gate0-activation", check_post_gate0_activation),
                      ("production", check_production),
                      ("bnb-funded", check_bnb_funded),
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
    # DELIVERY FIX (2026-07-24 external audit): the pager reads only PRINCIPAL_ACTION line 1.
    # The old code appended the escalation BELOW existing content (a stale RESOLVED line stayed
    # at line 1) AND only wrote once ever (one-shot latch), so 24 live defects never paged. Now
    # the escalation OWNS line 1 whenever defects are overdue, and is CLEARED when none are --
    # so the pager surfaces the truth and stops crying resolved-wolf.
    _MARK = "MAX-AUDIT ESCALATION"
    existing = PA.read_text("utf-8") if PA.exists() else ""
    # strip any prior escalation block so it never stacks / goes stale
    body = existing.split("\n" + _MARK)[0].split(_MARK)[0].rstrip()
    if overdue:
        head = (f"{_MARK}: {len(overdue)} below-max state(s) >48h unfixed/unacked -- "
                + "; ".join(f"{d}" for d, _ in overdue[:6])
                + (" ..." if len(overdue) > 6 else "") + "\n"
                + "".join(f"  - {d}: {m}\n" for d, m in overdue[:8]))
        PA.write_text(head + "\n" + body, "utf-8")   # escalation OWNS line 1
        print(f"ESCALATED to principal page (line 1): {len(overdue)} defect(s) >48h")
    elif existing != body + ("\n" if body else ""):
        PA.write_text(body + ("\n" if body else ""), "utf-8")  # cleared: drop stale escalation
        print("escalation cleared: no overdue defects")


if __name__ == "__main__":
    main()
