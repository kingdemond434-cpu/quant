"""The company's org chart: distinct laboratories, each with its own material and method.

Breadth comes from DIFFERENT MATERIAL AND DIFFERENT METHODS, never from asking one prompt for
"profitable strategies" a hundred times (that returns a hundred breakouts). Each role names the
slice of the desk it works, the kind of row it may donate, and its mission. The scheduler in
`lab.py` gives each role calls in proportion to its MEASURED yield (box scorecard: unique rows
that compiled, were judged, passed), with an exploration floor so a new role is never starved
before it has been measured.

Paperclip's own UI can host the same chart: `ops/paperclip/company.json` is generated from this
list, every agent on the `process` adapter running `scripts/paperclip_lab_run.py --role <name>`.
No agent gets a CLI-agent adapter (claude_local / codex_local default to approval bypass).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Role:
    name: str
    lane: str          # conversion | revival | triage | red_team
    material: str      # key into lab.MATERIAL
    kinds: tuple[str, ...]
    mission: str
    rows: int = 6      # rows asked per call


_EXACT = ("Prefer kind=recipe with exact params the family takes; use kind=hypothesis only "
          "when the family's defaults are the claim. Every row needs a concrete economic "
          "mechanism, a testable_claim, and a falsifier. No parameter sweeps: one row per BET.")

ROLES: tuple[Role, ...] = (
    Role("dataset_converter", "conversion", "datasets", ("recipe", "hypothesis"),
         "Turn stranded or unused datasets into executable MT5 cells. For each dataset, name "
         "the MT5 instrument it plausibly moves (directly, or indirectly through a proxy), the "
         "registered family that expresses it, and the publication lag that keeps it PIT. "
         + _EXACT),
    Role("dead_producer_reviver", "revival", "producers", ("revival", "recipe", "hypothesis"),
         "For each dead or starved producer: diagnose the most likely reason it emits nothing "
         "(input gone, filter too strict, vocabulary mismatch, budget, schema drift), propose "
         "ONE minimal tweak for its owner (kind=revival), and donate the cells its material "
         "would have produced had it worked. Never propose loosening statistical gates."),
    Role("graveyard_descendants", "conversion", "graveyard", ("recipe", "hypothesis"),
         "Read cells the gauntlet rejected and which gates they failed. Propose DESCENDANTS that "
         "change the mechanism (different session, regime condition, instrument transfer, "
         "timeframe), never a parameter nudge toward the failed sample -- that is overfitting. "
         "Set parent_cell. " + _EXACT),
    Role("paper_converter", "conversion", "corpus", ("recipe", "hypothesis"),
         "Read practitioner, blog and paper rows that never became cells (no exact rule). "
         "Extract the exact rule the text implies, map it to a registered family and MT5 "
         "symbols, and donate it. Skip rows with no testable mechanism. " + _EXACT),
    Role("repo_converter", "conversion", "strategies", ("recipe", "hypothesis"),
         "Read public strategy catalogue rows (repos, EA listings, sites). Recover the rule, "
         "map it to a registered family and MT5 symbols. " + _EXACT),
    Role("cross_asset_proxy", "conversion", "universe", ("recipe", "hypothesis"),
         "Find INDIRECT edges: lead-lag and proxy links between MT5 instruments and the "
         "economies behind them (commodity exporters and their currencies, rates and metals, "
         "risk proxies and havens, energy and CAD/NOK). Express each with a registered family "
         "such as relative_value, correlation_regime or carry. " + _EXACT),
    Role("calendar_event_lab", "conversion", "universe", ("recipe", "hypothesis"),
         "Calendar and scheduled-flow mechanisms: month/quarter turns, fixings, settlement "
         "windows, central-bank weeks, holiday liquidity, index rebalances, as they hit MT5 "
         "FX, metals, energy and index CFDs. " + _EXACT),
    Role("session_microstructure_lab", "conversion", "universe", ("recipe", "hypothesis"),
         "Intraday session mechanisms: Asia/London/NY handoffs, opening ranges, liquidity "
         "vacuums, gap behaviour, volatility transitions, on M5-H1 charts. " + _EXACT),
    Role("world_coverage_lab", "conversion", "regions", ("recipe", "hypothesis"),
         "Under-covered countries and regions: exotic FX, regional indices, local commodity "
         "links. For each region named, the mechanism that moves its MT5 instruments. " + _EXACT),
    Role("unknown_unknowns", "conversion", "families", ("hypothesis", "recipe"),
         "Mechanism classes the desk's family list does not obviously cover. Name the closest "
         "registered family that can express a first test of it and say in the mechanism what "
         "a dedicated family would add. " + _EXACT),
    Role("triage_prior", "triage", "queue", ("triage",),
         "Score UNJUDGED cells for economic plausibility (prior in [0,1]) so the most "
         "plausible are worth judging first. Flag leak (uses information not known at the "
         "decision time) or duplicate (same bet as another listed cell, name it in dup_of). "
         "You never decide a verdict; the gauntlet does.", rows=40),
)

RED_TEAM_MISSION = (
    "You are the pre-gauntlet red team. For each numbered candidate, decide KILL or KEEP. KILL "
    "only for: look-ahead or data not available at decision time; a duplicate of another "
    "candidate in this list (same bet reworded); no economic mechanism; a mechanism that "
    "contradicts its own claim; a parameter choice that only makes sense as a fit to past data. "
    "Return JSON {\"kill\": [{\"i\": <index>, \"why\": \"...\"}]}. Keep everything else.")

BY_NAME = {r.name: r for r in ROLES}
