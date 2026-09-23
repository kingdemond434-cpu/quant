"""NEGATIVE KNOWLEDGE LIBRARY -- failures as a queryable institutional asset.

The graveyard is PROSE: a human/LLM must read 44 markdown rows to know whether an idea was already
killed. That is why the 2026-07-27 breadth sweep re-suggested Bithumb/Coinone/Bitso hours after they
were refuted. Prose cannot be queried, so knowledge that exists is functionally absent.

This converts every failure into a STRUCTURED record with the one field prose always omits:
REVERSAL CONDITIONS -- what would have to change for this to be worth retesting. Without it a
graveyard is a tombstone; with it, it is a watchlist.

Every record carries:
  what failed | failure class | evidence | conditions under which failure may reverse |
  revisit trigger | whether the trigger is CURRENTLY MET

The last field is the point: the library actively tells you which dead ideas have become live
again, instead of waiting for someone to remember them. Failures stop being sunk cost and become
a monitored option.

Read-only. Run from repo root, cheap enough for daily cadence.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GRAVE = ROOT / "docs/graveyard.md"
LEDGER = ROOT / "data/decision_ledger.json"
OUT = ROOT / "data/negative_knowledge.json"

# failure class -> (permanence, what would have to change, machine-checkable trigger)
CLASSES = {
    "lookahead_artifact": ("PERMANENT", "nothing -- the construction was wrong", None),
    "timing_artifact": ("PERMANENT", "nothing -- signal was contemporaneous, not leading", None),
    "unstable_artifact": ("PERMANENT", "nothing -- sign flipped under cohort perturbation", None),
    "position_overlap_artifact": ("PERMANENT", "nothing -- mechanical PnL carry", None),
    "no_economics": ("NEAR-PERMANENT", "a NEW named causal mechanism is proposed", None),
    "wrong_sign": (
        "NEAR-PERMANENT",
        "a mechanism explains the sign (flipping alone is p-hacking)",
        None,
    ),
    "redundant": (
        "CONDITIONAL",
        "the signal it duplicates is retired or diverges",
        "live_axis_retired",
    ),
    "crowded": ("CONDITIONAL", "evidence the crowd left (volume//spread/decay)", "crowding_drop"),
    "costs_killed_edge": (
        "REVERSIBLE",
        "measured costs fall or hold period lengthens",
        "cost_model_improved",
    ),
    "narrow_breadth": ("REVERSIBLE", "the tradeable universe widens", "universe_widened"),
    "no_breadth": ("REVERSIBLE", "more venues/assets carry the signal", "universe_widened"),
    "regime_artifact": ("REVERSIBLE", "a different regime arrives", "regime_changed"),
    "insignificant": (
        "REVERSIBLE",
        "a larger sample / more power becomes available",
        "more_data_available",
    ),
    "no_edge_daily": ("REVERSIBLE", "test at a different horizon", "horizon_untested"),
    "no_predictive_power": ("REVERSIBLE", "a different SELECTION criterion, not a refit", None),
    "overfit": ("CONDITIONAL", "clean out-of-sample or forward evidence only", "oos_available"),
    "wrong_orthogonality": ("CONDITIONAL", "the sleeve it duplicated dies", "live_axis_retired"),
    "no_edge": ("NEAR-PERMANENT", "a genuinely new construction of the same data", None),
    "insufficient": (
        "REVERSIBLE",
        "data volume grows past the power threshold",
        "more_data_available",
    ),
}


def triggers_met() -> dict[str, tuple[bool, str]]:
    """Evaluate which reversal triggers are CURRENTLY satisfied -- the live half of the library."""
    out: dict[str, tuple[bool, str]] = {}

    # horizon_untested: was the horizon search ever run on this class?
    hz = ROOT / "data/horizon_discovery.json"
    out["horizon_untested"] = (
        not hz.exists(),
        "horizon sweep has run (1d-90d)" if hz.exists() else "no horizon sweep on record",
    )

    # more_data_available: are forward clocks accruing rows?
    clocks = list((ROOT / "data").glob("*.jsonl"))
    rows = sum(1 for c in clocks[:40] for _ in c.open("r", encoding="utf-8", errors="ignore"))
    out["more_data_available"] = (rows > 0, f"{rows} rows across {len(clocks)} clocks accruing")

    # oos_available: does a held-out OOS validator exist?
    # Was keyed on scripts/backfill_onchain_oos.py -- one crypto-axis backfill script, deleted
    # 2026-09-05 with the on-chain axis. Re-keyed on the LIBRARY that does the work rather than on
    # any single caller, which is the more honest question anyway: this trigger asks "can a dead
    # idea be re-tested out of sample yet?", and the answer depends on the validator existing, not
    # on which script last invoked it. Keyed to a script name, it would have answered False for
    # ever the moment that one caller was retired, silently stopping the whole revival path.
    oos = ROOT / "libs/validation/walk_forward.py"
    out["oos_available"] = (
        oos.exists(),
        "held-out OOS validator exists" if oos.exists() else "no OOS tool",
    )

    # cost_model_improved: is there a measured cost model?
    # Was data/cost_model.json, written by run_cost_model.py from the retired L2 tape (both gone
    # 2026-09-05). The MT5 desk's own cost surface is the successor artifact and answers the same
    # question -- "are costs measured rather than assumed?" -- for the market this desk trades.
    cm = ROOT / "desks/mt5/data/cost_surface.json"
    out["cost_model_improved"] = (
        cm.exists(),
        "measured MT5 cost surface present" if cm.exists() else "none",
    )

    # live_axis_retired: has any tracked axis been retired?
    # Was scripts/run_axis_shadows.py (deleted 2026-09-05); the retirement notices were prose
    # inside that one module. Read the clock registry instead, which is where a retirement is
    # RECORDED rather than commented -- a stronger source, and one that cannot go quiet because a
    # single script was rewritten.
    sh = ROOT / "libs/research/clock_registry.py"
    txt = sh.read_text("utf-8") if sh.exists() else ""
    out["live_axis_retired"] = (
        "RETIRED" in txt,
        "an axis has been retired" if "RETIRED" in txt else "no retirements yet",
    )

    out["regime_changed"] = (False, "no regime-change detector wired yet")
    out["crowding_drop"] = (False, "no crowding monitor wired yet")
    out["universe_widened"] = (False, "universe size not tracked over time yet")
    return out


def main() -> None:
    if not GRAVE.exists():
        raise SystemExit("no graveyard")
    trig = triggers_met()
    records = []
    for ln in GRAVE.read_text("utf-8").splitlines():
        if not ln.startswith("|") or set(ln) <= set("|- "):
            continue
        cells = [c.strip() for c in ln.strip("|").split("|")]
        if len(cells) < 3 or cells[0].lower() in ("name", "signal", "strategy"):
            continue
        tags = re.findall(r"`([a-z_]+)`", cells[2])
        if not tags:
            tags = ["untagged"]
        perms = [CLASSES.get(t, ("UNKNOWN", "unclassified -- tag it", None)) for t in tags]
        # the WEAKEST permanence governs: one reversible cause makes the whole record revisitable
        order = {
            "REVERSIBLE": 0,
            "CONDITIONAL": 1,
            "NEAR-PERMANENT": 2,
            "PERMANENT": 3,
            "UNKNOWN": 1,
        }
        perm = min((p[0] for p in perms), key=lambda x: order.get(x, 1))
        conds = "; ".join(dict.fromkeys(p[1] for p in perms))
        tkeys = [p[2] for p in perms if p[2]]
        met = [(k, trig[k][1]) for k in tkeys if k in trig and trig[k][0]]
        records.append(
            {
                "what": cells[0][:100],
                "classes": tags,
                "permanence": perm,
                "reversal_conditions": conds,
                "triggers": tkeys,
                "triggers_met": [k for k, _ in met],
                "evidence": cells[1][:140],
            }
        )

    live = [r for r in records if r["triggers_met"]]
    by_perm: dict[str, int] = {}
    for r in records:
        by_perm[r["permanence"]] = by_perm.get(r["permanence"], 0) + 1

    print(f"=== NEGATIVE KNOWLEDGE LIBRARY -- {len(records)} structured failures ===")
    print("    (the graveyard is prose and cannot be queried -- this is the queryable form)\n")
    for k in ("PERMANENT", "NEAR-PERMANENT", "CONDITIONAL", "REVERSIBLE", "UNKNOWN"):
        if by_perm.get(k):
            print(f"  {k:<15} {by_perm[k]:>3}")
    print("\n  reversal triggers, current state:")
    for k, (ok, why) in sorted(trig.items()):
        print(f"    {'MET  ' if ok else 'unmet'} {k:<22} {why}")

    print(f"\n  *** {len(live)} dead ideas have a reversal trigger CURRENTLY MET ***")
    for r in live[:12]:
        print(f"    {r['what'][:58]:<58} [{','.join(r['triggers_met'])}]")
    if len(live) > 12:
        print(f"    ... +{len(live) - 12} more")
    print("\n  These are NOT auto-resurrected -- they become Stage-A candidates with a stated")
    print("  reason the original refutation may no longer hold. Zero promotion authority.")

    OUT.write_text(
        json.dumps(
            {
                "updated": datetime.now(tz=UTC).isoformat(),
                "n": len(records),
                "by_permanence": by_perm,
                "triggers": {k: {"met": v[0], "why": v[1]} for k, v in trig.items()},
                "revivable_now": len(live),
                "records": records,
            },
            indent=1,
        ),
        "utf-8",
    )
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()
