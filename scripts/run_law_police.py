#!/usr/bin/env python3
"""THE LAW POLICE -- runs every audit check, grades whether it actually LOOKED, repairs, pages.

WHAT THIS ADDS TO SIXTY EXISTING CHECKS. They all answer "are the laws being broken today?" This
answers the question one level up, which decides whether their answers mean anything: IS THE AUDIT
STILL LOOKING? Three ways a law silently stops being enforced, none of which raises a defect today:

  * a check is deleted from CHECKS -- its defects stop appearing and the report gets BETTER;
  * a check passes VACUOUSLY -- it returns early because its artifact is gone, which is
    indistinguishable from a clean pass, so a dead collector converts a live law into a no-op;
  * a defect disappears and is read as fixed when the detector actually went blind.

Verified 2026-08-05 before building this: nothing in the repo tracks the registered check roster
over time, and nothing uses max_audit's read-probe -- which has recorded the paths every check
touches for weeks -- to ask whether a check that raised nothing evaluated anything at all.

HOW A CHECK IS GRADED. Each runs under the same read-probe max_audit already installs, so the
police sees BOTH what it raised and what it READ. A check that raised nothing and read nothing is
CANNOT-EVALUATE, which is a blind spot, not an all-clear. That single distinction is the
instrument; everything else here is bookkeeping around it.

DELETION IS WEAKENING. The roster is a ratchet: checks may be added freely, and any check that
VANISHES or falls to CANNOT-EVALUATE is a FALL needing a NAMED CAUSE in
data/law_police_causes.json. Unexplained falls page, so the roster cannot be emptied one check at
a time with every report along the way looking healthier.

REPAIR IS NARROW AND TWICE-FENCED. The police repairs only by RE-RUNNING idempotent measurement
organs from an explicit per-defect allowlist, each additionally screened against a never-touch
token list (deadman switch, thresholds, gates, sizing, promotion, deletion). Everything else is
REPORTED for a person. A police force that can rewrite the law is not enforcing it.

    python scripts/run_law_police.py [--no-repair] [--no-page] [--json]

EXIT CODES: 0 watching or blind-spots-only, 1 unexplained regression (the paging condition), 2 the
police itself could not run -- which is the one failure it cannot self-report, so it is loud.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops.law_police import (  # noqa: E402
    BROKEN,
    CANNOT_EVALUATE,
    CLEAN,
    DEFECTIVE,
    CheckState,
    grade_check,
    police,
)

STATE = "data/LAW_POLICE.json"
CAUSES = "data/law_police_causes.json"
OUT = "reports/law_police.json"


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return default


class _Consulted:
    """Counts every EXTERNAL consultation a check makes, not just file reads.

    THE FIRST VERSION OF THIS INSTRUMENT COUNTED FILES ONLY, AND CRIED WOLF ON ITS FIRST RUN.
    It named four blind spots; all four were false. `bnb-funded` and `fee-carry-ratio` query the
    exchange over HTTP, `dig-uncommitted` shells out to `git status --porcelain`, and
    `check-registry` enumerates module globals. None of them opens a file, and every one of them
    genuinely evaluates the desk.

    That mattered enough to fix rather than tune: a police force whose blind-spot alarm is mostly
    false gets ignored, and an ignored alarm is worse than none -- it is the pager problem this
    desk has already paid for once. So evidence means ANY external consultation: a repo path, a
    subprocess, or a network call. A check that makes none of the three has genuinely evaluated
    nothing but its own absence.
    """

    def __init__(self) -> None:
        self.n = 0
        self._patched: list[tuple[Any, str, Any]] = []

    def install(self) -> None:
        import socket
        import subprocess as _sp
        import urllib.request as _ur
        for mod, name in ((_sp, "run"), (_sp, "check_output"), (_sp, "Popen"),
                          (_ur, "urlopen"), (socket, "create_connection")):
            orig = getattr(mod, name, None)
            if orig is None:
                continue

            def wrap(*a: Any, _o: Any = orig, **kw: Any) -> Any:
                self.n += 1
                return _o(*a, **kw)

            self._patched.append((mod, name, orig))
            setattr(mod, name, wrap)

    def remove(self) -> None:
        for mod, name, orig in self._patched:
            setattr(mod, name, orig)
        self._patched = []


def measure(root: Path) -> tuple[list[CheckState], list[str]]:
    """Run every registered check under the read-probe. Returns (grades, defect ids).

    The file probe is max_audit's own -- the police does not reimplement it, because a second
    probe could drift from the one the audit actually uses and then grade a different program than
    the one that runs. The subprocess/network probe is the police's own, installed only for the
    duration of this pass.
    """
    import scripts.max_audit as M

    M._install_read_probe()
    calls = _Consulted()
    calls.install()
    states: list[CheckState] = []
    all_ids: list[str] = []
    for label, fn in M.CHECKS:
        defects: list[Any] = []
        M._RECORDING = []
        calls.n = 0
        raised = False
        try:
            fn(defects)
        except Exception:
            raised = True
        finally:
            seen, M._RECORDING = M._RECORDING or [], None
        # Only paths INSIDE the repo count as evidence. A check that stat()s /usr or its own
        # module file has not consulted the desk, and letting those count would make every check
        # look like it evaluated something.
        evidence = {p for p in seen if str(root) in str(p) and "__pycache__" not in str(p)}
        states.append(grade_check(label, n_defects=len(defects),
                                  n_evidence=len(evidence) + calls.n, raised=raised))
        all_ids += [str(d[0]) for d in defects if isinstance(d, (list, tuple)) and d]
    calls.remove()
    return states, all_ids


def _repair(root: Path, repairs: list[dict[str, str]], *, dry: bool) -> list[dict[str, Any]]:
    """Re-run each allowlisted measurement organ. Never edits a file directly."""
    done: list[dict[str, Any]] = []
    for r in repairs:
        organ = r["organ"]
        if dry:
            done.append({**r, "ran": False, "why_not": "--no-repair"})
            continue
        try:
            proc = subprocess.run(
                [sys.executable, str(root / organ)], cwd=str(root),
                capture_output=True, text=True, timeout=900, check=False)
            done.append({**r, "ran": True, "rc": proc.returncode,
                         "tail": (proc.stdout or proc.stderr or "")[-240:]})
        except subprocess.TimeoutExpired:
            done.append({**r, "ran": True, "rc": None,
                         "tail": "TIMEOUT after 900s -- a repair that hangs is a failure, not a "
                                 "slow success, and it is reported rather than awaited"})
    return done


def run(root: Path | None = None, *, repair: bool = True) -> dict[str, Any]:
    base = root or _ROOT
    prior = _load(base / STATE, {})
    causes = _load(base / CAUSES, {})
    causes = causes if isinstance(causes, dict) else {}

    states, defect_ids = measure(base)
    rep = police(states, prior, defect_ids, causes)
    performed = _repair(base, rep.repairs, dry=not repair)

    by_state: dict[str, int] = {}
    for c in states:
        by_state[c.state] = by_state.get(c.state, 0) + 1

    roster = {c.name: {"state": c.state, "n_evidence": c.n_evidence,
                       "last_seen": _now(),
                       "first_seen": ((prior.get("roster") or {}).get(c.name) or {})
                       .get("first_seen", _now())}
              for c in states}

    # RATCHET, and only upward. The high-water mark is the count of checks that can actually
    # evaluate -- not the count registered, because a roster full of blind checks is not coverage.
    prior_hw = int((prior.get("high_water") or {}).get("evaluating") or 0)
    evaluating = by_state.get(CLEAN, 0) + by_state.get(DEFECTIVE, 0)
    payload: dict[str, Any] = {
        "generated_utc": _now(),
        "verdict": rep.verdict,
        "n_checks": len(states),
        "by_state": by_state,
        "evaluating": evaluating,
        "high_water": {"evaluating": max(prior_hw, evaluating),
                       "prior": prior_hw,
                       "fell": evaluating < prior_hw},
        "roster": roster,
        "roster_diff": rep.diff,
        "unexplained_falls": rep.falls,
        "blind_spots": [c.as_dict() for c in states if c.state == CANNOT_EVALUATE],
        "broken_checks": [c.as_dict() for c in states if c.state == BROKEN],
        "repairs_performed": performed,
        "reported_for_a_person": rep.report_only[:40],
        "n_defects_seen": len(set(defect_ids)),
        "law": ("DELETION IS WEAKENING. Checks may be added freely; a check that VANISHES or "
                "stops evaluating is a FALL and needs a NAMED CAUSE in data/law_police_causes.json. "
                "CANNOT-EVALUATE is a blind spot, NEVER an all-clear -- it is the state that "
                "silently turns a dead artifact into a passing law."),
        "authority": ("REPAIRS BY RE-RUNNING idempotent measurement organs from an explicit "
                      "allowlist, twice-fenced. Never edits a threshold, a gate, a size, the "
                      "deadman switch, or any data. Everything else is reported for a person."),
    }
    (base / STATE).parent.mkdir(parents=True, exist_ok=True)
    (base / STATE).write_text(json.dumps(payload, indent=1) + "\n", "utf-8")
    (base / OUT).parent.mkdir(parents=True, exist_ok=True)
    (base / OUT).write_text(json.dumps(payload, indent=1) + "\n", "utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--no-repair", action="store_true", help="grade and report, repair nothing")
    ap.add_argument("--no-page", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    try:
        rep = run(repair=not args.no_repair)
    except Exception as exc:
        # THE ONE FAILURE THE POLICE CANNOT SELF-REPORT, so it is loud and it is rc 2. A silent
        # police is exactly the condition it exists to detect, one level up.
        print(f"LAW POLICE COULD NOT RUN: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(rep, indent=1))
    else:
        print(f"law police: {rep['verdict']} -- {rep['n_checks']} checks, "
              f"{rep['evaluating']} evaluating (high-water {rep['high_water']['evaluating']}), "
              f"{rep['n_defects_seen']} distinct defect(s)")
        for k in (DEFECTIVE, CLEAN, CANNOT_EVALUATE, BROKEN):
            if rep["by_state"].get(k):
                print(f"   {k:16s} {rep['by_state'][k]}")
        for b in rep["blind_spots"][:8]:
            print(f"  BLIND  {b['name']}: {b['why'][:96]}")
        for f in rep["unexplained_falls"]:
            print(f"  FALL   {f}")
        for r in rep["repairs_performed"]:
            print(f"  REPAIR {r['organ']} for {r['defect']} "
                  f"-> {'rc=' + str(r.get('rc')) if r.get('ran') else r.get('why_not')}")
        if rep["high_water"]["fell"]:
            print(f"  RATCHET FELL: {rep['high_water']['prior']} -> {rep['evaluating']} "
                  "evaluating checks. A fall needs a NAMED CAUSE.")

    if rep["unexplained_falls"] and not args.no_page:
        try:
            from libs.ops.alert_channels import send_all
            send_all(f"LAW POLICE: {len(rep['unexplained_falls'])} unexplained regression(s)",
                     "\n".join(rep["unexplained_falls"][:10])
                     + "\n\nA check vanished or went blind with no recorded cause. The law it "
                       "enforced is unenforced as of this run.")
        except Exception as exc:
            print(f"  (paging failed: {type(exc).__name__}: {exc})", file=sys.stderr)
    print(f"-> {OUT}")
    return 1 if rep["unexplained_falls"] else 0


if __name__ == "__main__":
    sys.exit(main())
