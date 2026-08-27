#!/usr/bin/env python3
"""RESEARCH FACTS PACK -- precompute everything an LLM organ would otherwise count for itself.

WHY THIS SAVES REAL TOKENS WITHOUT COSTING ROI (principal 2026-08-26: "what else can we migrate
to python to save massive token limits"). The desk's LLM organs are told, in their own prompts,
to do arithmetic: `ops/frontier_en_prompt.txt` contains SEVEN "count" instructions and two
"measure"; `ops/gap_wirer_prompt.txt` contains four "audit" and a "compute". Every one of those
makes a model read files and tally rows -- the most expensive possible way to do subtraction, and
the least reliable: a model that miscounts produces a confident wrong number, while Python either
produces the right one or raises.

THE SPLIT THIS ENFORCES:

    PYTHON  counting, tallying, diffing, freshness, coverage, ratios, staleness, "is X wired",
            "how many of Y", "what changed since Z"      -- deterministic, verifiable, free
    LLM     reading a Russian forum post and naming the mechanism; judging whether a mechanism
            is economically plausible; deciding which of six gaps is worth the next hour;
            translating a claim into a testable hypothesis   -- irreducible judgment

An organ reads this file at cycle start and spends its whole budget on the second column. That is
strictly more research per token, not less: nothing in the first column was ever a judgment call.

WHAT IT DELIBERATELY DOES NOT DO. It computes no verdicts and no rankings that imply a decision.
A facts pack that started saying "you should work on X" would be making the judgment it exists to
free up, and would be doing it with less context than the organ has.
"""
from __future__ import annotations

import json
import subprocess
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

# ONE definition of a usable miner row, shared with the fence that acts on it. Restating the
# rule here instead of importing it is how the pack and the fence would come to disagree.
from check_miner_health import classify_row

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
OUT = ROOT / "data" / "research_facts.json"


def _read(p: Path):
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _age_h(p: Path) -> float | None:
    try:
        return (datetime.now(tz=UTC)
                - datetime.fromtimestamp(p.stat().st_mtime, tz=UTC)).total_seconds() / 3600
    except OSError:
        return None


def main() -> int:
    now = datetime.now(tz=UTC)
    cutoff = now - timedelta(days=7)
    facts: dict = {"built_at": now.isoformat(timespec="seconds")}

    # --- universe: how much ground exists and how much is covered ------------------------------
    pq = list((DESK / "data" / "universe").glob("*_H1.parquet"))
    registry = _read(DESK / "data" / "universe" / "universe.json") or {}
    # THE REGISTRY CALLS IT `category`. This read `asset_class`, which no row has ever carried,
    # so the pack reported `{"unknown": 197}` -- a reader on the wrong key does not crash, it
    # takes the empty branch and publishes a plausible zero, and every organ downstream read
    # "this desk has no asset-class structure" when the structure was sitting in the file.
    # `asset_class` is kept as a fallback so a future producer using that name still lands.
    classes = Counter(str(v.get("category") or v.get("asset_class") or "unknown")
                      for v in registry.values() if isinstance(v, dict))
    # COSTABLE = has a `tick_value`. Without it a candidate cannot be priced, so it cannot clear
    # gate 8 (stress_costs) and is not really in the tradable universe however many bars it has.
    # Counted here because the pack is where the desk goes for universe size, and a size that
    # ignores costability overstates the ground the gauntlet can actually judge.
    costable = sum(1 for v in registry.values()
                   if isinstance(v, dict) and v.get("tick_value") is not None)
    facts["universe"] = {"symbols_with_bars": len(pq), "registry_rows": len(registry),
                         "costable_rows": costable,
                         "uncostable_rows": len(registry) - costable,
                         "by_asset_class": dict(classes)}

    # --- certificates: the only count that matters for promotion -------------------------------
    certs = (_read(DESK / "reports" / "UNIVERSAL_SURVIVORS.json") or {}).get("survivors") or {}
    fam = Counter(str((c.get("shadow_spec") or {}).get("family") or "unknown")
                  for c in certs.values())
    runnable = sum(1 for c in certs.values() if (c.get("shadow_spec") or {}).get("params"))
    facts["certificates"] = {"total": len(certs), "runnable": runnable,
                             "unrunnable_no_params": len(certs) - runnable,
                             "by_family": dict(fam),
                             "largest_family_share": (round(max(fam.values()) / len(certs), 3)
                                                      if certs else None)}

    # --- forward clocks: where evidence actually stands ----------------------------------------
    live, fwd_obs, hist_obs = 0, 0, 0
    terminal = {"KILL", "KILLED", "PROMOTED", "DEAD", "REJECTED", "RETIRED", "QUARANTINED"}
    for name in ("shadow_state.json", "qquant_shadow_state.json", "scalp_shadow_state.json"):
        doc = _read(DESK / "reports" / "shadow" / name) or {}
        rows = list(doc.values()) + list((doc.get("sleeves") or {}).values())
        for row in rows:
            if not isinstance(row, dict) or "status" not in row:
                continue
            if str(row.get("status") or "").upper().split("_")[0] in terminal:
                continue
            live += 1
            fwd_obs += int(row.get("n") or 0)
            hist_obs += int(row.get("n_historical") or 0)
    facts["forward"] = {"live_clocks": live, "forward_observations": fwd_obs,
                        "historical_observations_excluded": hist_obs}

    # --- miners: REAL rows, not rows ------------------------------------------------------------
    # A miner's health is the information it produced, and an error row is still a row. The
    # previous version of this block measured `error_rate = fetch_errors / rows` and reported
    # 35 of 41 sources healthy while 30 of them had produced ZERO usable rows for 18 consecutive
    # hourly sweeps (measured 2026-08-26). It had three structural blind spots, each of which
    # failed toward a CLEAN verdict -- the one direction nothing downstream catches (WS-005):
    #
    #   1. `if rows:` dropped any source with zero rows from the pack ENTIRELY, so the most
    #      completely broken miners were the most invisible ones. 13 sources were missing.
    #   2. A selector-drift stub (`raw_capture` + needs_selector_work) is not an "error", so a
    #      miner emitting nothing but "page shape drifted" scored error_rate 0.0 -- perfect
    #      health -- while carrying no information at all. fbs_tape: 21 rows, 21 stubs, 0.0.
    #   3. The `all_errors` list required rows_7d >= 5, hiding every 100%-error miner that
    #      produces one error row per sweep on a slow cadence (followme_cn, hfm_pamm, minfx_jp,
    #      readitrades_africa, share4you -- all at error_rate 1.0, none reported).
    #
    # Organs are under standing orders to trust this file and not recompute it, so a number that
    # is wrong here is wrong everywhere, silently. `real_rows_7d` is therefore the headline and
    # `dead` is derived from it. Fence: scripts/check_miner_health.py (same definition of real).
    miners: dict[str, dict] = {}
    for base in (DESK / "data" / "intelligence", ROOT / "data" / "intelligence"):
        if not base.exists():
            continue
        for src in sorted(d for d in base.iterdir() if d.is_dir()):
            rows = errors = stubs = real = walled = sweeps = 0
            for f in src.glob("discoveries_*.json"):
                try:
                    if datetime.fromtimestamp(f.stat().st_mtime, tz=UTC) < cutoff:
                        continue
                except OSError:
                    continue
                sweeps += 1
                data = _read(f)
                items = data if isinstance(data, list) else []
                for it in items:
                    if not isinstance(it, dict):
                        continue
                    rows += 1
                    bucket = classify_row(it)
                    errors += bucket == "error"
                    walled += bucket == "walled"
                    stubs += bucket == "stub"
                    real += bucket == "real"
            if not sweeps:
                continue
            miners[src.name] = {
                "sweeps_7d": sweeps, "rows_7d": rows, "real_rows_7d": real,
                "fetch_errors": errors, "selector_stubs": stubs, "walled_rows": walled,
                "error_rate": round(errors / rows, 3) if rows else 0.0,
                "usable_rate": round(real / rows, 3) if rows else 0.0,
            }
    dead = sorted(k for k, v in miners.items()
                  if v["real_rows_7d"] == 0 and not v["walled_rows"])
    facts["miners"] = {
        "count": len(miners), "detail": miners,
        "dead_no_usable_output": dead,
        "walled": sorted(k for k, v in miners.items() if v["walled_rows"]),
        "all_errors": sorted(k for k, v in miners.items() if v["error_rate"] >= 0.99),
        "note": "HEALTH IS real_rows_7d, NEVER rows_7d -- an error row and a selector stub are "
                "both rows and neither is information. `dead_no_usable_output` produced nothing "
                "usable in the window and is a repair queue, not a statistic.",
    }

    # --- artifact freshness: "is X wired and alive" as a number, not an impression --------------
    fresh = {}
    for rel in ("desks/mt5/reports/UNIVERSAL_SURVIVORS.json",
                "desks/mt5/reports/shadow/shadow_state.json",
                "desks/mt5/reports/execution_quality.json",
                "desks/mt5/reports/portfolio_evidence.json",
                "desks/mt5/data/sleeve_registry.json",
                "data/gauntlet_survivors.json", "data/miner_conversion.json",
                "data/live_readiness.json", "web/desk_state.json"):
        age = _age_h(ROOT / rel)
        fresh[rel] = None if age is None else round(age, 2)
    facts["artifact_age_hours"] = fresh

    # --- readiness + portfolio: already computed, carried so nobody recomputes ------------------
    rd = _read(ROOT / "data" / "live_readiness.json") or {}
    facts["readiness"] = {"rung": rd.get("rung"), "status": rd.get("status"),
                          "blocking": rd.get("blocking", [])}
    pf = _read(DESK / "reports" / "portfolio_evidence.json") or {}
    facts["portfolio"] = pf.get("effective_bets", {})

    # --- what changed in the repo lately -------------------------------------------------------
    try:
        r = subprocess.run(["git", "log", "--since=24 hours ago", "--oneline"],
                           cwd=ROOT, capture_output=True, text=True, timeout=30, check=False)
        facts["commits_24h"] = len([x for x in r.stdout.splitlines() if x.strip()])
    except (OSError, subprocess.SubprocessError):
        facts["commits_24h"] = None

    facts["contract"] = ("Python counts; the model judges. Every number here is deterministic and "
                         "was previously derived by an LLM reading files. Organs must NOT "
                         "recompute these -- spend the budget on mechanism extraction, economic "
                         "plausibility and prioritisation, which are the parts Python cannot do.")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(facts, indent=1, default=str), "utf-8")
    print(f"research facts: {facts['universe']['symbols_with_bars']} symbols, "
          f"{facts['certificates']['total']} certificates "
          f"({facts['certificates']['runnable']} runnable), "
          f"{facts['forward']['live_clocks']} clocks, {facts['miners']['count']} miners")
    print(f"  -> {OUT.relative_to(ROOT)}  (organs read this instead of counting)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
