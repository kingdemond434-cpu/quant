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
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "data/audit_coverage.json"

# what the sweep covers -- code + operator contracts (the brain's prompt lives in ops/*.sh)
INCLUDE_GLOBS = ("scripts/*.py", "libs/**/*.py", "ops/*.sh", "ops/*.txt",
                 "tests/**/*.py", "docs/*.md", "docs/research/*.md", "docs/playbooks/*.md")
# never read, never send
EXCLUDE_PARTS = ("secrets", "__pycache__", ".venv", ".git", "node_modules")
EXCLUDE_SUFFIX = (".bak", ".pyc", ".log")

# risk-path files are audited on a tighter clock than everything else
TIER1_PREFIXES = ("libs/execution/", "scripts/run_deadman_switch.py", "scripts/run_cashcarry",
                  "scripts/run_alerts.py", "scripts/run_recorder.py", "scripts/run_ci.py")
TIER1_MAX_AGE_D = 14.0
TIER2_MAX_AGE_D = 30.0

# TIER-0 = the DECISION surface: what a reviewer must see to give SPECIFIC advice rather
# than generic advice ("add these 3 grounds to the JP miner" vs "consider more breadth").
# Ships IN FULL on every run, exempt from the rotating budget, re-audited every run.
TIER0_PREFIXES = (
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
CODE_BUDGET_CHARS = 320_000      # TOTAL payload ceiling (tier-0 + rotating)
CODE_BUDGET_MIN = 40_000         # floor for the ROTATING part; tier-0 always ships
DIFF_BUDGET_CHARS = 60_000
QUORUM_FRAC = 0.6                # >=60% of seats must answer substantively to count
SUBSTANTIVE_CHARS = 400          # shorter than this is not a real review


def _tier(rel: str) -> int:
    if any(rel.startswith(p) for p in TIER0_PREFIXES):
        return 0                                   # decision surface: always sent
    return 1 if any(rel.startswith(p) for p in TIER1_PREFIXES) else 2


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
            rec["loc"] = sum(1 for _ in p.open("r", encoding="utf-8", errors="ignore"))
        except Exception:
            rec["loc"] = 0
        rec["tier"] = _tier(rel)
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
              if r.get("tier") == 1 and _age_days(r.get("last_audited")) > TIER1_MAX_AGE_D]
    stale2 = [f for f, r in files.items()
              if r.get("tier") == 2 and _age_days(r.get("last_audited")) > TIER2_MAX_AGE_D]
    t0 = [f for f, r in files.items() if r.get("tier") == 0]
    return {"total": len(files), "never": never, "stale_tier1": stale1, "stale_tier2": stale2,
            "tier0": len(t0),
            "covered": len(files) - len(never),
            "pct": round(100.0 * (len(files) - len(never)) / max(1, len(files)), 1)}


def current_budget(m: dict) -> int:
    """Largest payload every seat has survived recently (learned, not guessed)."""
    return int(m.get("code_budget_chars", CODE_BUDGET_CHARS))


def tune_budget(blanked: int, total: int) -> int:
    """Shrink hard on any blank, grow gently on a clean run. Called after every panel."""
    m = refresh(load())
    cur = current_budget(m)
    if blanked:
        new = max(CODE_BUDGET_MIN, int(cur * 0.6))   # a blank is a real failure: cut deep
    else:
        new = min(CODE_BUDGET_CHARS, int(cur * 1.15))  # earn size back slowly
    m["code_budget_chars"] = new
    m.setdefault("budget_history", []).append(
        {"blanked": blanked, "of": total, "from": cur, "to": new})
    m["budget_history"] = m["budget_history"][-30:]
    save(m)
    return new


def record_blank(model: str) -> None:
    """Per-seat blank tally -- turns a flaky seat into an evidence-backed swap decision."""
    m = refresh(load())
    m.setdefault("seat_blanks", {})[model] = int(m.get("seat_blanks", {}).get(model, 0)) + 1
    save(m)


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

    # (B0) TIER-0 decision surface -- ALWAYS, IN FULL, budget-exempt. This is what lets a
    # reviewer say "add these grounds to the KR miner" instead of "consider more breadth".
    t0_chunks, t0_files, t0_used = [], [], 0
    for rel, _rec in sorted(files.items()):
        if _rec.get("tier") != 0:
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
    order = sorted(((k, v) for k, v in files.items() if v.get("tier") != 0),
                   key=lambda kv: (kv[1].get("tier", 2),
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
        chunks.append(f"\n----- FILE: {rel} ({len(body.splitlines())} lines, "
                      f"tier{_tier(rel)}, last audited: {_rec.get('last_audited') or 'NEVER'}) "
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
        f"Stale risk-path (>{TIER1_MAX_AGE_D:.0f}d): {len(st['stale_tier1'])}. "
        f"Stale other (>{TIER2_MAX_AGE_D:.0f}d): {len(st['stale_tier2'])}.",
        "If a file you would need to judge a claim is NOT included below, say so explicitly -- "
        "'I could not verify X because file Y was not provided' is a first-class finding here.",
        f"\n### (A) RAW DIFF SINCE LAST PANEL ({'since ' + sha[:8] if sha else 'last 3 days'})\n",
        "```diff\n" + (diff.strip() or "(no changes)") + "\n```",
        f"\n### (B0) DECISION SURFACE -- ALWAYS SENT IN FULL ({len(t0_files)} files, "
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
    print(f"  stale risk-path    : {len(st['stale_tier1'])} (floor {TIER1_MAX_AGE_D:.0f}d)")
    print(f"  stale other        : {len(st['stale_tier2'])} (floor {TIER2_MAX_AGE_D:.0f}d)")
    print(f"  TIER-0 always-sent : {st['tier0']} decision-surface files (100% every run)")
    total_loc = sum(r.get("loc", 0) for r in m["files"].values())
    runs_needed = max(1, round(total_loc * 40 / CODE_BUDGET_CHARS))
    print(f"  total LOC in sweep : {total_loc:,}  (~{runs_needed} panel runs per full sweep)")
    for f in sorted(st["never"])[:10]:
        print(f"    NEVER: {f}")


if __name__ == "__main__":
    main()
