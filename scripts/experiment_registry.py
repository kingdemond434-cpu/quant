"""EXPERIMENT REGISTRY -- the write path, not another schema.

THE MEASURED FINDING THAT MOTIVATES THIS. The principal's review asks for an Experiment Registry,
Alpha Lineage, Reproducibility Layer, Research Memory and a Decision Log. This desk ALREADY HAS
those tables. I counted the rows:

    data/alpha_registry.sqlite   alpha_registry     0 rows
                                 trials_ledger      0 rows
                                 research_runs      0 rows
                                 snapshots          0 rows
    data/sor_research.sqlite     (same schema)      0 rows
    ... 8 sqlite files, every research table EMPTY
    data/panel_scorecard.json    13 providers, 0 scored, hit_rate null, stale since 2026-07-17

Meanwhile 43 commits landed on 2026-07-27 alone, each one an experiment, NONE of them recorded.

So the bottleneck is NOT missing architecture. It is that nothing WRITES. Adding the twenty-odd
new subsystems in the review as designed would produce twenty-odd more empty tables and one more
layer of things to maintain. The intervention with actual leverage is a harvester that turns the
evidence the desk already emits -- git history, artifacts on disk, the graveyard -- into permanent
experiment objects, automatically, with no discipline required from whoever runs the experiment.
Discipline-dependent logging is what produced the zeros.

WHAT AN EXPERIMENT OBJECT IS HERE (reproducibility is the point):
    id            stable, derived from commit sha -- survives rewrites of this file
    commit        the exact tree that produced the result. `git show <sha>` reproduces it.
    artifacts     which data/*.json it wrote, and whether that file STILL EXISTS
    decision      SURVIVED / REFUTED / INCONCLUSIVE / FIX / INFRA, parsed from the commit record
    mechanism     mapped through the mechanism_board taxonomy, so lineage is at mechanism level
    failure_mode  the autopsy taxonomy where a cause is stated

HONESTY RAIL: anything this cannot classify is reported as UNCLASSIFIED with a count, not guessed
into a bucket. A registry that silently invents decisions is worse than no registry, because the
scoreboard downstream would then allocate research capital against fiction.

Read-only w.r.t. the desk. No LLM, no keys. Run from repo root.
"""
from __future__ import annotations

import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/experiment_registry.jsonl"
SUMMARY = ROOT / "data/experiment_registry.json"

# decision parsing -- ordered, first match wins. Tokens taken from THIS desk's actual commit
# vocabulary (I read 43 real subjects), not from a generic list.
DECISION = [
    ("REFUTED", ("refuted", "coincident", "0/3 pass", "0/", "zero predictive", "fails", "failed",
                 "dead)", "-- dead", "exhausted", "no edge", "does not persist", "do not persist",
                 "premise fails", "closed", "kill", "artifact", "not leading")),
    ("SURVIVED", ("survives", "survived", "replicates out-of-sample", "confirmed", "ic +",
                  "holds out-of-sample", "adds value")),
    ("INCONCLUSIVE", ("inconclusive", "underpowered", "blocked", "402", "needs ", "unproven",
                      "likely a synchronisation artifact")),
    ("FIX", ("fix applied", "fixed", "root cause", "correction", "resolved", "restarted",
             "incident", "p0 ")),
]
INFRA_HINT = ("built", "wire", "doctrine", "engine", "scanner", "registry", "library", "digest",
              "snapshot", "monitor", "guard", "simulator", "author", "cli")

MECHANISMS = {
    "M_ATTENTION_DELAY": ("attention", "sentiment", "social", "wikipedia", "search", "narrative"),
    "M_FUNDAMENTAL_PROXY": ("developer", "github", "tvl", "onchain", "on-chain", "unlock"),
    "M_SKILL_PERSISTENCE": ("trader", "elite", "copytrad", "skill", "leaderboard", "whale"),
    "M_STRUCTURAL_BARRIER": ("kimchi", "premium", "structural spread", "cme", "venue", "basis",
                             "collateral", "cross-venue"),
    "M_FORCED_DELEVERAGE": ("funding", "open interest", "oi_", "carry", "liquidation", "leverage",
                            "positioning", "long short"),
    "M_LIQUIDITY_WITHDRAWAL": ("microstructure", "order book", "orderbook", "depth", "spread",
                               "moat", "liquidity", "cost model"),
    "M_FLOW_PRESSURE": ("stablecoin", "flow", "bridge", "reserve"),
    "M_PRICE_PATTERN": ("momentum", "reversal", "breakout", "trend", "horizon discovery",
                        "reflexivity"),
}
FAILURE_MODES = {
    "A_NO_MECHANISM": ("no mechanism", "no causal", "premise fails"),
    "B_WRONG_MEASUREMENT": ("unit error", "scope", "construction", "parser", "misalign"),
    "C_WRONG_TIMING": ("coincident", "horizon", "lead", "same-period", "contemporaneous",
                       "not leading", "half-life"),
    "D_ALREADY_ARBITRAGED": ("arbitraged", "crowded", "competed"),
    "E_DATA_QUALITY": ("artifact", "synchronisation", "lookahead", "stale", "implausible"),
    "F_REGIME_DEPENDENT": ("regime",),
    "G_TOO_EXPENSIVE": ("costs", "cost model", "round-trip", "bps", "survive costs", "slippage"),
    "H_OVERFIT": ("overfit", "underpowered", "n=", "power", "dsr"),
}


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True, text=True,
                              check=False, timeout=90).stdout
    except Exception:  # noqa: BLE001
        return ""


def _tag(text: str, table: dict) -> list[str]:
    t = text.lower()
    return [k for k, kws in table.items() if any(w in t for w in kws)]


def _decide(text: str) -> str:
    t = text.lower()
    for label, kws in DECISION:
        if any(k in t for k in kws):
            return label
    if any(k in t for k in INFRA_HINT):
        return "INFRA"
    return "UNCLASSIFIED"


def harvest(days: int = 45) -> list[dict]:
    """One record per commit. The commit IS the reproducible unit -- it pins code + params."""
    raw = _git("log", f"--since={days} days ago", "--name-only",
               "--pretty=format:%x00%H%x1f%an%x1f%aI%x1f%s%x1f%b%x02")
    rows = []
    for chunk in raw.split("\x00"):
        if "\x02" not in chunk:
            continue
        head, files_blob = chunk.split("\x02", 1)
        parts = head.split("\x1f")
        if len(parts) < 4:
            continue
        sha, author, iso, subject = parts[0], parts[1], parts[2], parts[3]
        body = parts[4] if len(parts) > 4 else ""
        files = [f.strip() for f in files_blob.splitlines() if f.strip()]
        blob = f"{subject}\n{body}"
        arts = sorted({f for f in files if f.startswith(("data/", "docs/"))})
        code = sorted({f for f in files if f.startswith("scripts/") or f.startswith("libs/")})
        rows.append({
            "id": f"E-{sha[:10]}",
            "commit": sha,
            "date": iso[:10],
            "author": author,
            "title": subject[:180],
            "decision": _decide(blob),
            # SUBJECT ONLY. First pass tagged subject+body+code-paths and produced 2.4 mechanisms
            # per experiment with survival flat at 6-11% across all nine -- the signature of
            # keyword BLEED, not of nine equally productive mechanisms. A file named
            # scripts/run_cost_model.py dragged "cost model" into M_LIQUIDITY_WITHDRAWAL on every
            # commit that touched it. Flat rates across every category mean the tagger is not
            # discriminating, and the allocator downstream would have spent research capital on
            # that noise. The subject line is the one field that states what was actually tested.
            "mechanisms": _tag(subject, MECHANISMS) or ["M_UNMAPPED"],
            "failure_modes": _tag(blob, FAILURE_MODES) if _decide(blob) == "REFUTED" else [],
            "code": code[:8],
            "artifacts": arts[:8],
            # reproducibility: does the thing it wrote still exist in the working tree?
            "artifacts_present": sum(1 for a in arts if (ROOT / a).exists()),
            "artifacts_declared": len(arts),
        })
    return rows


def main() -> None:
    print("=== EXPERIMENT REGISTRY -- harvested, not hand-logged ===")
    print("    the registries this desk already owns hold 0 rows; discipline-based logging")
    print("    is what produced the zeros, so this reads evidence the desk emits anyway\n")
    rows = harvest()
    if not rows:
        raise SystemExit("no git history harvested -- refusing to write an empty registry")

    with OUT.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")

    dec: dict[str, int] = {}
    for r in rows:
        dec[r["decision"]] = dec.get(r["decision"], 0) + 1
    print(f"  {len(rows)} experiments registered over 45 days\n")
    print(f"  {'decision':<16}{'n':>5}   share")
    for k, v in sorted(dec.items(), key=lambda kv: -kv[1]):
        print(f"  {k:<16}{v:>5}   {v/len(rows)*100:4.0f}%")

    tested = [r for r in rows if r["decision"] in ("REFUTED", "SURVIVED", "INCONCLUSIVE")]
    surv = [r for r in rows if r["decision"] == "SURVIVED"]
    if tested:
        print(f"\n  SURVIVAL RATE  {len(surv)}/{len(tested)} = {len(surv)/len(tested)*100:.1f}% "
              f"of decided experiments")

    mech: dict[str, dict[str, int]] = {}
    for r in tested:
        for m in r["mechanisms"]:
            d = mech.setdefault(m, {"tested": 0, "survived": 0})
            d["tested"] += 1
            d["survived"] += r["decision"] == "SURVIVED"
    tags_per = sum(len(r["mechanisms"]) for r in tested) / max(len(tested), 1)
    print("\n  MECHANISM SURVIVAL (this is the input research allocation should use):")
    print(f"  {'mechanism':<26}{'tested':>7}{'survived':>10}{'rate':>8}")
    for m, d in sorted(mech.items(), key=lambda kv: -kv[1]["tested"]):
        rate = d["survived"] / d["tested"] * 100 if d["tested"] else 0.0
        flag = "  <-- n too small to rank" if d["tested"] < 8 else ""
        print(f"  {m:<26}{d['tested']:>7}{d['survived']:>10}{rate:>7.0f}%{flag}")
    print(f"\n  tag density {tags_per:.2f} mechanisms/experiment "
          f"({'OK -- tags discriminate' if tags_per < 1.4 else 'HIGH -- suspect keyword bleed'})")

    fm: dict[str, int] = {}
    for r in rows:
        for f in r["failure_modes"]:
            fm[f] = fm.get(f, 0) + 1
    if fm:
        print("\n  FAILURE MODES on refuted experiments:")
        for k, v in sorted(fm.items(), key=lambda kv: -kv[1]):
            print(f"    {k:<24}{v:>4}")

    declared = sum(r["artifacts_declared"] for r in rows)
    present = sum(r["artifacts_present"] for r in rows)
    unc = dec.get("UNCLASSIFIED", 0)
    print(f"\n  REPRODUCIBILITY: {present}/{declared} declared artifacts still present "
          f"({present/max(declared,1)*100:.0f}%); every row pins a commit sha, so "
          f"`git show <sha>` reproduces the code that produced it.")
    print(f"  UNCLASSIFIED: {unc} commits ({unc/len(rows)*100:.0f}%) state no decision this can")
    print("  parse. That is a real defect in commit discipline, reported rather than guessed --")
    print("  a registry that invents decisions would corrupt every allocation downstream.")

    SUMMARY.write_text(json.dumps({
        "updated": datetime.now(tz=UTC).isoformat(), "n": len(rows), "decisions": dec,
        "survival_rate": round(len(surv) / len(tested), 4) if tested else None,
        "mechanism_survival": mech, "failure_modes": fm,
        "artifacts_present": present, "artifacts_declared": declared,
        "unclassified": unc}, indent=1), "utf-8")
    print(f"\n  -> {OUT}\n  -> {SUMMARY}")


if __name__ == "__main__":
    main()
