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
    classes = Counter(str(v.get("asset_class", "unknown"))
                      for v in registry.values() if isinstance(v, dict))
    facts["universe"] = {"symbols_with_bars": len(pq), "registry_rows": len(registry),
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

    # --- miners: rows, usable rate, and who is producing nothing usable -------------------------
    miners: dict[str, dict] = {}
    for base in (DESK / "data" / "intelligence", ROOT / "data" / "intelligence"):
        if not base.exists():
            continue
        for src in sorted(d for d in base.iterdir() if d.is_dir()):
            rows = errors = 0
            for f in src.glob("discoveries_*.json"):
                try:
                    if datetime.fromtimestamp(f.stat().st_mtime, tz=UTC) < cutoff:
                        continue
                except OSError:
                    continue
                data = _read(f)
                items = data if isinstance(data, list) else []
                for it in items:
                    if isinstance(it, dict):
                        rows += 1
                        if str(it.get("kind") or "").endswith("error"):
                            errors += 1
            if rows:
                miners[src.name] = {"rows_7d": rows, "fetch_errors": errors,
                                    "error_rate": round(errors / rows, 3)}
    facts["miners"] = {"count": len(miners), "detail": miners,
                       "all_errors": sorted(k for k, v in miners.items()
                                            if v["rows_7d"] >= 5
                                            and v["error_rate"] >= 0.99)}

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
