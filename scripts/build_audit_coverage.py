#!/usr/bin/env python3
"""FULL-COVERAGE AUDIT FEED (principal exception to the doctrine freeze, 2026-07-20).

PROBLEM THIS SOLVES: the external panel used to see ONLY docs/EXTERNAL_PANEL_DOSSIER.md --
11KB of prose curated by the very system being audited, against ~44k lines of real code.
The auditee chose the auditor's evidence, so nothing outside the dossier could ever be
flagged, and most of the codebase had never been examined by anyone but its author.

WHAT THIS DOES: every panel run now also carries
  (A) the RAW, UNFILTERED git diff since the previous panel run -- curation-proof, and
  (B) a rotating slice of the LEAST-RECENTLY-AUDITED source files, in full, and
  (C) the coverage manifest itself, so models can see what is stale or never-audited and
      call out the blind spots directly.
A per-file ledger (data/audit_coverage.json) records who saw what and when, so "full
coverage" becomes a measurable property with staleness floors rather than an aspiration.

SAFETY: data/secrets/** and anything key/credential-shaped is excluded by path BEFORE
reading, and the assembled payload is run through the desk's own sanitize() before it is
ever returned. stdlib-only.
"""
from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "data/audit_coverage.json"

# what the sweep covers -- code + operator contracts (the brain's prompt lives in ops/*.sh)
INCLUDE_GLOBS = ("scripts/*.py", "libs/**/*.py", "ops/*.sh", "ops/*.txt",
                 "tests/**/*.py", "docs/*.md", "docs/research/*.md", "docs/playbooks/*.md")
# never read, never send
EXCLUDE_PARTS = ("secrets", "__pycache__", ".venv", ".git", "node_modules")
EXCLUDE_SUFFIX = (".bak", ".pyc", ".log")

# RISK-class (money path) files are audited on a tighter clock than everything else
RISK_PREFIXES = ("libs/execution/", "scripts/run_deadman_switch.py", "scripts/run_cashcarry",
                  "scripts/run_alerts.py", "scripts/run_recorder.py", "scripts/run_ci.py")
RISK_MAX_AGE_D = 14.0
ROTATE_MAX_AGE_D = 30.0

# CLASS 'ALWAYS' = the DECISION surface: what a reviewer must see to give SPECIFIC advice rather
# than generic advice ("add these 3 grounds to the JP miner" vs "consider more breadth").
# Ships IN FULL on every run, exempt from the rotating budget, re-audited every run.
ALWAYS_PREFIXES = (
    "ops/frontier_", "ops/prospector_dig_prompt", "ops/litminer_dig_prompt",
    "ops/dataaxis_dig_prompt", "ops/blindrediscovery_dig_prompt",
    "docs/research/data_axis_watchlist.md", "docs/research/prospector_coverage.md",
    "docs/research/improvement_inbox.md", "docs/research/search_operator_library.md",
    "docs/research/weak_signal_registry.md", "docs/research/discovery_hypotheses.md",
    "docs/research/negative_knowledge.md", "docs/research/canary_searches.md",
    "docs/research/prospector_watchlist.md", "docs/research/generation_due.md",
    "docs/research/HYPOTHESIS_MAX_SPEC.md", "docs/research/video_locked_log.md",
    "docs/GAP_REGISTER.md", "docs/DIGGING_CHARTER.md",
)

# how much source to ship per run. ~200k chars ~= 50k tokens; x13 seats ~= <$1/run.
CODE_BUDGET_CHARS = 2_400_000    # TOTAL payload ceiling = the WHOLE system
                                 # (2.29MB); adaptation still finds the safe level
                                 # empirically, so this is a ceiling not a target
CODE_BUDGET_MIN = 40_000         # floor for the ROTATING part; tier-0 always ships
DIFF_BUDGET_CHARS = 60_000
QUORUM_FRAC = 0.6                # >=60% of seats must answer substantively to count
SUBSTANTIVE_CHARS = 400          # shorter than this is not a real review


def _review_class(rel: str) -> int:
    if any(rel.startswith(p) for p in ALWAYS_PREFIXES):
        return 0                                   # decision surface: always sent
    return 1 if any(rel.startswith(p) for p in RISK_PREFIXES) else 2


def _eligible() -> list[Path]:
    out: list[Path] = []
    for g in INCLUDE_GLOBS:
        for p in ROOT.glob(g):
            if not p.is_file():
                continue
            rel = p.relative_to(ROOT).as_posix()
            if any(x in rel for x in EXCLUDE_PARTS):
                continue
            if p.suffix in EXCLUDE_SUFFIX or ".bak-" in rel:
                continue
            out.append(p)
    return sorted(set(out))


def load() -> dict:
    if MANIFEST.exists():
        try:
            return json.loads(MANIFEST.read_text("utf-8"))
        except Exception:
            pass
    return {"files": {}, "last_panel_sha": None, "runs": 0}


def save(m: dict) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(m, indent=1), "utf-8")


def refresh(m: dict) -> dict:
    """Sync the manifest with what actually exists on disk (new files appear as never-audited)."""
    files = m.setdefault("files", {})
    seen = set()
    for p in _eligible():
        rel = p.relative_to(ROOT).as_posix()
        seen.add(rel)
        rec = files.setdefault(rel, {"last_audited": None, "audit_count": 0})
        try:
            # CLOSE THE HANDLE (2026-08-12). `sum(1 for _ in p.open(...))` never closed the file:
            # CPython's refcount reaps it, but it emits a ResourceWarning first, and this repo
            # sets filterwarnings = error. So EVERY test that transitively reached refresh() --
            # i.e. every test of record_blank, tune_budget or audit_payload, and therefore every
            # test of the panel's own failure path, which calls record_blank per dead seat --
            # failed on the warning rather than on the behaviour. The R0343 total-failure fixture
            # was the first thing to need that path and the first thing to hit this. A leak that
            # makes a code path untestable costs more than the descriptors.
            with p.open("r", encoding="utf-8", errors="ignore") as fh:
                rec["loc"] = sum(1 for _ in fh)
        except Exception:
            rec["loc"] = 0
        rec["review_class"] = _review_class(rel)
    for gone in [k for k in files if k not in seen]:
        files.pop(gone)          # deleted files leave the ledger; git keeps the history
    return m


def _age_days(iso: str | None) -> float:
    if not iso:
        return 1e9                                    # never audited = infinitely stale
    try:
        return (datetime.now(tz=UTC) - datetime.fromisoformat(iso)).total_seconds() / 86400
    except Exception:
        return 1e9


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                              text=True, timeout=30).stdout
    except Exception:
        return ""


def status(m: dict) -> dict:
    files = m["files"]
    never = [f for f, r in files.items() if not r.get("last_audited")]
    stale1 = [f for f, r in files.items()
              if r.get("review_class") == 1 and _age_days(r.get("last_audited")) > RISK_MAX_AGE_D]
    stale2 = [f for f, r in files.items()
              if r.get("review_class") == 2 and _age_days(r.get("last_audited")) > ROTATE_MAX_AGE_D]
    t0 = [f for f, r in files.items() if r.get("review_class") == 0]
    return {"total": len(files), "never": never, "stale_risk": stale1, "stale_rotate": stale2,
            "always_class": len(t0),
            "covered": len(files) - len(never),
            "pct": round(100.0 * (len(files) - len(never)) / max(1, len(files)), 1)}


def current_budget(m: dict) -> int:
    """Largest payload every seat has survived recently (learned, not guessed)."""
    return int(m.get("code_budget_chars", CODE_BUDGET_CHARS))


def tune_budget(blanked: int, total: int) -> int:
    """Shrink hard on any blank, grow gently on a clean run. Called after every panel.

    THE WELD THIS NOW REPORTS (measured 2026-08-12). The budget sat at exactly CODE_BUDGET_MIN
    while the last eight recorded firings carried 2-4 blanks of 4 -- `max(40_000, int(40_000 *
    0.6))` is 40_000, so the shrink arm moved NOTHING, eight times, and the history rendered
    `from 40000 to 40000` with no hint that a bound had been hit. A control that fires and
    changes nothing is a welded gate (L1.43), and this one is the mechanistic reason the same
    free seats blank forever: they fail on a 40k payload, the adaptive response that exists to
    shrink it cannot, and the tally records the blanks while the budget records success.

    NOTHING IS LOOSENED HERE. The floor is not lowered and neither arm is re-rated -- lowering a
    floor to clear the violation it caught is the failure this desk has paid for repeatedly. The
    fix is that "the budget adapted" and "the budget COULD NOT adapt" stop being byte-identical
    in the record, which is the only way anyone can argue about whether the floor is right.
    Whether these seats need a smaller tier or the floor needs re-deriving is a payload-design
    decision with an owner; this makes it visible, it does not take it.
    """
    m = refresh(load())
    cur = current_budget(m)
    if blanked:
        new = max(CODE_BUDGET_MIN, int(cur * 0.6))   # a blank is a real failure: cut deep
        bound = "floor" if new >= cur else None
    else:
        new = min(CODE_BUDGET_CHARS, int(cur * 1.15))  # earn size back slowly
        bound = "ceiling" if new <= cur else None
    m["code_budget_chars"] = new
    m.setdefault("budget_history", []).append(
        {"blanked": blanked, "of": total, "from": cur, "to": new,
         # Present ONLY when the arm was inert, so a reader scanning the history sees the weld
         # rather than having to re-derive it from two equal numbers.
         **({"welded_at": bound, "wanted": int(cur * 0.6) if blanked else int(cur * 1.15)}
            if bound else {})})
    m["budget_history"] = m["budget_history"][-30:]
    save(m)
    return new


#: Timestamped blanks kept beside the lifetime tally. Bounded so the ledger cannot grow without
#: limit; 400 covers months of panel runs at this desk's cadence and the window queries only ever
#: look back days.
_BLANK_EVENT_CAP = 400


def record_blank(model: str) -> None:
    """Per-seat blank tally -- turns a flaky seat into an evidence-backed swap decision.

    THE TALLY ALONE COULD NOT SUPPORT THAT DECISION, WHICH IS WHY THE EVENTS EXIST.
    `seat_blanks` is a LIFETIME counter that nothing anywhere resets or decays, so a seat that
    blanked three times months ago and has answered every call since is permanently
    indistinguishable from one that is dying right now. The fence keyed on it (`seat-chronic-*`)
    therefore fires on every run forever once a seat crosses the threshold -- a gate that cannot
    clear carries zero information, and its recommendation is to SWAP a seat that may be
    perfectly healthy. Measured 2026-08-13: nemotron-3-super-120b had a lifetime 4 and the live
    canary reported it alive and answering, 4/4 seats up.

    The tally is KEPT and keeps incrementing -- `check_free_roster` and `model_upgrade` read it,
    and it is honest as history. What is added is the timestamp, so a reader can ask "is this
    seat failing NOW" instead of only "has it ever failed".
    """
    m = refresh(load())
    m.setdefault("seat_blanks", {})[model] = int(m.get("seat_blanks", {}).get(model, 0)) + 1
    events = m.setdefault("seat_blank_events", [])
    events.append({"model": model, "ts": datetime.now(tz=UTC).isoformat()})
    m["seat_blank_events"] = events[-_BLANK_EVENT_CAP:]
    save(m)


def recent_blanks(m: dict[str, object], *, window_days: int) -> dict[str, int] | None:
    """Blanks per seat inside `window_days`, or ``None`` when recency cannot be measured.

    ``None`` IS THE LOAD-BEARING RETURN AND MUST NOT COLLAPSE INTO AN EMPTY DICT. Until the
    event log has been written to, a seat with a lifetime tally has NO recency evidence at all,
    and `{}` would read as "zero recent blanks -- the seat is fine", quietly clearing a fence on
    a box where nothing has been measured. That is absence resolving to a clean verdict, this
    desk's most-repeated defect class. A caller that gets ``None`` must say UNMEASURED.
    """
    events = m.get("seat_blank_events")
    if not isinstance(events, list) or not events:
        return None
    cutoff = datetime.now(tz=UTC) - timedelta(days=window_days)
    out: dict[str, int] = {}
    for e in events:
        if not isinstance(e, dict):
            continue  # attrition-ok: a malformed row carries no timestamp to place in a window
        try:
            when = datetime.fromisoformat(str(e.get("ts", "")))
        except ValueError:
            continue  # attrition-ok: same -- an unparseable stamp is not evidence of recency
        if when >= cutoff:
            model = str(e.get("model", "?"))
            out[model] = out.get(model, 0) + 1
    return out


#: Attempts are kept as a per-seat, per-DAY tally rather than one event per call: attempts
#: outnumber blanks by ~2 orders of magnitude, and a capped event list would evict the oldest
#: attempts first -- shrinking exactly the denominator this exists to protect. Days retained; the
#: window queries only ever look back `SEAT_BLANK_WINDOW_DAYS`.
_ATTEMPT_DAY_CAP = 30


def record_attempt(model: str) -> None:
    """One call to one seat. THE DENOMINATOR (R0570) that makes the blank tally a rate.

    "Blanked 4x" is not a measurement. Four failures out of four calls is a dead seat; four out of
    four hundred is a 1% flake on a free tier, and until now nothing counted the calls, so the two
    were byte-identical to every reader -- L1.57's missing denominator, one subsystem over from
    where it was written.

    IT ALSO UN-WELDS THE FENCE, which is the half that bites today. `seat-chronic-*-unmeasured`
    can currently only clear when a seat BLANKS AGAIN: with no events, recency is unmeasured and
    the defect fires forever, so the fence is lit precisely while the seats are healthy and goes
    quiet only on new failure. That is the inverted-gate class R0492 named, reappearing one level
    up in the instrument built to fix it. An attempt is recorded whether the seat succeeds or
    fails, so health becomes measurable from success -- the only direction that can honestly
    clear it.

    ATTEMPTS ARE THEIR OWN EPOCH, which is why no separate "instrumented since" stamp is needed:
    an attempt recorded at T proves the instrumentation was live at T, so attempts inside the
    window with no blank events inside the window means zero blanks, MEASURED -- not unknown.
    """
    m = refresh(load())
    today = datetime.now(tz=UTC).date()
    att = m.setdefault("seat_attempts", {})
    if not isinstance(att, dict):
        att = m["seat_attempts"] = {}
    per = att.setdefault(model, {})
    per[today.isoformat()] = int(per.get(today.isoformat(), 0)) + 1
    cutoff = (today - timedelta(days=_ATTEMPT_DAY_CAP)).isoformat()
    for mdl in list(att):
        kept = {d: c for d, c in (att[mdl] or {}).items() if d >= cutoff}
        if kept:
            att[mdl] = kept
        else:
            del att[mdl]
    save(m)


def recent_attempts(m: dict[str, object], *, window_days: int) -> dict[str, int] | None:
    """Calls per seat inside `window_days`, or ``None`` when nothing has been recorded.

    ``None`` rather than ``{}`` for the same reason `recent_blanks` returns it: a box that has
    never counted an attempt has no rate evidence, and zero-attempts would read as a 0/0 rate that
    a caller could round to "fine".
    """
    att = m.get("seat_attempts")
    if not isinstance(att, dict) or not att:
        return None
    cutoff = (datetime.now(tz=UTC).date() - timedelta(days=window_days)).isoformat()
    out: dict[str, int] = {}
    for model, days in att.items():
        if not isinstance(days, dict):
            continue  # attrition-ok: a malformed seat block carries no dated counts to window
        n = sum(int(c) for d, c in days.items() if str(d) >= cutoff)
        if n:
            out[str(model)] = n
    return out or None


def blank_rate(m: dict[str, object], *, window_days: int) -> dict[str, tuple[int, int]] | None:
    """{seat: (blanks, attempts)} inside the window, or ``None`` when attempts are unrecorded.

    Keyed on ATTEMPTS, never on blanks: a seat that answered every call in the window has no blank
    events at all, and that is the healthy case the caller most needs to be able to see.
    """
    attempts = recent_attempts(m, window_days=window_days)
    if attempts is None:
        return None
    blanks = recent_blanks(m, window_days=window_days) or {}
    return {seat: (blanks.get(seat, 0), n) for seat, n in attempts.items()}


def audit_payload() -> tuple[str, list[str]]:
    """Return (text_to_append_to_dossier, files_included). Sanitized, budget-bounded."""
    m = refresh(load())
    files = m["files"]
    st = status(m)

    # (A) raw diff since the previous panel run -- the curation-proof part
    sha = m.get("last_panel_sha")
    diff = _git("diff", f"{sha}..HEAD") if sha else _git("log", "-p", "--since=3.days")
    if len(diff) > DIFF_BUDGET_CHARS:
        diff = diff[:DIFF_BUDGET_CHARS] + "\n... [diff truncated at budget -- ask for the rest]"

    # (B0) ALWAYS-class decision surface -- ALWAYS, IN FULL, budget-exempt. This is what lets a
    # reviewer say "add these grounds to the KR miner" instead of "consider more breadth".
    t0_chunks, t0_files, t0_used = [], [], 0
    for rel, _rec in sorted(files.items()):
        if _rec.get("review_class") != 0:
            continue
        fp = ROOT / rel
        if not fp.exists():
            continue
        try:
            body = fp.read_text("utf-8", errors="ignore")
        except Exception:
            continue
        t0_chunks.append(f"\n----- [DECISION SURFACE] {rel} "
                         f"({len(body.splitlines())} lines) -----\n{body}")
        t0_files.append(rel)
        t0_used += len(body)

    # (B) rotating slice: risk-path staleness first, then oldest-audited, then largest
    order = sorted(((k, v) for k, v in files.items() if v.get("review_class") != 0),
                   key=lambda kv: (kv[1].get("review_class", 2),
                                   -_age_days(kv[1].get("last_audited")),
                                   -kv[1].get("loc", 0)))
    chunks, included, used = [], [], 0
    for rel, _rec in order:
        p = ROOT / rel
        if not p.exists():
            continue
        try:
            body = p.read_text("utf-8", errors="ignore")
        except Exception:
            continue
        if used + len(body) > max(0, current_budget(m) - t0_used) and included:
            break
        _la = _rec.get('last_audited') or 'NEVER'
        chunks.append(f"\n----- FILE: {rel} ({len(body.splitlines())} lines, "
                      f"class={_review_class(rel)}, last audited: {_la}) "
                      f"-----\n{body}")
        included.append(rel)
        used += len(body)

    txt = [
        "\n\n" + "=" * 70,
        "## FULL-COVERAGE AUDIT FEED (raw system access -- judge ALL of it)",
        "=" * 70,
        "The prose dossier above is written BY the system being audited. Everything below is "
        "raw and uncurated, so you can flag what the dossier omits. You are explicitly asked "
        "to judge the CODE, not just the narrative: correctness, risk-path safety, silent-"
        "failure modes, dead code, unsafe defaults, and anything the author would not have "
        "thought to summarize.",
        f"\n### COVERAGE STATE: {st['covered']}/{st['total']} files ever audited "
        f"({st['pct']}%). NEVER audited: {len(st['never'])}. "
        f"Stale risk-path (>{RISK_MAX_AGE_D:.0f}d): {len(st['stale_risk'])}. "
        f"Stale other (>{ROTATE_MAX_AGE_D:.0f}d): {len(st['stale_rotate'])}.",
        "If a file you would need to judge a claim is NOT included below, say so explicitly -- "
        "'I could not verify X because file Y was not provided' is a first-class finding here.",
        f"\n### (A) RAW DIFF SINCE LAST PANEL ({'since ' + sha[:8] if sha else 'last 3 days'})\n",
        "```diff\n" + (diff.strip() or "(no changes)") + "\n```",
        f"\n### (B0) DECISION SURFACE [review class: ALWAYS] -- ALWAYS SENT IN FULL "
        f"({len(t0_files)} files, "
        f"{t0_used:,} chars): every miner/digger prompt, every watchlist, coverage map, "
        "operator library, hypothesis + weak-signal + negative-knowledge registries, gap "
        "register and digging charter. You are seeing 100% of what the desk uses to DECIDE. "
        "Your recommendations here must be SPECIFIC (name the prompt, name the ground, name "
        "the operator) -- generic advice is a failed review.\n",
        "```\n" + "".join(t0_chunks) + "\n```",
        f"\n### (B) ROTATING SOURCE REVIEW ({len(included)} files, {used:,} chars, "
        "least-recently-audited first; the rest is under staleness floors)\n",
        "```\n" + "".join(chunks) + "\n```",
    ]
    payload = "\n".join(txt)

    try:                                              # desk sanitizer is the last gate
        from scripts.generate_external_review_doc import sanitize
        clean = sanitize(payload)
        if clean != payload:
            print("coverage: sanitizer redacted secret-shaped content before send")
        payload = clean
    except Exception as e:
        print(f"coverage: sanitize unavailable ({e!r}) -- sending nothing rather than risk it")
        return "", []
    return payload, t0_files + included


def mark_audited(files: list[str], ts: str, mission: str,
                 substantive: int = 0, total_seats: int = 0) -> None:
    """Mark files reviewed ONLY on quorum. Coverage must reflect what was actually READ,
    not what was sent -- a run where seats blanked must not inflate the coverage figure."""
    if total_seats and substantive < max(1, int(QUORUM_FRAC * total_seats)):
        m = refresh(load())
        m.setdefault("failed_runs", []).append(
            {"ts": ts, "mission": mission, "substantive": substantive,
             "of": total_seats, "files_not_credited": len(files)})
        m["failed_runs"] = m["failed_runs"][-20:]
        save(m)
        print(f"coverage: QUORUM FAILED ({substantive}/{total_seats} substantive) -- "
              f"{len(files)} files NOT credited as audited")
        return
    m = refresh(load())
    for rel in files:
        rec = m["files"].get(rel)
        if rec is not None:
            rec["last_audited"] = ts
            rec["audit_count"] = int(rec.get("audit_count", 0)) + 1
            rec["last_mission"] = mission
    m["last_panel_sha"] = (_git("rev-parse", "HEAD").strip() or m.get("last_panel_sha"))
    m["runs"] = int(m.get("runs", 0)) + 1
    save(m)


def main() -> None:
    import sys
    m = refresh(load())
    save(m)
    st = status(m)
    if len(sys.argv) > 1 and sys.argv[1] == "verify":
        print(f"adaptive payload budget : {current_budget(m):,} chars "
              f"(ceiling {CODE_BUDGET_CHARS:,}, floor {CODE_BUDGET_MIN:,})")
        print(f"seat blanks recorded    : {m.get('seat_blanks', {}) or 'none'}")
        print(f"quorum-failed runs      : {len(m.get('failed_runs', []))}")
        for h in m.get("budget_history", [])[-5:]:
            print(f"  budget {h['from']:,} -> {h['to']:,} (blanked {h['blanked']}/{h['of']})")

    print(f"AUDIT COVERAGE: {st['covered']}/{st['total']} files ever audited ({st['pct']}%)")
    print(f"  never audited      : {len(st['never'])}")
    print(f"  stale RISK (money path): {len(st['stale_risk'])} (floor {RISK_MAX_AGE_D:.0f}d)")
    print(f"  stale ROTATE (long tail): {len(st['stale_rotate'])} (floor {ROTATE_MAX_AGE_D:.0f}d)")
    print(f"  TIER-0 always-sent : {st['always_class']} decision-surface files (100% every run)")
    total_loc = sum(r.get("loc", 0) for r in m["files"].values())
    runs_needed = max(1, round(total_loc * 40 / CODE_BUDGET_CHARS))
    print(f"  total LOC in sweep : {total_loc:,}  (~{runs_needed} panel runs per full sweep)")
    for f in sorted(st["never"])[:10]:
        print(f"    NEVER: {f}")


if __name__ == "__main__":
    main()
