#!/usr/bin/env python3
"""ORGAN LIVENESS (R0144) -- is every scheduled organ actually PRODUCING?

PRINCIPAL ORDER (2026-07-31): *"make sure all miners etc run, just do it all yourself, don't tell
me to check -- you make sure all cycles are running as intended."*

That instruction is correct and it exposed a real hole. The desk could already check two things:
`check_scheduler_manifest.py` compares the manifest against `crontab -l` (is the line INSTALLED),
and `check_exploration.py` checks freshness for six named exploration organs. Nothing checked the
question that actually matters for the other hundred-odd lines: **did this organ produce anything
recently?**

Those are genuinely different failures and only the third is the one that costs alpha:

    installed but never runs   -- wrong path, missing venv, a lock never released
    runs but produces nothing  -- auth expired, quota exhausted, an API gone 451
    produces but is stale      -- the cadence silently slipped

An organ can pass the manifest check, appear in `crontab -l`, and have emitted nothing for a week.
That is exactly how a miner goes dark unnoticed: nothing errors, no page fires, and the board stays
green because the board was only ever checking that the LINE existed.

HOW IT WORKS. The manifest already carries the two facts needed, on 79 of its entries:
a cron schedule, and an `# EVIDENCE: script -> artifact` line naming what the organ writes. This
parses both, converts the schedule into an expected interval, and compares against the artifact's
real age. No new bookkeeping -- the manifest was already the genome, it just was not being read
this way.

TOLERANCE IS 3x THE CADENCE, deliberately loose. A single missed tick is a machine hiccup; three
consecutive is a dead organ. A tighter tolerance produces a board that is red most mornings, and a
board that is red most mornings is one nobody reads -- which is the failure this organ exists to
end, not to reproduce.

NEVER-PRODUCED IS ITS OWN STATE, not a very old STALE. An organ that has never once written its
artifact was never working, which is a different diagnosis (wiring) from one that stopped (auth,
quota, upstream). Collapsing them would send someone to debug the wrong thing.

    python scripts/check_organ_liveness.py [--report-only] [--json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.lawful import guard as _law_guard  # noqa: E402

#: 3 consecutive missed cadences before an organ is called dead. One miss is a hiccup; three is a
#: pattern. Loose on purpose -- a board that is red most mornings is a board nobody reads.
STALE_MULTIPLE = 3.0
#: Floor on the tolerance so a */5 organ is not declared dead 15 minutes after a reboot. 2h is
#: about the shortest window in which "it did not run" is distinguishable from "the box restarted".
MIN_TOLERANCE_H = 2.0


def cadence_hours(cron: str) -> float | None:
    """Expected hours between runs, from a 5-field cron expression."""
    parts = cron.split()
    if len(parts) < 5:
        return None
    m, h, dom, _mon, dow = parts[:5]

    def count(field: str, span: int) -> int:
        if field.startswith("*/"):
            try:
                return max(1, span // int(field[2:]))
            except ValueError:
                return 1
        if field == "*":
            return span
        return len([x for x in field.split(",") if x])
    per_day = count(m, 60) * count(h, 24)
    if dow != "*":
        per_day *= len([x for x in dow.split(",") if x]) / 7.0
    if dom != "*" and dom.startswith("*/"):
        try:
            per_day /= float(dom[2:])
        except ValueError:
            # NOT swallowed: an unparseable day-of-month means the cadence is UNKNOWN, and a
            # wrong cadence produces a wrong tolerance -- which is how this fence would report a
            # live organ as dead, or a dead one as fine. Refuse to guess.
            return None
    elif dom != "*":
        per_day /= 30.0
    return 24.0 / per_day if per_day > 0 else None


def parse_manifest(text: str) -> list[dict[str, Any]]:
    """(schedule, script, artifacts) per scheduled line, from the EVIDENCE block above it."""
    out: list[dict[str, Any]] = []
    evidence: str | None = None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("# EVIDENCE:"):
            evidence = s[len("# EVIDENCE:"):].strip()
            continue
        if s.startswith("#") or not s:
            continue
        if not re.match(r"^[\d*]", s) or "SYSTEMD" in s:
            evidence = None if s.startswith("SYSTEMD") else evidence
            continue
        cron = " ".join(s.split()[:5])
        script = None
        ms = re.search(r"((?:scripts|ops)/[\w./-]+\.(?:py|sh))", s)
        if ms:
            script = ms.group(1)
        arts: list[str] = []
        if evidence and "->" in evidence:
            tail = evidence.split("->", 1)[1]
            # SEPARATORS ARE '+', ',' AND ';' -- the first version missed the semicolon, so
            # `data/law_gate.json; docs/CONSTITUTION.md L1.37` parsed as `data/law_gate.json;`
            # and every such organ read NEVER-PRODUCED. That is worse than no fence: a board
            # that is wrongly red gets disabled, which is precisely the failure this exists to
            # end. Trailing punctuation is stripped for the same reason.
            for tok in re.split(r"[+,;]", tail):
                tok = tok.strip().split()[0] if tok.strip() else ""
                tok = tok.strip(";,.)([]")
                # ONLY data/ PATHS COUNT. An EVIDENCE line often CITES a law
                # (`-> data/x.json; docs/CONSTITUTION.md L1.37`), and a citation is not an output.
                # Counting it would satisfy liveness with a static file that never changes, so
                # every organ citing a law would read FRESH forever -- a false GREEN, which is
                # strictly worse than the false RED the semicolon bug produced.
                if not tok or not tok.endswith((".json", ".jsonl")):
                    continue
                tok = tok if "/" in tok else f"data/{tok}"
                if not tok.startswith("data/"):
                    continue
                arts.append(tok)
        out.append({"cron": cron, "script": script, "artifacts": arts,
                    "cadence_h": cadence_hours(cron)})
        evidence = None
    return out


def audit(root: Path | None = None, *, now: float | None = None) -> dict[str, Any]:
    root = root or _ROOT
    now = now if now is not None else time.time()
    try:
        text = (root / "ops/crontab.manifest").read_text("utf-8", errors="ignore")
    except OSError as exc:
        return {"status": "UNMEASURED", "detail": f"manifest unreadable: {exc}", "organs": []}
    rows = parse_manifest(text)
    organs: list[dict[str, Any]] = []
    for r in rows:
        if not r["artifacts"] or not r["cadence_h"]:
            continue                       # no declared evidence: check_build_standard's problem
        tol = max(MIN_TOLERANCE_H, r["cadence_h"] * STALE_MULTIPLE)
        ages = []
        for a in r["artifacts"]:
            p = root / a
            ages.append((now - p.stat().st_mtime) / 3600.0 if p.exists() else None)
        fresh = [x for x in ages if x is not None]
        if not fresh:
            state, age = "NEVER-PRODUCED", None
        else:
            age = min(fresh)
            state = "FRESH" if age <= tol else "STALE"
        organs.append({"script": r["script"], "cron": r["cron"],
                       "cadence_h": round(r["cadence_h"], 2), "tolerance_h": round(tol, 2),
                       "artifacts": r["artifacts"],
                       "age_h": None if age is None else round(age, 2), "state": state})
    dead = [o for o in organs if o["state"] == "NEVER-PRODUCED"]
    stale = [o for o in organs if o["state"] == "STALE"]
    status = ("UNMEASURED" if not organs else
              "DARK" if dead or stale else "OK")
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "law": "L1.28a/L1.28c -- a scheduled line that produces nothing is not a running organ. "
               "Installed, running, and PRODUCING are three different facts and only the third "
               "is worth anything.",
        "status": status,
        "n_checked": len(organs), "n_fresh": len(organs) - len(dead) - len(stale),
        "never_produced": [o["script"] for o in dead],
        "stale": [{"script": o["script"], "age_h": o["age_h"], "tolerance_h": o["tolerance_h"]}
                  for o in stale],
        "organs": organs,
        "diagnosis": ("NEVER-PRODUCED means WIRING (path, venv, lock) -- it was never working. "
                      "STALE means it STOPPED (auth, quota, upstream 451). Different repairs, so "
                      "they are never collapsed into one state."),
        "detail": (f"{len(organs) - len(dead) - len(stale)}/{len(organs)} scheduled organs with "
                   f"declared evidence produced within their own cadence"
                   + (f"; NEVER PRODUCED: {', '.join(o['script'] or '?' for o in dead)}"
                      if dead else "")
                   + (f"; STALE: {', '.join(o['script'] or '?' for o in stale)}" if stale else "")),
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = audit()
    out = _ROOT / "data/organ_liveness.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"organ liveness (L1.28c): {rep['status']} -- {rep['detail'][:200]}")
        for o in rep["organs"]:
            if o["state"] != "FRESH":
                print(f"  {o['state']:<16}{o['script']!s:<38}"
                      f"age={o['age_h']} tol={o['tolerance_h']}h")
    if args.report_only:
        return 0
    return 2 if rep["status"] == "DARK" else 0


if __name__ == "__main__":
    sys.exit(main())
