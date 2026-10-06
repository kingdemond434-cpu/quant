#!/usr/bin/env python3
"""THE MANDATE AUDIT, REGENERATED EVERY HOUR FROM THE TREE AND THE BOX'S OWN ARTIFACTS.

    python desks/mt5/research/mandate_audit.py           # hourly leg `mandate_audit`
    python desks/mt5/research/mandate_audit.py --json

WHY (ASIA-0931, principal 2026-10-05 PART XXXVII; built 2026-10-06). The three standing mandates
(ASIA_CHINA_FIRST, breadth_law, ROMAN_QUANT_GUILD) were audited once, by hand, into 3,601 rows
with one of thirteen states each. That file lived outside the repo and nothing re-ran it, so a
row that started running, or a module that was deleted, read the same as on the day of the
audit. Prose status drifts the moment code changes (completion_ledger's lesson).

WHAT IT DOES. The 2026-10-06 audit is the BASELINE (desks/mt5/data/mandate_audit/), with the
UNOWNED-row owner assignment applied. The audit graded each row against its REQUIREMENT, not its
host module: a requirement whose host module exists and runs hourly can still be CODED, because
the behaviour it asks for is not in that module. So file presence never promotes a row. Every
pass measures, from the tree and this host's artifacts:

    module present     each `path:line` the row names still exists in the tree
    leg present        each hourly-cycle leg the audit credited the row with still runs
    artifact fresh     an output artifact carries its own stamp younger than FRESH_H (an
                       untracked file may fall back to its mtime; a checkout's mtime is not a run)

and moves a row only on evidence about THAT row:

    REGRESSION   every named module gone -> ABSENT; every credited leg gone -> CODED.
    RUNNING      an audited SCHEDULED row whose output artifact is fresh. The audit could not
                 see the box's artifacts, which is why it read RUNNING 0; this is that reading.
    CLAIMS       an owner thread moves an ABSENT/CODED/WIRED/SCHEDULED row by registering its
                 evidence in desks/mt5/data/mandate_audit/claims.json: `code` as `path::symbol`
                 (the symbol must be defined there), `tests` that exist and name the module, a
                 `leg` the hourly cycle runs, `artifacts` it writes. Verified stage by stage; the
                 row takes the highest stage that holds (CODED needs code and a test, SCHEDULED
                 adds the leg, RUNNING adds a fresh artifact). A failing claim changes nothing
                 and is listed with its reason.

WHAT IT NEVER DOES. It does not promote a row past RUNNING: PRODUCING_DATA, PRODUCING_CELLS,
JUDGED, FORWARD, LIVE and PROVEN need evidence (cells, verdicts, fills) a file cannot show, so
those audited states are KEPT and marked `evidence_stale` when none of their output artifacts is
fresh here. BLOCKED and UNMEASURED stay unless their own artifact runs. A row that names no
module keeps its audited state with `measured: UNMEASURED` (L1.28a).

Writes desks/mt5/reports/MANDATE_AUDIT.json. Read by the CRO pass (STEP 4B, D13 and D41) and by
the unfinished-work tracker.
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import subprocess
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
BASELINE = DESK / "data" / "mandate_audit" / "baseline_2026-10-06.json.gz"
CLAIMS = DESK / "data" / "mandate_audit" / "claims.json"
OUT = DESK / "reports" / "MANDATE_AUDIT.json"

#: Files whose text decides whether a leg runs.
SCHEDULER_FILES: tuple[str, ...] = (
    "desks/mt5/research/hourly_cycle.py", "desks/mt5/research/daily_cycle.py",
)
#: Older than this, an artifact does not show its organ running. 26h admits daily organs.
FRESH_H = 26.0
#: Files read per artifact directory when finding its newest run.
DIR_SCAN_MAX = 2000

STATES: tuple[str, ...] = (
    "ABSENT", "CODED", "WIRED", "SCHEDULED", "RUNNING", "PRODUCING_DATA", "PRODUCING_CELLS",
    "JUDGED", "FORWARD", "LIVE", "PROVEN", "BLOCKED", "UNMEASURED",
)
#: Stages a claim or a fresh artifact may move a row between.
CODE_STAGES: tuple[str, ...] = ("ABSENT", "CODED", "WIRED", "SCHEDULED", "RUNNING")
EVIDENCE_STAGES: tuple[str, ...] = (
    "PRODUCING_DATA", "PRODUCING_CELLS", "JUDGED", "FORWARD", "LIVE", "PROVEN",
)
_STAMPS = ("generated_utc", "generated_at", "at", "checked_at", "measured_at", "ts")
_LEG_RE = re.compile(r'_costed\(\s*"([A-Za-z0-9_]+)"')
_WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")


def load_baseline(path: Path = BASELINE) -> dict[str, Any]:
    return json.loads(gzip.decompress(path.read_bytes()))


def load_claims(path: Path = CLAIMS) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    claims = doc.get("claims") if isinstance(doc, dict) else None
    return claims if isinstance(claims, dict) else {}


def _ts(x: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(x).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _rel_path(entry: Any) -> str | None:
    """`desks/mt5/x.py:120` -> `desks/mt5/x.py`; prose and absolute shared-folder paths -> None."""
    s = str(entry).strip()
    s = s.split()[0] if s else ""
    s = re.sub(r":\d+$", "", s)
    if not s or s.startswith("/") or "/" not in s:
        return None
    return s


class Tree:
    """What the hourly cycle runs and what the tree holds, read once per pass."""

    def __init__(self, root: Path = ROOT, tracked: set[str] | None = None) -> None:
        self.root = root
        self.sched_text = ""
        for f in SCHEDULER_FILES:
            try:
                self.sched_text += (root / f).read_text("utf-8", errors="replace") + "\n"
            except OSError:
                continue
        self.legs = set(_LEG_RE.findall(self.sched_text))
        self.tracked = tracked if tracked is not None else self._git_tracked()

    def _git_tracked(self) -> set[str]:
        try:
            out = subprocess.run(["git", "-C", str(self.root), "ls-files"], capture_output=True,
                                 text=True, timeout=60, check=False).stdout
        except (OSError, subprocess.SubprocessError):
            return set()
        return set(out.splitlines())

    def exists(self, rel: str) -> bool:
        return (self.root / rel).exists()

    def legs_named(self, scheduler: str) -> list[str]:
        if not scheduler or scheduler.strip().upper().startswith("NONE"):
            return []
        return sorted({w for w in _WORD_RE.findall(scheduler) if w in self.legs})

    def defines(self, rel: str, symbol: str) -> bool:
        try:
            src = (self.root / rel).read_text("utf-8", errors="replace")
        except OSError:
            return False
        pat = rf"^\s*(?:async\s+def|def|class)\s+{re.escape(symbol)}\b|^{re.escape(symbol)}\s*[:=]"
        return re.search(pat, src, re.M) is not None

    def age_h(self, rel: str, now: datetime) -> float | None:
        """Age from the artifact's own stamp; an untracked file may fall back to its mtime."""
        p = self.root / rel
        if p.is_dir():
            # A directory runs when its newest file does; the directory's own mtime is the
            # checkout's, not a run. Bounded: a lake of files is sampled, never walked whole.
            ages = []
            for i, f in enumerate(sorted(p.rglob("*"))):
                if i >= DIR_SCAN_MAX:
                    break
                if f.is_file():
                    h = self.age_h(f.relative_to(self.root).as_posix(), now)
                    if h is not None:
                        ages.append(h)
            return min(ages) if ages else None
        if not p.exists():
            return None
        stamp = None
        if p.suffix == ".json":
            try:
                doc = json.loads(p.read_text("utf-8-sig"))
            except (OSError, ValueError):
                doc = None
            if isinstance(doc, dict):
                for k in _STAMPS:
                    stamp = _ts(doc.get(k)) if doc.get(k) else None
                    if stamp:
                        break
        if stamp is None and rel not in self.tracked:
            try:
                stamp = datetime.fromtimestamp(p.stat().st_mtime, tz=UTC)
            except OSError:
                return None
        if stamp is None:
            return None
        return round((now - stamp).total_seconds() / 3600.0, 2)


def measure(row: dict[str, Any], tree: Tree, now: datetime) -> dict[str, Any]:
    """The facts about one audited row on this host, separate from any grading."""
    mods = [m for m in (_rel_path(x) for x in row.get("module") or []) if m]
    present = [m for m in mods if tree.exists(m)]
    audit_legs = list(row.get("audit_legs") or [])
    legs_now = [g for g in audit_legs if g in tree.legs]
    arts = [a for a in (_rel_path(x) for x in row.get("output_artifacts") or []) if a]
    ages = {a: tree.age_h(a, now) for a in arts}
    fresh = [a for a, h in ages.items() if h is not None and h <= FRESH_H]
    return {"modules_named": len(mods), "modules_present": len(present),
            "legs_credited": audit_legs, "legs_running": legs_now,
            "artifacts_named": len(arts), "artifacts_fresh": len(fresh),
            "artifact_age_h": {a: h for a, h in ages.items() if h is not None}}


def verify_claim(claim: dict[str, Any], tree: Tree, now: datetime) -> tuple[str | None, str]:
    """(highest stage the claim proves, why). None when it proves nothing."""
    code = [str(c) for c in claim.get("code") or []]
    if not code:
        return None, "claim names no code"
    mods = []
    for c in code:
        path, _, sym = c.partition("::")
        if not tree.exists(path):
            return None, f"{path} does not exist"
        if sym and not tree.defines(path, sym):
            return None, f"{sym} is not defined in {path}"
        if not sym:
            return None, f"{c} names no symbol (path::symbol)"
        mods.append(Path(path).stem)
    tests = [str(t) for t in claim.get("tests") or []]
    named = False
    for t in tests:
        try:
            src = (tree.root / t).read_text("utf-8", errors="replace")
        except OSError:
            return None, f"test {t} does not exist"
        named = named or any(m in src for m in mods)
    if not named:
        return None, "no claimed test names the claimed module"
    leg = str(claim.get("leg") or "")
    if not leg:
        return "CODED", "code and test verified; no leg claimed"
    if leg not in tree.legs:
        return "CODED", f"code and test verified; leg {leg} is not run by the hourly cycle"
    arts = [a for a in (_rel_path(x) for x in claim.get("artifacts") or []) if a]
    fresh = [a for a in arts if (h := tree.age_h(a, now)) is not None and h <= FRESH_H]
    if fresh:
        return "RUNNING", f"leg {leg} runs; {len(fresh)}/{len(arts)} artifact(s) fresh"
    return "SCHEDULED", (f"leg {leg} runs; no claimed artifact fresh on this host" if arts
                         else f"leg {leg} runs; the claim names no artifact")


def grade(audited: str, m: dict[str, Any], claim_stage: str | None) -> tuple[str, bool, str]:
    """(state, evidence_stale, why). Moves only on evidence about this row."""
    if m["modules_named"] and not m["modules_present"] and audited not in (
            "ABSENT", "BLOCKED", "UNMEASURED"):
        return "ABSENT", False, f"regressed: none of its {m['modules_named']} module(s) exists"
    if audited in EVIDENCE_STAGES:
        stale = m["artifacts_fresh"] == 0
        return audited, stale, ("audited evidence kept; no output artifact fresh here" if stale
                                else "audited evidence kept; an output artifact is fresh")
    state, why = audited, "as audited"
    if audited in ("SCHEDULED", "WIRED") and m["legs_credited"] and not m["legs_running"]:
        state, why = "CODED", "regressed: no leg the audit credited still runs"
    if state == "SCHEDULED" and m["artifacts_fresh"]:
        state, why = "RUNNING", f"scheduled and {m['artifacts_fresh']} output artifact(s) fresh"
    if audited in ("BLOCKED", "UNMEASURED") and m["legs_running"] and m["artifacts_fresh"]:
        state, why = "RUNNING", "its leg runs and its output artifact is fresh"
    if claim_stage and state in CODE_STAGES and (
            CODE_STAGES.index(claim_stage) > CODE_STAGES.index(state)):
        state, why = claim_stage, "verified claim"
    return state, False, why


def build(now: datetime | None = None, baseline: dict[str, Any] | None = None,
          tree: Tree | None = None, claims: dict[str, Any] | None = None) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    base = baseline or load_baseline()
    tree = tree or Tree()
    claims = load_claims() if claims is None else claims
    rows: list[dict[str, Any]] = []
    claim_log: list[dict[str, Any]] = []
    for r in base["requirements"]:
        rid = r["id"]
        cstage, cwhy = None, ""
        if rid in claims:
            try:
                cstage, cwhy = verify_claim(claims[rid], tree, now)
            except Exception as exc:     # a claim that cannot be checked proves nothing
                cstage, cwhy = None, f"{type(exc).__name__}: {exc}"[:200]
            claim_log.append({"id": rid, "by": claims[rid].get("by"), "proves": cstage,
                              "why": cwhy})
        try:
            m = measure(r, tree, now)
            state, stale, why = grade(r["state"], m, cstage)
        except Exception as exc:         # a row that cannot be measured keeps its audit
            m, state, stale = {}, r["state"], False
            why = f"unmeasured: {type(exc).__name__}: {exc}"[:200]
        rows.append({
            "id": rid, "mandate": rid.split("-")[0], "source": r.get("source"),
            "requirement": r.get("requirement"), "owner_thread": r.get("owner_thread"),
            "state": state, "audited_state": r["state"], "changed": state != r["state"],
            "why": why, "evidence_stale": stale, **m,
            "blocker": r.get("blocker"), "next_repair": r.get("next_repair"),
        })
    per_state = Counter(r["state"] for r in rows)
    per_mandate: dict[str, Counter] = {}
    per_owner: dict[str, Counter] = {}
    for r in rows:
        per_mandate.setdefault(r["mandate"], Counter())[r["state"]] += 1
        per_owner.setdefault(r["owner_thread"] or "UNOWNED", Counter())[r["state"]] += 1
    below = ("ABSENT", "CODED", "WIRED", "BLOCKED", "UNMEASURED")
    at_least_scheduled = sum(1 for r in rows if r["state"] not in below)
    return {
        "generated_utc": now.isoformat(timespec="seconds"),
        "baseline": {"file": str(BASELINE.relative_to(ROOT)),
                     "audited_at": base.get("generated_at"), "audited_sha": base.get("live_sha"),
                     "owner_overlay": base.get("owner_overlay")},
        "n": len(rows),
        "counts_per_state": {s: per_state.get(s, 0) for s in STATES},
        "counts_per_mandate": {k: {s: v[s] for s in STATES if v.get(s)}
                               for k, v in sorted(per_mandate.items())},
        "counts_per_owner": {k: {s: v[s] for s in STATES if v.get(s)}
                             for k, v in sorted(per_owner.items())},
        "unowned": sum(per_owner.get("UNOWNED", Counter()).values()),
        "share_at_least_scheduled": round(at_least_scheduled / max(len(rows), 1), 4),
        "running": per_state.get("RUNNING", 0),
        "changed_vs_audit": sum(1 for r in rows if r["changed"]),
        "regressed": sum(1 for r in rows if r["why"].startswith("regressed")),
        "evidence_stale": sum(1 for r in rows if r["evidence_stale"]),
        "claims": {"n": len(claim_log), "verified": sum(1 for c in claim_log if c["proves"]),
                   "rows": claim_log},
        "rule": "rows move only on evidence about the row: a regression (module or credited "
                "leg gone), a fresh stamped output artifact on an audited SCHEDULED row, or a "
                "verified claim; file presence never promotes; evidence stages are kept from "
                "the audit and flagged evidence_stale when no output artifact is fresh",
        "valid_until": (now + timedelta(hours=3)).isoformat(timespec="seconds"),
        "rows": rows,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    doc = build()
    if not a.dry_run:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        tmp = OUT.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
        tmp.replace(OUT)
    if a.json:
        print(json.dumps({k: v for k, v in doc.items() if k != "rows"}, default=str))
    else:
        print(f"mandate_audit: {doc['n']} rows, RUNNING {doc['running']}, "
              f">=SCHEDULED {doc['share_at_least_scheduled']:.1%}, changed "
              f"{doc['changed_vs_audit']} (regressed {doc['regressed']}), claims "
              f"{doc['claims']['verified']}/{doc['claims']['n']}, unowned {doc['unowned']}")
        print("  " + ", ".join(f"{k} {v}" for k, v in doc["counts_per_state"].items() if v))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
