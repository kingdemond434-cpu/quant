"""SCREEN-DESIGN AUDITOR -- checks the TEST, not the code.

THE FAILURE THIS EXISTS FOR (3 occurrences on 2026-07-27, all caught by the principal or by luck):
  * structural_spreads.py  -- tested persistence/reversion/boundedness, OMITTED net-of-cost.
                              All 4 "candidates" die on fees. The code was correct; the TEST was
                              incomplete, so it produced confident false positives.
  * horizon_search.py      -- needed the ADJACENCY rail; the principal had to ask for it.
  * hl_longterm_skill.py   -- underpowered; the principal had to point out SE/min-detectable-effect.
A code auditor would have passed all three: the code did exactly what it said. The DESIGN was
missing a gate that, once applied, killed everything that passed. That is the most expensive
failure mode on a research desk.

RULE-BASED, NO LLM: each screen is checked for the presence of the rails the desk EARNED, by
scanning for their implementations. It cannot judge whether a rail is correctly applied -- only
whether it is ABSENT, which is the failure that actually occurred all three times.

Rails are declared per screen KIND, because a spread screen and a forecast screen need different
gates -- demanding all rails everywhere would just train people to ignore the auditor.
"""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
OUT = ROOT / "data/screen_audit.json"

# rail -> (regex evidence it is present, why it matters, which screen kinds require it)
RAILS = {
    "net_of_cost": (
        r"cost_model|round.?trip|bps|fee|slippage|net.of.cost",
        "a spread/edge smaller than transaction costs is not an edge -- USDC/USDT passed every "
        "structural test at 1.1bps against 4-10bps fees",
        {"spread", "forecast"}),
    "power_reporting": (
        r"min_detectable|minimum detectable|se\b|n_eff|powered|sqrt\(len|standard error",
        "a null without power is not a result -- the n=229 skill test could only detect rho>=0.13 "
        "and reported 'no persistence' anyway",
        {"forecast", "cross_sectional"}),
    "decontamination": (
        r"same_period|same-period|contam|residual_ic|orthogonalis",
        "a signal correlated with the CONCURRENT return is not leading it -- killed coinbase, "
        "turkey and elite order flow",
        {"forecast"}),
    "lookahead_rail": (
        r"SUSPECT-LOOKAHEAD|ic_ceiling|implausible_leak|shift|lookahead",
        "an implausibly strong daily IC means misalignment, not skill -- bithumb showed IC 0.72",
        {"forecast", "cross_sectional"}),
    "multiplicity": (
        r"bonferroni|holm|multiplicity|alpha\s*/\s*(len|n_)|/ *len\(HORIZONS\)",
        "k tests at alpha=0.05 manufacture k/20 false discoveries -- the horizon search ran 96",
        {"forecast", "cross_sectional", "spread"}),
    "stability_check": (
        r"perturb|stability|neighbour|adjacen|same-sign|resampl",
        "a result that flips under a small universe/parameter change is noise -- elite flow "
        "inverted when 60 traders were added",
        {"forecast", "cross_sectional"}),
    "gapped_windows": (
        r"gap|formation|holding|non-overlap",
        "adjacent formation/holding windows carry open positions across the boundary and "
        "manufacture persistence -- rho +0.12 became -0.06 with a 3-week gap",
        {"cross_sectional"}),
}

# screen kind by filename hint
KIND = {
    "structural_spreads.py": "spread",
    "horizon_search.py": "forecast",
    "batch_altdata.py": "forecast",
    "batch_onchain.py": "forecast",
    "batch_premium.py": "forecast",
    "fusion_engine.py": "forecast",
    "reflexivity_m5.py": "forecast",
    "hl_feature_factory.py": "forecast",
    "hl_skill_persistence.py": "cross_sectional",
    "hl_longterm_skill.py": "cross_sectional",
    "hl_highpower_skill.py": "cross_sectional",
    "build_dev_factor.py": "cross_sectional",
    "hl_gapped.py": "cross_sectional",
}


def main() -> None:
    print("=== SCREEN-DESIGN AUDITOR (audits the TEST, not the code) ===")
    print("    A code auditor passes an incomplete test. This asks: what gate is MISSING")
    print("    that would kill everything currently passing?\n")
    rows, total_missing = [], 0
    for fname, kind in sorted(KIND.items()):
        p = SCRIPTS / fname
        if not p.exists():
            continue
        src = p.read_text("utf-8", errors="ignore").lower()
        # A screen that calls stage_a_screen INHERITS its rails -- de-contamination, the
        # SUSPECT-LOOKAHEAD plausibility rail and power reporting are inside the harness. Not
        # crediting inheritance produced false "MISSING" on screens that are correctly gated,
        # and a noisy auditor is one nobody reads.
        inherits = bool(re.search(r"stage_a_screen", src, re.I))
        INHERITED = {"decontamination", "lookahead_rail", "power_reporting"} if inherits else set()
        required = [r for r, (_, _, kinds) in RAILS.items() if kind in kinds]
        missing = [r for r in required
                   if r not in INHERITED and not re.search(RAILS[r][0], src, re.I)]
        total_missing += len(missing)
        status = "OK" if not missing else ("INCOMPLETE" if len(missing) < 3 else "WEAK")
        print(f"  {fname:<28} [{kind:<15}] {status:<11} "
              f"{len(required)-len(missing)}/{len(required)} rails")
        for m in missing:
            print(f"      MISSING {m:<18} {RAILS[m][1][:88]}")
        rows.append({"screen": fname, "kind": kind, "required": required,
                     "inherited": sorted(INHERITED), "missing": missing, "status": status})

    print(f"\n  {total_missing} missing rails across {len(rows)} screens")
    print("  NOTE: this detects ABSENCE only. A present rail may still be wrongly applied --")
    print("  that needs the LLM code auditor (blocked on credits). Absence is what actually")
    print("  happened all three times today, so absence is the check worth having first.")
    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                               "total_missing": total_missing, "screens": rows}, indent=1),
                   "utf-8")
    print(f"\n  -> {OUT}")


if __name__ == "__main__":
    main()
