"""AUDIT SHARDING -- give the 13-seat panel 100% code coverage instead of 0.42%.

THE DEFECT, measured. docs/EXTERNAL_PANEL_DOSSIER.md is 13,185 chars of state summaries against a
3,139,420-char codebase: **0.42% code coverage**. The panel has never read the code. It has been
reviewing this desk's own account of itself, which is the one input guaranteed to share the desk's
blind spots. max_audit's docstring already recorded "audits seeing 1% of the code" as a historical
defect; it was never actually closed.

WHY ONE PAYLOAD CANNOT FIX IT. The merit subset (everything except the 90 INERT modules) is
1,434,589 chars, and libs/ adds 1,232,485 -- 2,667,074 total against a PROVEN per-seat capacity of
750,805 chars. A single dossier is 191% over before libs/ is even counted.

THE ANSWER IS AGGREGATE CAPACITY. 13 seats x 750,805 = 9.75M chars. Sharding turns a capacity
problem into an assignment problem.

  TIER 1 -- MONEY PATH, sent to EVERY seat. The executor, execution libs, risk rails, gates.
            Reviewed 13 times over, because a defect here costs money and a defect in a research
            script costs a wasted afternoon. This desk has already lost a hedge to an unreviewed
            order path.
  TIER 2 -- everything else with merit, SHARDED disjointly across seats. Each file lands with
            exactly one seat, so union coverage is 100% with zero duplicated spend.
  EXCLUDED -- the 90 INERT modules, LISTED BY NAME in every shard. The panel is told what was
            withheld and invited to challenge the exclusion. Silent omission is how a blind spot
            survives an audit; a named omission is a question.

Coverage is PRINTED per seat and in aggregate, so "the panel reviewed the code" becomes a number
rather than a claim.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JUST = ROOT / "data/module_justification.json"
KEYS = ROOT / "data/secrets/llm_panel.json"
OUTDIR = ROOT / "docs/audit_shards"
SUMMARY = ROOT / "data/audit_shards.json"

PER_SEAT_BUDGET = 700_000        # under the 750,805 proven payload, leaving room for the charter

# Money path: anything that can move funds or gate a trade. Reviewed by EVERY seat.
TIER1_PATTERNS = ("run_cashcarry_executor", "binance_testnet", "binance_live", "binance_spot",
                  "run_deadman_switch", "hedge_integrity", "measurement_gate", "flatten_",
                  "run_alerts", "risk", "carry_viability", "execution_bottleneck")


def _files() -> list[Path]:
    return sorted(list((ROOT / "scripts").glob("*.py")) + list((ROOT / "libs").rglob("*.py")))


def main() -> None:
    verdicts = {}
    if JUST.exists():
        verdicts = {m["module"]: m["verdict"] for m in
                    json.loads(JUST.read_text("utf-8"))["modules"]}
    seats = []
    if KEYS.exists():
        seats = [p["model"] for p in json.loads(KEYS.read_text("utf-8")).get("providers", [])
                 if isinstance(p, dict) and p.get("model")]
    n_seats = max(len(seats), 1)

    tier1, tier2, inert = [], [], []
    for f in _files():
        rel = str(f.relative_to(ROOT))
        size = f.stat().st_size
        if any(pat in rel for pat in TIER1_PATTERNS):
            tier1.append((rel, size))
        elif verdicts.get(f.stem) == "INERT":
            inert.append(rel)
        else:
            tier2.append((rel, size))

    t1_bytes = sum(s for _, s in tier1)
    t2_bytes = sum(s for _, s in tier2)
    total_code = t1_bytes + t2_bytes + sum((ROOT / i).stat().st_size for i in inert)

    print("=== AUDIT SHARDING -- 100% coverage via aggregate seat capacity ===")
    print(f"    current dossier coverage: 0.42% (state summaries, no source)\n")
    print(f"  seats                {n_seats}")
    print(f"  TIER 1 (money path)  {len(tier1):>4} files  {t1_bytes:>10,} chars -> EVERY seat")
    print(f"  TIER 2 (merit)       {len(tier2):>4} files  {t2_bytes:>10,} chars -> sharded")
    print(f"  EXCLUDED (INERT)     {len(inert):>4} files  -> named in every shard, not sent\n")

    if t1_bytes > PER_SEAT_BUDGET:
        print(f"  WARNING: tier-1 alone ({t1_bytes:,}) exceeds the per-seat budget "
              f"({PER_SEAT_BUDGET:,}).")
        print("  Money-path review would be truncated, which is the one thing this must not do.")
        print("  Reporting rather than silently trimming.")

    # greedy disjoint sharding of tier 2, largest-first for even fill
    room = max(PER_SEAT_BUDGET - t1_bytes, 1)
    shards: list[list[tuple[str, int]]] = [[] for _ in range(n_seats)]
    loads = [0] * n_seats
    overflow = []
    for rel, size in sorted(tier2, key=lambda x: -x[1]):
        i = loads.index(min(loads))
        if loads[i] + size > room:
            overflow.append(rel)
            continue
        shards[i].append((rel, size))
        loads[i] += size

    OUTDIR.mkdir(parents=True, exist_ok=True)
    for old in OUTDIR.glob("shard_*.md"):
        old.unlink()

    covered = set(r for r, _ in tier1)
    rows = []
    for i in range(n_seats):
        seat = seats[i] if i < len(seats) else f"seat{i}"
        parts = [f"# AUDIT SHARD {i+1}/{n_seats} -- seat {seat}",
                 "",
                 "You are reviewing SOURCE CODE, not a summary. Previous panels received a "
                 "13,185-char self-description and never saw the code; that is why this exists.",
                 "",
                 f"- TIER 1 (money path) is included IN FULL and is sent to every seat: "
                 f"{len(tier1)} files. A defect here costs money.",
                 f"- TIER 2 is YOUR SHARD ALONE: {len(shards[i])} files. No other seat sees these, "
                 f"so anything you miss here is missed entirely.",
                 f"- WITHHELD: {len(inert)} modules classified INERT (nothing reads them; deleting "
                 f"breaks nothing). They are named below. **If you believe an exclusion is wrong, "
                 f"say so** -- a silent omission is how a blind spot survives an audit.",
                 "",
                 "## Withheld (INERT) -- challenge these if the classification looks wrong", ""]
        parts.append(", ".join(sorted(Path(i2).stem for i2 in inert)))
        parts += ["", "## TIER 1 -- money path (every seat reviews this)", ""]
        for rel, _ in sorted(tier1):
            parts += [f"### {rel}", "```python",
                      (ROOT / rel).read_text("utf-8", errors="ignore"), "```", ""]
        parts += ["## TIER 2 -- your shard", ""]
        for rel, _ in sorted(shards[i]):
            covered.add(rel)
            parts += [f"### {rel}", "```python",
                      (ROOT / rel).read_text("utf-8", errors="ignore"), "```", ""]
        doc = "\n".join(parts)
        (OUTDIR / f"shard_{i+1:02d}.md").write_text(doc, "utf-8")
        rows.append({"seat": seat, "shard": i + 1, "tier2_files": len(shards[i]),
                     "chars": len(doc)})
        print(f"  shard {i+1:>2} {seat[:26]:<28} {len(shards[i]):>3} tier-2 files  "
              f"{len(doc):>9,} chars")

    reviewable = t1_bytes + t2_bytes
    cov = sum((ROOT / c).stat().st_size for c in covered) / max(reviewable, 1) * 100
    print(f"\n  UNION COVERAGE OF MERIT CODE: {cov:.1f}%  ({len(covered)}/"
          f"{len(tier1)+len(tier2)} files)")
    print(f"  coverage of ENTIRE codebase incl INERT: "
          f"{sum((ROOT/c).stat().st_size for c in covered)/max(total_code,1)*100:.1f}%")
    if overflow:
        print(f"\n  OVERFLOW -- {len(overflow)} files did not fit any shard:")
        for o in overflow[:8]:
            print(f"    {o}")
        print("  These are UNREVIEWED. Raise PER_SEAT_BUDGET or add seats; do not pretend "
              "coverage is complete while this list is non-empty.")
    else:
        print("  No overflow: every merit file is assigned to exactly one seat.")

    SUMMARY.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                                   "seats": n_seats, "tier1_files": len(tier1),
                                   "tier2_files": len(tier2), "inert_withheld": len(inert),
                                   "union_coverage_pct": round(cov, 2),
                                   "overflow": overflow, "shards": rows}, indent=1), "utf-8")
    print(f"\n  -> {OUTDIR}/  ({n_seats} shards)\n  -> {SUMMARY}")


if __name__ == "__main__":
    main()
