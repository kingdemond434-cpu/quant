"""RESEARCH ALPHA OPTIMIZER (Level-5 meta-learning) -- "which ways of finding alpha actually work?"

Not alpha. ALPHA FOR FINDING ALPHA. Learns from the desk's own experiment history which RESEARCH
METHODS (not which signals) convert effort into knowledge, and feeds that back into the allocator.

THE ACTIVATION RULE (the reason this is safe to build now): a meta-learner fitted to zero
survivors produces confident allocations from pure noise -- worse than having none. So this runs
in two modes and says which one it is in:
    INSTRUMENTING -- records method-level outcomes every cycle, drives NOTHING (default today)
    ACTIVE        -- once >=MIN_SURVIVORS confirmed edges exist, its weights may inform allocation
Building the recorder now is correct because method-outcome history cannot be reconstructed
retroactively; fitting the model now would be malpractice.

METHOD TAXONOMY -- how a hypothesis was PRODUCED, which is the thing being learned about:
    new_data_axis      onboarding a genuinely new external dataset
    horizon_variation  same signal, different measurement horizon
    fusion             combining existing signals
    cross_sectional    ranking across a universe rather than timing one asset
    reconstruction     rebuilding a paid/vendor metric from free primitives
    literature_import  a mechanism taken from papers/other fields
    parameter_search   re-fitting an existing construction (the lowest-prior method)

Read-only. Run from repo root.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from libs.research.search_strategy import evolve_search_strategies

LEDGER = Path("data/decision_ledger.json")
OUT = Path("data/research_alpha_optimizer.json")
HIST = Path("data/method_outcomes.jsonl")
MIN_SURVIVORS = 3  # activation threshold -- below this the model informs nothing

METHODS = {
    "new_data_axis": (
        "new axis",
        "onboard",
        "collector",
        "orthogonal data",
        "new source",
        "free-data",
        "data axis",
    ),
    "horizon_variation": ("horizon", "timeframe", "daily", "weekly", "monthly"),
    "fusion": ("fusion", "composite", "combined filter", "combination", "multi-factor"),
    "cross_sectional": (
        "cross-sectional",
        "cross sectional",
        "universe",
        "rank",
        "decile",
        "quartile",
        "cohort",
    ),
    "reconstruction": ("reconstruct", "backfill", "held-out", "vendor", "free alternative"),
    "literature_import": (
        "literature",
        "paper",
        "arxiv",
        "academic",
        "cross-domain",
        "epidemiolog",
        "insurance",
    ),
    "parameter_search": ("parameter", "re-fit", "refit", "tuning", "threshold", "optimis"),
}

OUTCOMES = {
    "survivor": ("forward clock", "screen-interesting", "wired", "replicat"),
    "refutation": (
        "refut",
        "killed",
        "reject",
        "graveyard",
        "zero predictive",
        "exhausted",
        "fails",
        "no edge",
        "dead",
    ),
    "method_upgrade": ("rail", "harness", "control", "standard", "power reporting", "gate"),
    "inconclusive": (
        "underpowered",
        "data-blocked",
        "thin",
        "insufficient",
        "blocked",
        "inconclusive",
    ),
}
VALUE = {"survivor": 1.0, "refutation": 0.6, "method_upgrade": 0.5, "inconclusive": 0.0}


def tag(text: str, table: dict) -> list[str]:
    t = text.lower()
    return [k for k, kws in table.items() if any(w in t for w in kws)]


def main() -> None:
    led = json.loads(LEDGER.read_text("utf-8"))["decisions"]
    stats = {
        m: {
            "n": 0,
            "survivor": 0,
            "refutation": 0,
            "method_upgrade": 0,
            "inconclusive": 0,
            "value": 0.0,
            "survivor_ids": [],
        }
        for m in METHODS
    }
    for d in led:
        blob = " ".join(
            str(d.get(k, ""))
            for k in ("id", "decision", "hypothesis", "success_metric", "flagged_gap")
        )
        ms = tag(blob, METHODS)
        os_ = tag(blob, OUTCOMES)
        if not ms:
            continue
        # a decision can express several outcomes; take the most informative present
        outcome = (
            "survivor"
            if "survivor" in os_
            else "refutation"
            if "refutation" in os_
            else "method_upgrade"
            if "method_upgrade" in os_
            else "inconclusive"
            if "inconclusive" in os_
            else None
        )
        if outcome is None:
            continue
        for m in ms:
            stats[m]["n"] += 1
            stats[m][outcome] += 1
            stats[m]["value"] += VALUE[outcome]
            if outcome == "survivor":
                stats[m]["survivor_ids"].append(str(d.get("id", "UNKNOWN")))

    # ACTIVATION GATE -- must FAIL CLOSED. Counting keyword hits in ledger prose is NOT evidence
    # of a confirmed edge (it counted 63 when the true count was 0, flipping the gate open --
    # the exact fitting-on-noise failure this mode was built to prevent). Ground truth is the
    # Stage-B shadow tracker: only verdict == ELIGIBLE is a confirmed edge.
    confirmed = 0
    shadow = Path("web/axis_shadows.json")
    shadow_rows: list[dict] = []
    shadow_updated = None
    try:
        sd = json.loads(shadow.read_text("utf-8"))
        shadow_updated = sd.get("updated")
        shadow_rows = [a for a in sd.get("axes", []) if isinstance(a, dict)]
        confirmed = sum(1 for a in shadow_rows if a.get("verdict") == "ELIGIBLE")
    except (OSError, TypeError, ValueError):
        confirmed = 0
    keyword_surv = sum(s["survivor"] for s in stats.values())
    total_surv = confirmed
    mode = "ACTIVE" if confirmed >= MIN_SURVIVORS else "INSTRUMENTING"

    history = []
    try:
        history = [
            json.loads(line) for line in HIST.read_text("utf-8").splitlines() if line.strip()
        ]
    except (OSError, json.JSONDecodeError):
        history = []
    today = datetime.now(tz=UTC).date().isoformat()
    evolution = evolve_search_strategies(led, history, as_of=today)
    rows = []
    for m, s in stats.items():
        n = max(1, s["n"])
        yield_ = s["value"] / n
        # Beta posterior for uncertainty-aware ranking
        a, b = 1.0 + s["value"], 1.0 + max(0.0, s["n"] - s["value"])
        post = a / (a + b)
        rows.append(
            {
                "method": m,
                "classified_ledger_records": s["n"],
                "keyword_classified_hits": s["survivor"],
                "keyword_hit_ids": s["survivor_ids"],
                "refutation_mentions": s["refutation"],
                "method_upgrade_mentions": s["method_upgrade"],
                "inconclusive_mentions": s["inconclusive"],
                "diagnostic_value_per_record": round(yield_, 3),
                "diagnostic_posterior": round(post, 3),
            }
        )
    rows.sort(key=lambda r: -r["diagnostic_posterior"])

    print(
        "=== RESEARCH ALPHA OPTIMIZER -- which RESEARCH METHODS convert effort into knowledge ==="
    )
    mode_note = (
        "  (records only, drives NOTHING)"
        if mode == "INSTRUMENTING"
        else "  (may inform allocation)"
    )
    print(f"    MODE: {mode}{mode_note}")
    print(f"    activation needs >={MIN_SURVIVORS} confirmed edges; currently {total_surv}\n")
    print(
        f"  {'method':<20}{'docs':>5}{'kw-hit':>7}{'refut':>7}{'upg':>5}{'incon':>7}"
        f"{'diag/rec':>9}{'diag-p':>7}"
    )
    for r in rows:
        print(
            f"  {r['method']:<20}{r['classified_ledger_records']:>5}"
            f"{r['keyword_classified_hits']:>7}{r['refutation_mentions']:>7}"
            f"{r['method_upgrade_mentions']:>5}{r['inconclusive_mentions']:>7}"
            f"{r['diagnostic_value_per_record']:>9.3f}{r['diagnostic_posterior']:>7.3f}"
        )

    print(
        f"\n  value: survivor {VALUE['survivor']} | refutation {VALUE['refutation']} "
        f"| method upgrade {VALUE['method_upgrade']} | inconclusive {VALUE['inconclusive']}"
    )
    if mode == "INSTRUMENTING":
        print(
            "\n  *** INSTRUMENTING ONLY. These numbers describe HISTORY, not a recommendation. ***"
        )
        print(
            "  Fitting research allocation to zero confirmed edges would produce confident noise."
        )
        print("  The recorder runs now because method-outcome history cannot be rebuilt")
        print("  retroactively; the MODEL activates when the numerator exists (Aug 7 clocks).")

    authority_rows = evolution.get("methods", [])
    authoritative_value = sum(
        float(r.get("useful_attempts", 0.0) or 0.0)
        + float(r.get("realized_value", 0.0) or 0.0)
        for r in authority_rows
        if isinstance(r, dict)
    )
    # One daily observation, even when several schedules invoke this script. Repeated same-day
    # rows would make the six-row stagnation window equal "six executions today" rather than six
    # independent daily opportunities and could trigger a search-process mutation from duplicate
    # bookkeeping alone. The optimizer runs at the end of the research cycle, so first writer wins
    # for the day; history remains append-only.
    if not any(str(row.get("date", "")) == today for row in history):
        with HIST.open("a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {
                        "date": today,
                        "mode": mode,
                        "total_survivors": total_surv,
                        "methods": {
                            r["method"]: r.get("useful_yield_posterior")
                            for r in authority_rows
                        },
                        "total_value": authoritative_value,
                        "serendipity_domain": evolution["serendipity_channel"]["domain"],
                    }
                )
                + "\n"
            )
    OUT.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "updated": datetime.now(tz=UTC).isoformat(),
                "mode": mode,
                "activation_threshold": MIN_SURVIVORS,
                "confirmed_edges": confirmed,
                "strategy_survivors": {
                    "count": confirmed,
                    "source": str(shadow),
                    "promotion_authority": False,
                },
                "shadow_admission": {
                    "status": "MEASURED" if shadow_updated is not None else "UNMEASURED",
                    "source": str(shadow),
                    "updated": shadow_updated,
                    "eligible": [r for r in shadow_rows if r.get("verdict") == "ELIGIBLE"],
                    "accruing": [r for r in shadow_rows if r.get("verdict") == "ACCRUING"],
                    "failing": [r for r in shadow_rows if r.get("verdict") == "FAILING"],
                },
                "methods": authority_rows,
                "weak_label_diagnostics": {
                    "classification_authority": "NONE",
                    "keyword_classified_hits": keyword_surv,
                    "value_function": VALUE,
                    "methods": rows,
                    "note": (
                        "Historical ledger prose classification only. These are not strategies, "
                        "survivors, shadow candidates, attempts, or evidence."
                    ),
                },
                "search_strategy_evolution": evolution,
            },
            indent=1,
        ),
        "utf-8",
    )
    print(f"\n-> {OUT} (+ appended to {HIST})")


if __name__ == "__main__":
    main()
