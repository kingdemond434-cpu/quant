"""GRAVEYARD RESURRECTION ENGINE (principal 2026-07-27, Tier-1 #2).

Premise: 'different deaths require different treatment.' A signal killed for NO SIGNAL is dead.
A signal killed for WRONG HORIZON, INSUFFICIENT DATA, or COST is a potential FALSE NEGATIVE -- it
was judged by a weaker court. Four new rails landed 2026-07-23..27 (gapped-window, cohort-
perturbation stability, mandatory power reporting, SUSPECT-LOOKAHEAD), and the harness now reports
n_eff / min_detectable_ic / powered. Anything killed BEFORE those existed is unexamined,
not refuted.

This parses docs/graveyard.md, classifies every entry by CAUSE OF DEATH, and ranks resurrection
candidates. It does NOT resurrect anything -- it produces the queue the brain/CRO works, so
re-testing is evidence-driven rather than nostalgic. Read-only. Run from repo root.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

GY = Path("docs/graveyard.md")
OUT = Path("data/graveyard_resurrection_queue.json")

# cause -> (resurrect_priority 0-5, treatment)
CAUSES = {
    "no_economics": (0, "DEAD -- no mechanism. Do not resurrect without a NEW named mechanism."),
    "wrong_sign": (
        1,
        "Mostly dead. Sign-flipping is p-hacking; only revisit if a mechanism explains the sign.",
    ),
    "crowded": (1, "Dead unless the crowd left -- re-test only with evidence of decrowding."),
    "overfit": (2, "Re-testable ONLY out-of-sample / forward. The original fit is worthless."),
    "regime_artifact": (3, "RESURRECT-ABLE: died in one regime. Re-test conditioned on regime."),
    "costs_killed_edge": (
        3,
        "RESURRECT-ABLE: re-test against the NEW measured cost model + 24h min-hold.",
    ),
    "narrow_breadth": (3, "RESURRECT-ABLE: re-test if the universe widened (more venues/assets)."),
    "no_breadth": (3, "RESURRECT-ABLE: same -- starved, not wrong."),
    "no_edge_daily": (
        5,
        "PRIME RESURRECTION: killed at DAILY horizon only. Horizon search is the exact remedy.",
    ),
    "insufficient": (
        5,
        "PRIME RESURRECTION: underpowered. New harness reports n_eff/min_detectable_ic.",
    ),
    "no_predictive_power": (2, "Re-test only with a different SELECTION criterion, not a new fit."),
    "timing_artifact": (0, "DEAD -- failed de-contamination. Contemporaneous, not leading."),
    "lookahead_artifact": (0, "DEAD -- construction bug. Never resurrect."),
    "unstable_artifact": (0, "DEAD -- sign flipped under cohort perturbation."),
    "no_edge": (1, "Weak. Only with a genuinely new construction."),
    "wrong_orthogonality": (
        2,
        "Redundant with an existing sleeve; revisit only if that sleeve dies.",
    ),
    "redundant": (1, "Duplicate of a live signal. Not independent evidence."),
    "insignificant": (
        4,
        "RESURRECT-ABLE: direction was right but underpowered -- re-test at scale.",
    ),
}


def main() -> None:
    if not GY.exists():
        raise SystemExit("no graveyard")
    rows = [
        ln
        for ln in GY.read_text("utf-8").splitlines()
        if ln.startswith("|") and not set(ln) <= set("|- ")
    ]
    entries = []
    for ln in rows:
        cells = [c.strip() for c in ln.strip("|").split("|")]
        if len(cells) < 3 or cells[0].lower() in ("name", "signal", "strategy"):
            continue
        name, metric = cells[0], cells[1]
        tags = re.findall(r"`([a-z_]+)`", cells[2]) if len(cells) > 2 else []
        note = cells[3] if len(cells) > 3 else ""
        pri = max([CAUSES.get(t, (2, ""))[0] for t in tags], default=2)
        treat = (
            "; ".join({CAUSES.get(t, (2, "unclassified cause"))[1] for t in tags})
            or "UNCLASSIFIED death -- tag it before judging."
        )
        # bonus: anything killed on a purely DAILY test is a horizon-search candidate
        horizon_flag = bool(re.search(r"daily|next-day|1d|4h", (metric + note).lower()))
        entries.append(
            {
                "name": name[:90],
                "tags": tags or ["untagged"],
                "priority": pri,
                "horizon_candidate": horizon_flag,
                "treatment": treat,
                "metric": metric[:110],
            }
        )

    entries.sort(key=lambda e: (-e["priority"], e["name"]))
    print(f"=== GRAVEYARD RESURRECTION QUEUE ({len(entries)} entries) ===\n")
    buckets = {}
    for e in entries:
        buckets.setdefault(e["priority"], []).append(e)
    labels = {
        5: "PRIME (horizon/power remedy exists)",
        4: "STRONG",
        3: "RESURRECT-ABLE (regime/cost/breadth)",
        2: "CONDITIONAL (OOS only)",
        1: "WEAK",
        0: "DEAD (construction/mechanism)",
    }
    for p in sorted(buckets, reverse=True):
        print(f"--- priority {p}: {labels.get(p, '')} -- {len(buckets[p])} entries")
        for e in buckets[p][:8]:
            h = " [HORIZON]" if e["horizon_candidate"] else ""
            print(f"    {e['name'][:74]}{h}")
            print(f"       tags={','.join(e['tags'])}")
        if len(buckets[p]) > 8:
            print(f"    ... +{len(buckets[p]) - 8} more")
        print()
    hz = [e for e in entries if e["horizon_candidate"] and e["priority"] >= 3]
    print(f"=> HORIZON-SEARCH SHORTLIST (priority>=3 AND daily-only test): {len(hz)}")
    for e in hz[:12]:
        print(f"     - {e['name'][:80]}")
    OUT.write_text(
        json.dumps(
            {"updated": datetime.now(tz=UTC).isoformat(), "n": len(entries), "entries": entries},
            indent=1,
        ),
        "utf-8",
    )
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()
