"""RESEARCH AUTOPSY -- every failure must produce a LESSON, not just a tombstone.

THE GAP: the graveyard records WHAT died and a cause tag. It does not record the FAILURE MODE, so
the desk cannot learn sentences like "crypto attention features fail because they are COINCIDENT,
not delayed" -- which is the kind of statement that prevents a whole future family of experiments.
negative_knowledge.py classifies PERMANENCE (can this revive?). This classifies AETIOLOGY (why did
it die?) and then AGGREGATES across families to extract institutional lessons.

EIGHT FAILURE MODES (the principal's taxonomy, mapped onto this desk's measured history):
  A NO_MECHANISM        no causal story that survives "why has nobody arbitraged this?"
  B WRONG_MEASUREMENT   the construction measured something other than the intended quantity
  C WRONG_TIMING        real relationship, wrong horizon or lead/lag
  D ALREADY_ARBITRAGED  the edge exists but is competed to below cost
  E DATA_QUALITY        the finding was an artifact of the pipeline, not the market
  F REGIME_DEPENDENT    worked in one environment, not generally
  G TOO_EXPENSIVE       real edge, smaller than its own transaction cost
  H OVERFIT             fit the sample, not the process

WHY THIS MATTERS MORE THAN IT LOOKS: the desk killed ~28 hypotheses today. If each is stored as
"rejected", that is 28 tombstones. If each is stored with its MODE, patterns emerge that are worth
more than any single experiment -- e.g. if most public-data failures are mode D or G, the lesson is
not "try different public data", it is "public data cannot clear costs here", which retires an
entire search direction.

Read-only. No LLM, no keys. Run from repo root.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
GRAVE = ROOT / "docs/graveyard.md"
OUT = ROOT / "data/research_autopsy.json"

MODES = {
    "A_NO_MECHANISM": ("no_economics", "no mechanism", "no causal", "no named mechanism",
                       "base rate", "no strong pre-registered"),
    "B_WRONG_MEASUREMENT": ("construction", "scope", "unit error", "misalign", "mismatch",
                            "parser", "fragment", "measured the wrong"),
    "C_WRONG_TIMING": ("horizon", "daily", "no_edge_daily", "timing", "lead", "coincid",
                       "same-period", "contemporaneous", "half-life"),
    "D_ALREADY_ARBITRAGED": ("crowded", "arbitraged", "tightly arbitraged", "competed",
                             "pre-arbitraged", "everyone"),
    "E_DATA_QUALITY": ("artifact", "lookahead", "degenerate", "non-synchronous", "timezone",
                       "stale", "silent-zero", "implausible", "data-blocked"),
    "F_REGIME_DEPENDENT": ("regime", "only-recent-era", "bull", "inverts", "regime_artifact"),
    "G_TOO_EXPENSIVE": ("cost", "fee", "bps", "round-trip", "costs_killed", "slippage",
                        "unprofitable", "too tight"),
    "H_OVERFIT": ("overfit", "dsr", "p-hack", "specification search", "unstable", "n=",
                  "underpowered", "insignificant", "fat sharpe"),
}

FAMILY = {
    "attention/social": ("attention", "wikipedia", "sentiment", "social", "narrative", "search"),
    "developer": ("developer", "github", "commit", "contributor", "dev "),
    "trader/behavioural": ("trader", "elite", "copytrad", "leaderboard", "skill", "whale"),
    "regional premium": ("premium", "kimchi", "bithumb", "coinone", "turk", "cny", "peg", "lsd",
                         "staking"),
    "funding/positioning": ("funding", "oi_", "open interest", "ls_contrarian", "basis", "carry"),
    "on-chain/flow": ("onchain", "on-chain", "stablecoin", "throughput", "flow", "bridge", "dex"),
    "price-only/TA": ("momentum", "reversal", "breakout", "kama", "squeeze", "lowvol", "trend",
                      "illiquidity", "indicator"),
}


def classify(text: str, table: dict[str, Any]) -> list[str]:
    t = text.lower()
    return [k for k, kws in table.items() if any(w in t for w in kws)]


def main() -> None:
    if not GRAVE.exists():
        raise SystemExit("no graveyard")
    rows = []
    for ln in GRAVE.read_text("utf-8").splitlines():
        if not ln.startswith("|") or set(ln) <= set("|- "):
            continue
        cells = [c.strip() for c in ln.strip("|").split("|")]
        if len(cells) < 3 or cells[0].lower() in ("name", "signal", "strategy"):
            continue
        blob = " ".join(cells)
        modes = classify(blob, MODES) or ["UNCLASSIFIED"]
        fams = classify(blob, FAMILY) or ["other"]
        rows.append({"name": cells[0][:80], "modes": modes, "families": fams,
                     "evidence": cells[1][:110]})

    print(f"=== RESEARCH AUTOPSY -- {len(rows)} failures, cause of death classified ===")
    print("    a tombstone says WHAT died; an autopsy says WHY, and why is what transfers\n")

    mc: dict[str, int] = {}
    for r in rows:
        for m in r["modes"]:
            mc[m] = mc.get(m, 0) + 1
    print("  FAILURE MODES across the graveyard:")
    for m, c in sorted(mc.items(), key=lambda kv: -kv[1]):
        print(f"    {m:<24} {c:>3}  ({c/len(rows)*100:.0f}%)")

    print("\n  FAMILY x DOMINANT MODE -- this is where the transferable lesson lives:")
    fam_modes: dict[str, dict[str, int]] = {}
    for r in rows:
        for f in r["families"]:
            d = fam_modes.setdefault(f, {})
            for m in r["modes"]:
                d[m] = d.get(m, 0) + 1
    lessons = []
    for f, d in sorted(fam_modes.items(), key=lambda kv: -sum(kv[1].values())):
        top = sorted(d.items(), key=lambda kv: -kv[1])[:2]
        n = sum(d.values())
        print(f"    {f:<22} n={n:<3} -> {', '.join(f'{k}({v})' for k, v in top)}")
        if top and top[0][1] >= 2:
            lessons.append({"family": f, "dominant_mode": top[0][0], "count": top[0][1],
                            "n": n})

    print("\n  INSTITUTIONAL LESSONS (family + dominant failure mode, n>=2):")
    TEXT = {
        "C_WRONG_TIMING": "the relationship may be real but is COINCIDENT or on the wrong horizon "
                          "-- do not retry at the same frequency",
        "G_TOO_EXPENSIVE": "the edge is smaller than its own transaction cost -- only revisit if "
                           "costs fall structurally, not if the signal looks better",
        "H_OVERFIT": "died to sample/power, not to the world -- a properly powered re-test is "
                     "legitimate, a re-fit is not",
        "E_DATA_QUALITY": "the finding was a PIPELINE artifact -- fix measurement before "
                          "concluding anything about the market",
        "A_NO_MECHANISM": "no causal story survived scrutiny -- needs a NEW named mechanism, not "
                          "new data",
        "D_ALREADY_ARBITRAGED": "competed away -- only revisit with evidence the crowd left",
        "F_REGIME_DEPENDENT": "environment-specific -- test conditional on regime or not at all",
        "B_WRONG_MEASUREMENT": "measured something other than intended -- rebuild the construction",
    }
    for L in lessons:
        print(f"    {L['family']:<22} {TEXT.get(L['dominant_mode'], L['dominant_mode'])}")

    unc = sum(1 for r in rows if r["modes"] == ["UNCLASSIFIED"])
    print(f"\n  {unc} entries UNCLASSIFIED -- each is a graveyard row whose cause was never")
    print("  written precisely enough to learn from. That is itself a defect worth fixing.")
    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(), "n": len(rows),
                               "mode_counts": mc, "family_modes": fam_modes,
                               "lessons": lessons, "unclassified": unc,
                               "autopsies": rows}, indent=1), "utf-8")
    print(f"  -> {OUT}")


if __name__ == "__main__":
    main()
