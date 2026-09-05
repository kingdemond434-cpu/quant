"""Rank what data to acquire next by what it would UNLOCK, not by how interesting it sounds.

Renaissance told the Senate it collects every public series that might move prices. The
operational version of that is not "collect everything"; it is a ranked queue in which each
candidate source is scored by the coverage it would create. `libs.autodiscovery.data_opportunity`
already scores a catalogue of sources by `expected_alpha_value / cost` and names the families each
would unlock. This joins that catalogue to three things the desk now measures:

    COVERAGE GAPS      `regime_coverage`: state buckets where no sleeve pays, and which
                       families have never been tried there
    FAMILY BARRENNESS  `funnel_census`: families whose Beta posterior says they are barren AT
                       CURRENT INPUTS -- carry with no swap terms, event_reaction with no
                       `actual`, cross_asset_residual before the driver map existed
    NAMED DATA GAPS    every `gaps` entry the state engines emit -- "no `actual` on the
                       calendar", "no tape for X", "no M15 for Y" -- each of which is a source

A source's rank is its catalogue value multiplied by how many uncovered states its families
would enter, plus a bonus for closing a NAMED gap that a running engine has already asked for.
The output is an acquisition queue with, for each item, exactly which engine asked and why.

THE CRAWLER READS THIS. `world_crawler` hunts datasets by keyword; this hands it the ranked
targets so it hunts what the desk needs rather than what it finds.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

OUT = BASE / "reports" / "DATA_PROSPECTOR.json"
COVERAGE = BASE / "reports" / "REGIME_COVERAGE.json"
STATE_VECTOR = BASE / "data" / "state_vector.json"
CRAWLER_TARGETS = BASE / "data" / "prospector_targets.json"

#: Named gaps the state engines emit, mapped to the source that closes them. DECLARED because a
#: gap message is written by an engine and its remedy is a fact about the world.
GAP_SOURCES: dict[str, dict] = {
    "surprise": {"source": "economic calendar with ACTUAL prints (e.g. FF/Investing/TE history)",
                 "unlocks": ["event_reaction", "macro_surprise_residual"],
                 "why": "surprise = actual - forecast is uncomputable without `actual`"},
    "spread_history": {"source": "tick tape for every book symbol (data/tape/ticks/<SYM>)",
                       "unlocks": ["liquidity_regime", "orderflow_imbalance", "execution_cost"],
                       "why": "liquidity state is UNMEASURED without the venue's own spreads"},
    "M15": {"source": "M15 bars for book symbols", "unlocks": ["intraday regime tiers"],
            "why": "the 15-minute regime tier refuses to upsample hourly bars"},
    "M5": {"source": "M5 bars for book symbols", "unlocks": ["execution-state regime tier"],
           "why": "the 5-minute tier refuses to upsample"},
    "factor:RATES": {"source": "UST10Y/UST05Y/UKGILT H1 bars",
                     "unlocks": ["dollar_real_rates", "rates_repricing_residual"],
                     "why": "the real-rate factor regime cannot be fitted"},
    "factor:RISK": {"source": "US500/NAS100 H1 bars", "unlocks": ["risk_appetite", "global_beta"],
                    "why": "the risk factor regime cannot be fitted"},
    "factor:OIL": {"source": "XBRUSD/XTIUSD H1 bars", "unlocks": ["commodity_cad", "energy_complex"],
                   "why": "the energy factor regime cannot be fitted"},
    "factor:GROWTH": {"source": "XCUUSD/CHINAH H1 bars", "unlocks": ["commodity_aud", "growth_dollar"],
                      "why": "the growth factor regime cannot be fitted"},
    "session": {"source": "broker_clock.json (record the terminal's UTC offset once)",
                "unlocks": ["session conditioning", "plumbing_miner", "clock_transition"],
                "why": "every clock-based engine refuses to assume UTC"},
}


#: Catalogue entries the standing mandate forbids hunting. `funding_rates` is a perpetual-swap
#: quantity: it exists only on crypto exchanges, and the mandate (2026-08-18) says no
#: crypto-exchange universe may ever be hunted again. Excluded by name, with the exclusion
#: reported, rather than quietly left out of a list somebody later wonders about.
MANDATE_EXCLUDED: dict[str, str] = {
    "funding_rates": "perpetual-swap funding is exchange-native; forbidden universe",
}


def _catalogue() -> list[dict]:
    try:
        from libs.autodiscovery.data_opportunity import _CATALOG
    except Exception:                                            # noqa: BLE001
        return []
    out = []
    for d in _CATALOG:
        row = d.model_dump() if hasattr(d, "model_dump") else dict(d)
        if str(row.get("name")) in MANDATE_EXCLUDED:
            continue
        row["expected_alpha_value"] = float(getattr(d, "expected_alpha_value", 0.0))
        out.append(row)
    return out


def _coverage_gaps() -> tuple[list[str], dict[str, int]]:
    """Uncovered states, and how many of them each never-tried family could enter."""
    try:
        doc = json.loads(COVERAGE.read_text("utf-8"))
    except (OSError, ValueError):
        return [], {}
    uncovered = list(doc.get("uncovered") or [])
    never: dict[str, int] = {}
    for key in uncovered:
        for fam in (doc.get("coverage") or {}).get(key, {}).get("families_never_tried_here", []):
            never[fam] = never.get(fam, 0) + 1
    return uncovered, never


def _named_gaps() -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        sv = json.loads(STATE_VECTOR.read_text("utf-8"))
    except (OSError, ValueError):
        return out
    for k, v in (sv.get("gaps") or {}).items():
        out[k] = str(v)
    for scope in ("event", "liquidity"):
        for sym, st in ((sv.get(scope) or {}).get("per_symbol") or {}).items():
            for g, why in (st.get("gaps") or {}).items():
                out.setdefault(g, str(why))
    return out


def _barren() -> dict[str, float]:
    try:
        from libs.research import funnel_census as fc
        recs = fc.build(ROOT)
        out = {}
        for name, r in recs.items():
            a, b = r.posterior("certified")
            out[name] = round(a / (a + b), 4) if (a + b) > 0 else 0.0
        return out
    except Exception:                                            # noqa: BLE001
        return {}


def rank() -> dict:
    uncovered, never = _coverage_gaps()
    gaps = _named_gaps()
    barren = _barren()
    items: list[dict] = []

    for gap, why in gaps.items():
        key = next((k for k in GAP_SOURCES if gap == k or gap.startswith(k)), None)
        if key is None:
            continue
        spec = GAP_SOURCES[key]
        entered = sum(never.get(f, 0) for f in spec["unlocks"])
        items.append({"source": spec["source"], "asked_by": gap, "engine_said": why[:160],
                      "unlocks": spec["unlocks"], "uncovered_states_entered": entered,
                      "score": round(3.0 + entered + 2.0 * sum(
                          1 for f in spec["unlocks"] if barren.get(f, 1.0) < 0.02), 3),
                      "kind": "named_gap"})

    for d in _catalogue():
        unlocks = list(d.get("unlocks") or [])
        entered = sum(never.get(f, 0) for f in unlocks)
        base = float(d.get("expected_alpha_value") or 0.0)
        items.append({"source": str(d.get("name")), "asked_by": "catalogue",
                      "engine_said": "", "unlocks": unlocks,
                      "uncovered_states_entered": entered,
                      "score": round(base * (1.0 + entered) + 1.5 * sum(
                          1 for f in unlocks if barren.get(f, 1.0) < 0.02), 3),
                      "kind": "catalogue"})

    seen: set[str] = set()
    ranked = []
    for it in sorted(items, key=lambda x: -x["score"]):
        if it["source"] in seen:
            continue
        seen.add(it["source"])
        ranked.append(it)
    return {"generated_utc": datetime.now(tz=UTC).isoformat(), "n_uncovered_states": len(uncovered),
            "families_never_tried_in_uncovered": never, "named_gaps": gaps,
            "barren_families": {k: v for k, v in barren.items() if v < 0.02},
            "mandate_excluded": MANDATE_EXCLUDED, "queue": ranked}


def run() -> dict:
    doc = rank()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    # The crawler's targeting file: source strings only, in rank order, with the reason.
    CRAWLER_TARGETS.parent.mkdir(parents=True, exist_ok=True)
    CRAWLER_TARGETS.write_text(json.dumps(
        {"generated_utc": doc["generated_utc"],
         "targets": [{"query": it["source"], "why": it["engine_said"] or "catalogue",
                      "unlocks": it["unlocks"], "score": it["score"]}
                     for it in doc["queue"][:25]]}, indent=1), "utf-8")
    return doc


def main() -> int:
    argparse.ArgumentParser().parse_args()
    doc = run()
    print(f"DATA PROSPECTOR  {len(doc['queue'])} sources ranked; "
          f"{doc['n_uncovered_states']} uncovered states; "
          f"{len(doc['named_gaps'])} named gaps from running engines")
    for it in doc["queue"][:15]:
        print(f"  {it['score']:6.2f}  {it['source'][:60]:60s}  asked_by={it['asked_by']}")
    print(f"written: {OUT}  targets: {CRAWLER_TARGETS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
