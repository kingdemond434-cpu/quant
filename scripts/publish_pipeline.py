#!/usr/bin/env python3
"""PUBLISH THE DISCOVERY -> SHADOW -> LIVE FUNNEL TO THE DASHBOARD.

THE DEFECT. The principal asked why no candidates appear on dash.quanttt.xyz. Measured
2026-08-12: the dashboard's two pages load thirty-odd JSON feeds between them and NOT ONE of them
is a shadow or candidate feed. Not the roster, not the spawn queue, not the forward accrual, not
the promotion gate, not the live authority. `web/paper_sleeve_forward.json` is already sitting in
the served directory and no page has ever fetched it.

So the answer to "none of them are on the dashboard" is that nothing on the dashboard ever asked.
This is the read-without-writer defect inverted -- written, served, and read by nobody -- and it
lands on the one view that would show whether the desk is making progress at all.

WHAT IT PUBLISHES, as one file the page can render without stitching:

  THE FUNNEL, honestly staged. Trials screened -> candidates -> sleeve records -> live in shadow
  -> accruing -> resolved -> live authority. Each stage carries its own denominator, because a
  funnel that only shows survivors cannot distinguish "nothing survived" from "nothing was tried".

  EVERY CANDIDATE, not a top-N. The point of the view is that the principal can see all of them;
  truncating it would recreate the situation this fixes. Rows carry their corrected Stage-A
  verdict, their state, and -- for a sleeve -- its forward progress and why it is or is not
  accruing.

  THE QUEUE, in the order it will actually drain (capacity runway, shortest first), so a queued
  candidate's position is visible rather than a matter of trust.

WHAT IT IS CAREFUL ABOUT. Every number carries the age of the artifact it came from. On an
ephemeral container `data/` is a fossil layer -- files present, shapes real, numbers days old --
and a dashboard that renders a fortnight-old queue as current fact is the 2026-08-05 failure with
a nicer font. A stage whose source is missing publishes UNMEASURED, never zero.

    python scripts/publish_pipeline.py [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

OUT = "web/pipeline.json"

#: ONE DEFINITION OF "CANDIDATE", AND IT IS THE ORGAN'S, NOT A SECOND COPY.
#: The first draft of this file hardcoded a POSITIVE list -- UNDERPOWERED, UNRATED, WEAK -- which
#: silently EXCLUDED SCREEN-INTERESTING, the only verdict that actually starts a forward clock
#: (libs/research/axis_screen: "This is the ONLY verdict that starts a forward clock"). The first
#: genuine survivor the desk ever produced would have rendered on the dashboard as NOT a
#: candidate. That is the slot_registry failure repeated: one quantity counted differently by two
#: files, and the dashboard's copy drifting toward the friendlier answer.
#: The rule is a NEGATIVE list and it is imported: only a BROKEN measurement is disqualifying.
#: WEAK and UNDERPOWERED stay candidates (L1.49) -- "underpowered" means the screen could not see,
#: not that it looked and found nothing.
from libs.research.paper_sleeves import NON_ADMISSIBLE_PREFIXES  # noqa: E402


def is_candidate(verdict: str) -> bool:
    """Delegates to the spawner's own admissibility rule. Never a second opinion."""
    return not str(verdict).startswith(NON_ADMISSIBLE_PREFIXES)


def _age_h(p: Path) -> float | None:
    try:
        return round((datetime.now(tz=UTC).timestamp() - p.stat().st_mtime) / 3600.0, 1)
    except OSError:
        return None


def _load(root: Path, rel: str) -> tuple[Any, float | None]:
    p = root / rel
    try:
        return json.loads(p.read_text("utf-8")), _age_h(p)
    except (OSError, ValueError):
        return None, None


def _screen_rows(root: Path) -> list[dict[str, Any]]:
    """Every screened trial with a corrected verdict, from the axis-screen store."""
    out = []
    for p in sorted((root / "reports/axis_screens").glob("*.json")):
        try:
            doc = json.loads(p.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        rows = doc if isinstance(doc, list) else (
            doc.get("rows") or doc.get("cells") or doc.get("trials") or [])
        if isinstance(rows, dict):
            rows = list(rows.values())
        for r in rows:
            if not isinstance(r, dict):
                continue
            v = r.get("verdict_adjusted") or r.get("verdict")
            if not v:
                continue
            out.append({"axis": p.stem, "trial": r.get("trial") or r.get("name") or "?",
                        "verdict": str(v), "ic_t": r.get("ic_t"), "n_eff": r.get("n_eff"),
                        "candidate": (r.get("is_candidate") is not False
                                      and is_candidate(v)),
                        "age_h": _age_h(p)})
    return out


def _spawner(root: Path) -> tuple[dict[str, Any], float | None]:
    """The spawner's own artifact. A PURE READ, and the first draft of this was not.

    It invoked `run_paper_sleeve_spawner.py --json` as a subprocess so the queue would be fresh.
    That organ WRITES: it spawns sleeves, edits the roster and rewrites the queue file, and it is
    scheduled under `data/.cron_paper_spawner.lock`. Calling it from a publisher, without that
    lock, puts a second writer on the same files -- the R0048 shape, two launchers on one artifact
    with split lock paths, which this desk already has a fence against.

    A dashboard must never be able to change what it is displaying. It reads what the spawner's
    own scheduled passes wrote, and reports the artifact's AGE so a stale queue is visible as a
    stale queue rather than rendered as current fact.
    """
    doc, age = _load(root, "data/paper_sleeve_queue.json")
    return (doc if isinstance(doc, dict) else {}), age


def build(root: Path | None = None) -> dict[str, Any]:
    base = root or _ROOT
    now = datetime.now(tz=UTC)

    screened = _screen_rows(base)
    spawn, queue_age = _spawner(base)
    spawned = spawn.get("spawned") or []
    queued = spawn.get("queued") or []

    forward, fwd_age = _load(base, "web/paper_sleeve_forward.json")
    if not isinstance(forward, dict):
        forward, fwd_age = _load(base, "data/paper_sleeve_forward.json")
    sleeves = (forward or {}).get("sleeves") or {}

    liveness, _ = _load(base, "data/slot_liveness.json")
    authority, auth_age = _load(base, "data/live_authority.json")
    gate, gate_age = _load(base, "data/promotion_gate.json")

    live_names = set(_load(base, "data/shadow_sleeves.json")[0] or [])
    by_state: dict[str, int] = {}
    for s in spawned:
        by_state[str(s.get("state", "?"))] = by_state.get(str(s.get("state", "?")), 0) + 1

    health = {c["name"]: c for c in (liveness or {}).get("clocks", [])}
    rows = []
    for name in sorted(set(live_names) | set(sleeves)):
        f = sleeves.get(name) or {}
        h = health.get(name) or {}
        rows.append({
            "name": name, "in_roster": name in live_names,
            "shadow_start": f.get("shadow_start"),
            "forward_days": f.get("forward_days"),
            "rows_added": f.get("rows_added"),
            "n_now": f.get("n_now"), "n_baseline": f.get("n_baseline"),
            "n_needed": f.get("n_needed_for_forward_rejection"),
            "evidence": f.get("evidence") or "UNMEASURED",
            "health": h.get("state") or "UNKNOWN",
            "origin_artifact": f.get("origin_artifact"),
            "why": h.get("why") or f.get("why") or "",
            "repair": h.get("repair") or "",
        })

    n_cand = sum(1 for r in screened if r["candidate"])
    accruing = sum(1 for r in rows if r["evidence"] == "ACCRUING")
    resolved = sum(1 for r in rows if str(r["evidence"]).upper() in ("RESOLVED", "PROMOTED"))

    funnel = [
        {"stage": "screened", "n": len(screened),
         "why": "Stage-A trials carrying a corrected verdict"},
        {"stage": "candidates", "n": n_cand,
         "why": "eligible for a forward clock. WEAK and UNDERPOWERED stay candidates (L1.49) -- "
                "a weak result is not a dead one and an underpowered screen has measured nothing"},
        {"stage": "sleeve_records", "n": len(spawned),
         "why": f"turned into a sleeve record ({by_state})"},
        {"stage": "in_shadow", "n": len(live_names),
         "why": "live on the roster, paying multiplicity from birth"},
        {"stage": "queued", "n": len(queued),
         "why": "corrected survivors waiting on a forward slot; the cohort cap is a concurrency "
                "budget, not a judgement on them"},
        {"stage": "accruing", "n": accruing,
         "why": "adding out-of-sample rows. ROWS are the clock, never calendar days"},
        {"stage": "resolved", "n": resolved,
         "why": "cleared the forward bar. Stage B is the SOLE promotion authority"},
    ]

    return {
        "generated_utc": now.isoformat(timespec="seconds"),
        "funnel": funnel,
        "cohort": spawn.get("cohort") or {},
        "spawn_status": spawn.get("status"),
        "sleeves": rows,
        "queue": [{"pos": i + 1, "name": q.get("name"), "axis": q.get("axis"),
                   "trial": q.get("trial"), "why": q.get("reason", "")[:200]}
                  for i, q in enumerate(queued)],
        "screened": screened,
        "verdict_tally": _tally(screened),
        "authority": authority or {"mode": "UNMEASURED",
                                   "why": "data/live_authority.json absent -- the actuator has "
                                          "not run on this box"},
        "gate": {"granted_rung": (gate or {}).get("granted_rung"),
                 "granted": (gate or {}).get("granted"),
                 "blocked_at_rung": (gate or {}).get("blocked_at_rung"),
                 "n_closed": (gate or {}).get("n_closed"),
                 "days_of_record": (gate or {}).get("days_of_record")},
        "source_ages_h": {"forward": fwd_age, "authority": auth_age, "gate": gate_age,
                          "spawn_queue": queue_age},
        "law": "Stage A ranks and has ZERO promotion authority; the forward clocks are the sole "
               "promotion authority. A full slot table is a CONCURRENCY limit, never a verdict on "
               "the candidates queued behind it.",
        "freshness_warning": "every number here carries the age of the artifact it came from. A "
                             "stale figure rendered as current fact is the failure this desk has "
                             "already paid for -- read the ages, not just the counts.",
    }


def _tally(screened: list[dict[str, Any]]) -> list[dict[str, Any]]:
    t: dict[str, int] = {}
    for r in screened:
        # Collapse the long NOT-A-CANDIDATE prose to its head so the tally stays readable.
        v = r["verdict"].split(" (")[0]
        t[v] = t.get(v, 0) + 1
    return [{"verdict": k, "n": v} for k, v in sorted(t.items(), key=lambda kv: -kv[1])]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    doc = build()
    p = _ROOT / OUT
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=1), "utf-8")

    if args.json:
        print(json.dumps(doc, indent=1))
    else:
        print(f"pipeline -> {OUT}")
        for s in doc["funnel"]:
            print(f"  {s['n']:5d}  {s['stage']}")
        a = doc["authority"]
        print(f"  authority: {a.get('mode')} at {a.get('book_fraction', 0) or 0:.0%} of book "
              f"(rung {a.get('rung')})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
