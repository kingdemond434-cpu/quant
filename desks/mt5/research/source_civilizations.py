#!/usr/bin/env python3
"""THE SOURCE CIVILIZATIONS -- two public lineages and a set of research primitives, absorbed.

THE PRINCIPAL'S ORDER, 2026-09-17, PERMANENT. Absorb every useful mechanism, data-quality trick,
research primitive and behavioural sensor the world has published. Published thresholds are
PRIORS THE GENOME MUTATES, never sacred parameters. A claim is a HYPOTHESIS, never verified
alpha. And NO AUTHOR IS MONITORED: what is encoded here are ideas, as families, with their own
falsifiers -- there is no crawler pointed at a person, no feed of anybody's posts, and nothing in
this module fetches a named individual's output on a schedule.

WHY THE DISTINCTION MATTERS AND IS NOT A FORMALITY. A desk that tracks an author inherits the
author's survivorship: it learns what the author said loudly and recently, weighted by how well
it worked for them on the sample they chose to publish. A desk that absorbs the MECHANISM inherits
a testable claim about a constrained participant, which its own ten gates can kill. The first is
following; the second is research. Everything below is the second, and every family carries the
falsifier that would end it.

WHAT IS HERE.

  THE L1VSUN LINEAGE, six families about derivative-market behaviour and research hygiene:
    1  funding ecology          crowding read off funding, OI, basis, liquidations and options
    2  forced-flow ecology      abnormal liquidation into depleted depth -- THREE populations
    3  narrative lifecycle      birth -> velocity -> diffusion -> saturation -> decay -> revival
    4  thesis/event clocks      every enrolled clock and live sleeve has a staleness age
    5  evidence verification    delegated whole to `evidence_watchtower`
    6  specialist discipline    the six role separations, and where each is enforced HERE

  THE BL888M LINEAGE, six families about forecasting and participants. Three of them (market
  calibration, crowd-vs-model disagreement, the fractional-Kelly reference) live in
  `prediction_markets`. The other three live here: counterfactual GATE ATTRIBUTION, the BOUNDED
  LLM CONTRIBUTION policy, and SMART-PARTICIPANT ARCHAEOLOGY with its provenance firewall.

  THE RESEARCH PRIMITIVES, taken as ideas with no author lineage attached: Hawkes event-intensity
  modelling, prediction-market dependency constraints, the opportunistic-vs-routine insider
  classifier (EVENT LANE ONLY), a multimodal central-bank collector contract, the cheap-monitor /
  expensive-reasoner split with its information-independence rule, and source -> paper -> citation
  archaeology.

  THE CROSS-SOURCE INTERACTION FORGE: nine named cells where two civilizations' legs meet, each
  minting BOTH an agreement and a DISAGREEMENT hypothesis, because "the crowd and the model
  disagree" is a different and usually better trade than "they agree".

EVERY FAMILY IS A SENSOR OR MECHANISM FOR AN MT5 INSTRUMENT (mandate 2026-08-18). The targets are
XAUUSD, NAS100, US500, USDJPY, AUDUSD, USDX and XTIUSD, and the crypto-native readings that feed
families 1 and 2 are REFERENCE DATA informing those instruments -- never a hunted universe. No
crypto-exchange ground is scouted, ranked, scored or queued anywhere below.

AND ON THIS BOX MOST OF THOSE READINGS DO NOT EXIST. `data/axes/crypto_*.json` is absent and
`shadow_institutional` is not on the tree, so the funding/OI/liquidation/options legs are
UNMEASURED BY NAME (L1.28a): the hypotheses are still minted, still expanded into descendants,
and the descendants that need an absent leg are BLOCKED with the sensor named. An absent sensor
is a disposition, not a reason to not have had the idea.

    python desks/mt5/research/source_civilizations.py --dry-run
    python desks/mt5/research/source_civilizations.py --budget-s 300
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as R  # noqa: E402
from libs.research import external_federation as XF  # noqa: E402
from research import transformation_miners as TM  # noqa: E402

UNMEASURED = "UNMEASURED"
REPORT = DESK / "reports" / "SOURCE_CIVILIZATIONS.json"
THESIS_CLOCKS = DESK / "data" / "thesis_clocks.json"
GATE_ATTRIBUTION = DESK / "reports" / "GATE_ATTRIBUTION.json"
AXES = DESK / "data" / "axes"
UNIVERSE = DESK / "data" / "universe"
CALENDAR = DESK / "data" / "forced_flow_calendar.json"
SLEEVES = DESK / "data" / "sleeves.json"
SHADOW_STATE = DESK / "reports" / "shadow" / "shadow_state.json"
FORWARD_RECONCILE = DESK / "data" / "forward_reconcile.json"
GATE_LEDGER = DESK / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"

#: THE MT5 TARGETS. Every family below ends on one of these; a crypto reading is an INPUT to a
#: hypothesis about one of them and is never itself hunted.
TARGETS: tuple[str, ...] = ("XAUUSD", "NAS100", "US500", "USDJPY", "AUDUSD", "USDX", "XTIUSD")
TARGET_CLASS: dict[str, str] = {"XAUUSD": "commodities", "XTIUSD": "commodities",
                                "NAS100": "indices", "US500": "indices", "USDJPY": "forex",
                                "AUDUSD": "forex", "USDX": "forex"}
RISK_ON: tuple[str, ...] = ("NAS100", "US500", "AUDUSD")
RISK_OFF: tuple[str, ...] = ("XAUUSD", "USDX", "USDJPY")


# ------------------------------------------------ LEGALITY IS A ROUTER, NEVER A RESEARCH BRAKE
#: THE PRINCIPAL, 2026-09-17. The order on every source is DISCOVER -> CAPTURE METADATA ->
#: LEGAL/ACCESS CLASSIFICATION -> EVIDENCE CLASSIFICATION -> RESEARCH. Never "looks risky ->
#: discard": discarding on a hunch is not caution, it is an unrecorded decision that deletes the
#: desk's ability to notice the source later. A source is ROUTED by what it is, and the route is
#: written down.
SOURCE_PIPELINE: tuple[str, ...] = ("DISCOVER", "CAPTURE_METADATA", "ACCESS_CLASSIFICATION",
                                    "EVIDENCE_CLASSIFICATION", "RESEARCH")

#: THREE INDEPENDENT LABELS, and their independence is the whole design. "Fringe" is a
#: CREDIBILITY reading and says nothing about whether the desk may look; "public" is an ACCESS
#: reading and says nothing about whether the content is true; and neither says whether it
#: predicts anything, which is the third axis and the only one the gauntlet settles. Collapsing
#: them into one "is this source OK" flag is how a desk loses the weird public material that turns
#: out to carry a mechanism.
ACCESS_LABELS: tuple[str, ...] = ("PUBLIC", "PUBLIC_WITH_TERMS", "LICENSED", "OPEN_DATA",
                                  "PUBLIC_ARCHIVE", "PUBLIC_SOCIAL", "USER_SUBMITTED",
                                  "ACCESS_UNCLEAR", "PRIVATE", "CONFIDENTIAL_MNPI",
                                  "STOLEN_UNAUTHORIZED")
CREDIBILITY_LABELS: tuple[str, ...] = ("AUTHORITATIVE", "RELIABLE", "UNRELIABLE", "FRINGE",
                                       "CONTRADICTED", "UNKNOWN")
PREDICTIVE_STATES: tuple[str, ...] = ("UNTESTED", "PREDICTIVE", "NOT_PREDICTIVE",
                                      "NARRATIVE_FEATURE")

#: WHAT EACH ACCESS LABEL ROUTES (LAWS 5e, 2026-09-23). `machine_use_allowed` is the field every
#: source row carries and the crawlers read, and since 2026-09-23 it answers ONE question -- "is
#: this row mined at all" -- whose answer is True for everything off the five refused acts.
#: `consume` follows it. The old table said False for PUBLIC_WITH_TERMS, LICENSED and
#: ACCESS_UNCLEAR and routed the last of those to QUARANTINE; all three were DISCOVERY BRAKES THE
#: DESK IMPOSED ON ITSELF, not legal requirements, and all three are deleted. What a licence or a
#: terms note still withholds is `redistribute_allowed`, which is where it now lives.
ACCESS_BEHAVIOUR: dict[str, dict[str, Any]] = {
    "PUBLIC": {"route": "RESEARCHABLE", "consume": True, "machine_use_allowed": True,
               "redistribute_allowed": False,
               "why": "public material at whatever evidence weight its credibility earns"},
    "OPEN_DATA": {"route": "RESEARCHABLE", "consume": True, "machine_use_allowed": True,
                  "redistribute_allowed": True,
                  "why": "published under an open-data licence: redistribution included"},
    "PUBLIC_ARCHIVE": {"route": "RESEARCHABLE", "consume": True, "machine_use_allowed": True,
                       "redistribute_allowed": False,
                       "why": "an archive of material that was public when it was captured"},
    "PUBLIC_SOCIAL": {"route": "RESEARCHABLE", "consume": True, "machine_use_allowed": True,
                      "redistribute_allowed": False,
                      "why": "public social posting; credibility carries the caveat, not access"},
    "USER_SUBMITTED": {"route": "RESEARCHABLE", "consume": True, "machine_use_allowed": True,
                       "redistribute_allowed": False,
                       "why": "submitted for publication by its own author"},
    "PUBLIC_WITH_TERMS": {"route": "RESEARCHABLE", "consume": True, "machine_use_allowed": True,
                          "redistribute_allowed": False,
                          "why": "MINED AND TESTED IN FULL; the terms or robots note is a "
                                 "routing label that withholds REDISTRIBUTION and nothing else"},
    "LICENSED": {"route": "RESEARCHABLE", "consume": True, "machine_use_allowed": True,
                 "redistribute_allowed": False,
                 "why": "mined and tested; the licence bounds redistribution, not research"},
    "ACCESS_UNCLEAR": {"route": "RESEARCHABLE", "consume": True, "machine_use_allowed": True,
                       "redistribute_allowed": False,
                       "why": "MINED AND TESTED WITH THE LABEL ATTACHED: the unclear-access "
                              "quarantine was deleted on 2026-09-23; an unresolved access "
                              "question is a provenance note, never a reason to leave it unread"},
    "PRIVATE": {"route": "REFUSED", "consume": False, "machine_use_allowed": False,
                "redistribute_allowed": False,
                "why": "private material is never an alpha input"},
    "CONFIDENTIAL_MNPI": {"route": "REFUSED", "consume": False, "machine_use_allowed": False,
                          "redistribute_allowed": False,
                          "why": "material non-public information is never an alpha input"},
    "STOLEN_UNAUTHORIZED": {"route": "REFUSED", "consume": False, "machine_use_allowed": False,
                            "redistribute_allowed": False,
                            "why": "a stolen or unauthorised dataset is never an alpha input"},
}

#: Credibility sets the EVIDENCE WEIGHT and nothing else. A FRINGE public claim is kept, at 0.15,
#: because the question is not "is this true" -- it is "can we lawfully observe it, what does it
#: represent, and does its EXISTENCE predict anything". Deleting probably-false public material
#: destroys the only record of what the fringe believed before the move.
EVIDENCE_WEIGHT: dict[str, float] = {"AUTHORITATIVE": 1.0, "RELIABLE": 0.7, "UNKNOWN": 0.4,
                                     "UNRELIABLE": 0.2, "FRINGE": 0.15, "CONTRADICTED": 0.1}

#: THE HARD BOUNDARY -- the five ACTS of `libs.research.access_classifier.HARD_BOUNDARY`, verbatim
#: and in the same order, restated so no reader has to infer it from the table above. Five, not
#: six: a fence checks the count, so a later session cannot quietly add a brake and call it a
#: boundary. Nothing off this list refuses anything.
HARD_BOUNDARY: tuple[str, ...] = (
    "no credential theft or logging in as someone else",
    "no bypassing an access control or a paywall",
    "no material non-public information",
    "no stolen or leaked private data",
    "no personal data harvesting or doxxing",
)


def _external_classifier() -> Any:
    """`libs/research/access_classifier` when another builder has landed it; None otherwise.

    IMPORTED, NEVER RE-IMPLEMENTED. One vocabulary owner or two that disagree about whether a
    source is PUBLIC_WITH_TERMS -- and the second outcome is worse than having no module at all.
    """
    try:
        from libs.research import access_classifier
        return access_classifier
    except Exception:
        return None


def classify_source(row: Mapping[str, Any]) -> dict[str, Any]:
    """The three labels, the route they imply, and the pipeline stage this row has reached.

    Unknown spellings resolve to ACCESS_UNCLEAR rather than PUBLIC, because the LABEL should be
    honest about what was measured -- but since LAWS 5e (2026-09-23) that label is MINED AND
    TESTED like any other, at full evidence weight, with the unresolved-access fact carried as
    provenance. An unrecognised credibility becomes UNKNOWN, which keeps the source and prices its
    evidence at 0.4 -- a discount, not a deletion.
    """
    ext = _external_classifier()
    if ext is not None and hasattr(ext, "classify"):     # pragma: no cover - other builder
        try:
            got = ext.classify(dict(row))
            if isinstance(got, Mapping) and got.get("access_label"):
                return dict(got)
        except Exception:
            pass
    access = str(row.get("access_label") or "").upper()
    access = access if access in ACCESS_LABELS else "ACCESS_UNCLEAR"
    cred = str(row.get("credibility") or "").upper()
    cred = cred if cred in CREDIBILITY_LABELS else "UNKNOWN"
    pred = str(row.get("predictive_state") or "").upper()
    pred = pred if pred in PREDICTIVE_STATES else "UNTESTED"
    beh = ACCESS_BEHAVIOUR[access]
    return {"source_id": str(row.get("source_id") or row.get("url") or ""),
            "access_label": access, "credibility": cred, "predictive_state": pred,
            "route": beh["route"], "may_consume_content": beh["consume"],
            "machine_use_allowed": beh["machine_use_allowed"],
            "redistribute_allowed": beh["redistribute_allowed"],
            "terms_note": str(row.get("terms_note") or row.get("licence_note") or ""),
            "evidence_weight": EVIDENCE_WEIGHT[cred],
            "stage": SOURCE_PIPELINE[-1] if beh["consume"] else "ACCESS_CLASSIFICATION",
            "why": beh["why"], "pipeline": list(SOURCE_PIPELINE),
            "refused": beh["route"] == "REFUSED",
            # ALWAYS FALSE (LAWS 5e, 2026-09-23). The key stays so an old reader does not
            # KeyError; the quarantine behind it was deleted.
            "quarantined": False,
            "hard_boundary": list(HARD_BOUNDARY),
            "rule": "access routes and provenances, it never stops mining: every label off the "
                    "five refused acts is mined and tested, and weird, fringe and contradicted "
                    "material is preserved as an evidence object at low weight"}


def _plant_source(run: Run, source_id: str, *, kind: str, meta: Mapping[str, Any],
                  discovered_via: str, discovered_from: str = "source_civilizations",
                  url: str = "", language: str = "en") -> bool:
    """One classified `sources` row, upserted. Returns True when it is new.

    Every row lands CLASSIFIED AND MINEABLE: the licence note carries the access route and the
    evidence weight, so a later reader knows what may be REDISTRIBUTED and how much the row
    weighs. Since LAWS 5e no row is parked for access -- only the five refused acts land
    `refused`.
    """
    verdict = classify_source(meta)
    if run.dry_run or run.conn is None:
        run.notes.append({"where": "plant_source", "why": f"dry run: {source_id} "
                                                          f"[{verdict['access_label']}]"})
        return False
    row = run.conn.execute("SELECT source_id FROM sources WHERE source_id=?",
                           (source_id,)).fetchone()
    note = (f"{verdict['access_label']}/{verdict['credibility']}/{verdict['predictive_state']} "
            f"-> {verdict['route']} (evidence weight {verdict['evidence_weight']}): "
            f"{verdict['why']}")[:900]
    payload = json.dumps({**dict(meta), **verdict}, sort_keys=True, default=str)
    if row is None:
        run.conn.execute(
            "INSERT INTO sources(source_id, url, kind, language, country, asset_classes_json, "
            "discovered_from, discovered_via, first_seen, last_crawled, status, licence_note, "
            "meta_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (source_id, url, kind, language, "", json.dumps([]), discovered_from, discovered_via,
             _now(), None, "refused" if verdict["refused"] else "candidate", note, payload))
        return True
    run.conn.execute("UPDATE sources SET licence_note=?, meta_json=?, discovered_via=? "
                     "WHERE source_id=?", (note, payload, discovered_via, source_id))
    return False


# --------------------------------- RECURSIVE, OPEN-ENDED SOURCE DISCOVERY (seed NODES, not feeds)
#: THE SEEDS ARE NODES, NOT FEEDS. A handle enters this desk as a POINTER to public work --
#: papers, references, code, collaborators, datasets, historical predecessors -- and the pointer
#: is followed once. The handle's own timeline, posts and feed are NEVER monitored or mined
#: (principal's standing order): monitoring a person makes the desk a follower of that person's
#: survivorship, and the whole value of the seed is the LITERATURE it leads to.
SEED_NODES: tuple[dict[str, Any], ...] = (
    {"handle": "RohOnChain", "role": "seed node: research primitives taken as IDEAS",
     "expand_through": ("papers", "references", "code", "datasets", "collaborators",
                        "historical_predecessors"),
     "monitored": False, "feeds_or_posts_mined": False,
     "access_label": "PUBLIC", "credibility": "UNKNOWN",
     "contributes": ("hawkes_event_intensity", "prediction_market_dependency",
                     "insider_opportunistic_classifier", "multimodal_central_bank",
                     "cheap_monitor_expensive_reasoner", "source_paper_citation_archaeology")},
    {"handle": "L1vsun", "role": "seed node: derivative-behaviour and research-hygiene families",
     "expand_through": ("papers", "references", "code", "datasets", "collaborators",
                        "historical_predecessors"),
     "monitored": False, "feeds_or_posts_mined": False,
     "access_label": "PUBLIC", "credibility": "UNKNOWN",
     "contributes": ("funding_ecology", "forced_flow", "narrative_lifecycle", "thesis_clocks",
                     "evidence_verification", "specialist_discipline")},
    {"handle": "bl888m", "role": "seed node: forecasting and participant families",
     "expand_through": ("papers", "references", "code", "datasets", "collaborators",
                        "historical_predecessors"),
     "monitored": False, "feeds_or_posts_mined": False,
     "access_label": "PUBLIC", "credibility": "UNKNOWN",
     "contributes": ("prediction_calibration", "crowd_vs_model", "fractional_kelly_reference",
                     "gate_attribution", "bounded_llm", "smart_participant_archaeology")},
)

#: The recursion, in order. Each layer's members are the next layer's seeds, and the walk stops
#: when the MARGINAL INFORMATION VALUE of the next layer falls below what the same compute would
#: buy elsewhere -- with the stopping reason recorded, because "we stopped" and "there was nothing
#: left" are different findings and only one of them is exhaustion (L1.51).
EXPANSION_LAYERS: tuple[str, ...] = ("source", "people", "papers", "datasets", "apps", "forums",
                                     "code", "new_sources")
#: The opportunity floor: below this marginal yield, the next layer is worth less than the hour
#: spent on any other research the desk could run instead.
MARGINAL_VALUE_FLOOR = 0.15


def expand_seed(run: Run, seed: Mapping[str, Any], *,
                layers: Sequence[str] = EXPANSION_LAYERS,
                floor: float = MARGINAL_VALUE_FLOOR) -> dict[str, Any]:
    """Walk one seed NODE outward through its public work, planting a classified source per hop.

    Every hop writes a PROVENANCE EDGE (`registry.link`) from the seed to the node it produced, so
    when a survivor eventually comes out of a paper four layers downstream the credit walks back
    to the seed that pointed at it. That edge is the only reason a seed is worth having: without
    it the desk cannot tell a productive pointer from a fashionable one.
    """
    handle = str(seed.get("handle") or "seed")
    seed_id = f"seed:{handle}"
    planted = {"seed": handle, "monitored": False, "feeds_or_posts_mined": False,
               "seed_source_new": _plant_source(
                   run, seed_id, kind="seed_node",
                   meta={**dict(seed), "source_id": seed_id,
                         "predictive_state": "UNTESTED"},
                   discovered_via="principal's standing order 2026-09-17")}
    by_layer: list[dict[str, Any]] = []
    cumulative = 1
    stop_reason = "every declared layer was walked"
    for layer in layers:
        if layer == "source":
            continue
        if run.left <= 0:
            stop_reason = f"budget exhausted at layer {layer!r}; the remaining layers are owed"
            break
        members = _layer_members(seed, layer)
        new = 0
        for node in members:
            sid = f"{layer}:{handle}:{node['name'][:60]}"
            if _plant_source(run, sid, kind=layer,
                             meta={**node, "source_id": sid,
                                   "access_label": node.get("access_label", "PUBLIC"),
                                   "credibility": node.get("credibility", "UNKNOWN"),
                                   "predictive_state": "UNTESTED"},
                             discovered_via=f"expansion:{layer}", discovered_from=seed_id):
                new += 1
            if not run.dry_run and run.conn is not None:
                R.link("source", seed_id, "source", sid, f"expanded:{layer}", conn=run.conn)
        marginal = new / max(cumulative, 1)
        cumulative += len(members)
        by_layer.append({"layer": layer, "candidates": len(members), "new": new,
                         "marginal_value": marginal})
        if members and marginal < floor:
            stop_reason = (f"marginal information value {marginal:.3f} at layer {layer!r} fell "
                           f"below the opportunity floor {floor}: the next layer is worth less "
                           "than the same compute spent on any other research the desk could run")
            break
    if not run.dry_run and run.conn is not None:
        run.conn.commit()
    planted.update({"layers": by_layer, "stop_reason": stop_reason,
                    "layers_walked": len(by_layer), "layers_declared": len(layers) - 1,
                    "exhausted": stop_reason == "every declared layer was walked",
                    "rule": "seed handles are expanded through PUBLIC papers, references, code, "
                            "collaborators, datasets and predecessors ONLY; their feeds and posts "
                            "are never monitored or mined"})
    return planted


def _layer_members(seed: Mapping[str, Any], layer: str) -> list[dict[str, Any]]:
    """What one layer of a seed's public work contains, from what this tree already declares.

    NOT A CRAWL. The members come from the mechanisms the seed contributed and the primary
    literature those mechanisms name -- material the desk already holds. A layer the tree knows
    nothing about returns [] and the marginal-value test sees the zero, which is exactly how the
    recursion is supposed to terminate.
    """
    contributes = [str(c) for c in (seed.get("contributes") or ())]
    if layer == "papers":
        return [{"name": ref["title"], "why": ref["why"], "family": fam, "access_label": "PUBLIC",
                 "credibility": "RELIABLE"}
                for fam in contributes for ref in LITERATURE.get(fam, ())]
    if layer == "people":
        return [{"name": f"authors of {ref['title'][:40]}", "family": fam,
                 "access_label": "PUBLIC", "credibility": "UNKNOWN",
                 "why": "the paper's authors are the next hop, through their OTHER public work"}
                for fam in contributes for ref in LITERATURE.get(fam, ())][:6]
    if layer == "datasets":
        return [{"name": leg, "why": SENSOR_LEGS[leg], "access_label": "ACCESS_UNCLEAR",
                 "credibility": "UNKNOWN"}
                for leg in SENSOR_LEGS if any("funding" in c or "flow" in c for c in contributes)]
    if layer == "code":
        return [{"name": f"reference implementation: {fam}", "family": fam,
                 "access_label": "PUBLIC", "credibility": "UNKNOWN",
                 "why": "public code is a mechanism written down unambiguously"}
                for fam in contributes if fam in LITERATURE]
    return []


# --------------------------------------------------------------------------- priors, not laws
@dataclass(frozen=True)
class Prior:
    """A published threshold, and the ladder the genome is allowed to walk instead of it.

    THE WHOLE POINT. "Funding above the 35th percentile for three readings" is somebody's fitted
    parameter on somebody's sample, and copying it is copying their overfit. It enters here as
    `published`, sits INSIDE a ladder that brackets it on both sides, and every rung is minted as
    its own cell. If the published rung wins, that is evidence; if a neighbour wins, the published
    number was a coincidence; and if none win, the mechanism is dead at every parameterisation,
    which is the strongest kill available.
    """

    name: str
    published: float
    ladder: tuple[float, ...]
    unit: str
    why: str

    def rungs(self) -> tuple[float, ...]:
        return tuple(sorted({*self.ladder, self.published}))


PRIORS: dict[str, Prior] = {
    "funding_percentile": Prior(
        "funding_percentile", 35.0, (10.0, 20.0, 35.0, 50.0, 75.0), "percentile",
        "the published crowding trigger; the ladder brackets it so the desk measures the "
        "threshold rather than inheriting it"),
    "funding_readings": Prior(
        "funding_readings", 3.0, (1.0, 2.0, 3.0, 5.0, 8.0), "consecutive readings",
        "persistence is what separates a crowded book from one noisy print"),
    "liquidation_multiple": Prior(
        "liquidation_multiple", 3.0, (1.5, 3.0, 6.0, 10.0), "x median 6h volume",
        "abnormal is relative to a window, and the window is as fitted as the multiple"),
    "liquidation_window_h": Prior(
        "liquidation_window_h", 6.0, (1.0, 3.0, 6.0, 24.0), "hours",
        "the baseline window the multiple is measured against"),
    "narrative_saturation": Prior(
        "narrative_saturation", 60.0, (30.0, 45.0, 60.0, 80.0), "% of sources carrying it",
        "saturation is the moment the last marginal buyer has already heard it"),
    "narrative_halflife_h": Prior(
        "narrative_halflife_h", 72.0, (24.0, 48.0, 72.0, 168.0), "hours",
        "attention decays; the half-life says how long a story is still a tradable state"),
    "narrative_decay_floor": Prior(
        "narrative_decay_floor", 5.0, (1.0, 5.0, 15.0), "% of peak velocity",
        "below this a narrative is over rather than quiet"),
    "calibration_slope": Prior(
        "calibration_slope", 1.18, (1.0, 1.10, 1.18, 1.35), "logit slope",
        "the favourite/longshot correction; fitted per category rather than assumed"),
    "llm_probability_delta": Prior(
        "llm_probability_delta", 0.10, (0.02, 0.05, 0.10), "absolute probability",
        "the cap on what a reasoning seat may move a posterior by; never capital authority"),
}


# --------------------------------------------------------------------------- the sensor contract
@dataclass(frozen=True)
class Reading:
    """One sensor leg: a value, or UNMEASURED with the path it wanted named."""

    name: str
    verdict: str
    value: float | None = None
    at: str = ""
    path: str = ""
    why: str = ""

    @property
    def measured(self) -> bool:
        return self.verdict == "MEASURED"

    def as_row(self) -> dict[str, Any]:
        return {"sensor": self.name, "verdict": self.verdict, "value": self.value,
                "at": self.at, "path": self.path, "why": self.why}


#: THE SENSOR CONTRACT. `shadow_institutional` is the module that OWNS these readers when it
#: exists (funding / OI / liquidation / options). It is not on this tree, so the contract is
#: declared here and satisfied from `data/axes/crypto_<leg>.json` when such a file appears.
#: Reading order is: the other builder's module first (never re-implemented), then the axis file,
#: then UNMEASURED. Absence resolves to UNMEASURED, never to zero and never to "no crowding".
SENSOR_LEGS: dict[str, str] = {
    "funding_level": "current funding rate across venues, as a percentile of its own history",
    "funding_acceleration": "change in funding level over the last k readings",
    "funding_persistence": "consecutive readings on the same side of the threshold",
    "funding_dispersion": "cross-venue spread of the funding rate: agreement vs one venue",
    "oi_level": "aggregate open interest, as a percentile of its own history",
    "oi_acceleration": "change in open interest over the same window",
    "basis": "perp/spot or futures/spot basis",
    "liquidation_state": "liquidation notional over the trailing window",
    "spot_perp_divergence": "spot leading perp or the reverse",
    "options_state": "dealer gamma / skew state where an options surface is readable",
    "book_depth": "resting depth within a band of mid, for the forced-flow family",
    "cross_venue_sync": "how synchronised a liquidation burst is across venues",
}


def _axis_path(leg: str) -> Path:
    return AXES / f"crypto_{leg}.json"


def sensor(leg: str, *, axes_dir: Path | None = None) -> Reading:
    """One leg of the crowding/forced-flow sensor bank, from whoever owns it.

    REUSED, NEVER RE-IMPLEMENTED. If `shadow_institutional` is importable its reader wins: two
    implementations of one funding series is how two organs end up disagreeing about the same
    market at the same minute. When it is absent -- which it is on this box today -- the axis
    file is read, and when that is absent too the leg is UNMEASURED with its path named.
    """
    try:                                                        # pragma: no cover - other builder
        import shadow_institutional as si
        fn = getattr(si, "read_sensor", None) or getattr(si, "sensor", None)
        if callable(fn):
            got = fn(leg)
            if isinstance(got, Mapping) and got.get("value") is not None:
                return Reading(leg, "MEASURED", float(got["value"]), str(got.get("at") or ""),
                               "shadow_institutional", "the sensor module owns this leg")
    except Exception:
        pass
    p = (axes_dir or AXES) / f"crypto_{leg}.json"
    try:
        doc = json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return Reading(leg, UNMEASURED, None, "", str(p),
                       f"no reader and no axis file: {SENSOR_LEGS.get(leg, leg)} is unknown on "
                       "this box, which is a verdict and not a zero")
    val = doc.get("value") if isinstance(doc, dict) else None
    if val is None:
        return Reading(leg, UNMEASURED, None, "", str(p), "axis file carries no value field")
    return Reading(leg, "MEASURED", float(val), str(doc.get("at") or ""), str(p), "axis file")


def sensor_bank(*, axes_dir: Path | None = None) -> dict[str, Reading]:
    return {leg: sensor(leg, axes_dir=axes_dir) for leg in SENSOR_LEGS}


# --------------------------------------------------------------------------- discovery plumbing
def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(payload, indent=1, sort_keys=False, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


@dataclass
class Run:
    """One pass: the connection, the budget, the context, and everything it recorded."""

    dry_run: bool = False
    budget_s: float = 300.0
    started: float = field(default_factory=time.monotonic)
    conn: Any = None
    ctx: TM.Context | None = None
    sensors: dict[str, Reading] = field(default_factory=dict)
    discoveries: list[dict[str, Any]] = field(default_factory=list)
    blocked: list[dict[str, Any]] = field(default_factory=list)
    notes: list[dict[str, Any]] = field(default_factory=list)

    @property
    def left(self) -> float:
        return max(0.0, self.budget_s - (time.monotonic() - self.started))

    def note(self, where: str, why: str) -> None:
        self.notes.append({"where": where, "why": why})

    def missing(self, legs: Iterable[str]) -> list[str]:
        return [leg for leg in legs if not self.sensors.get(leg, sensor(leg)).measured]


def _context(run: Run) -> TM.Context:
    """ONE miner context per pass, restricted to the MT5 targets. Never an equity: the two-lane
    mandate is enforced at the instrument source, so `mine_asset_transfer` cannot reach one."""
    if run.ctx is not None:
        return run.ctx
    inst: dict[str, list[str]] = {}
    for sym, klass in TARGET_CLASS.items():
        inst.setdefault(klass, []).append(sym)
    lane = None
    try:
        from research.universe_policy import may_hypothesise
        lane = may_hypothesise
    except Exception:
        lane = None
    run.ctx = TM.Context(
        instruments=inst, families=frozenset(), defaults={}, ontology=dict(TM.CONTRACTS),
        macro_states={}, bars_available=lambda s, c: (UNIVERSE / f"{s}_{c.upper()}.parquet"
                                                      ).exists(),
        lane_ok=lane, max_per_miner=3)
    return run.ctx


def record(run: Run, *, generator: str, spec: Mapping[str, Any], mechanism: str,
           source_id: str, source_type: str = "source_civilization",
           parents: Sequence[str] = ()) -> str | None:
    """One discovery row, origin EXTERNAL, generator `l1vsun:<family>` or its sibling.

    A dry run mints the id locally and writes NOTHING, so the plan is inspectable without a
    registry side effect -- the same contract every other organ on this desk keeps.
    """
    payload = {**dict(spec), "recorded_at": _now()}
    row = {"generator": generator, "mechanism": mechanism[:400], "spec": payload,
           "parents": list(parents)}
    if run.dry_run:
        row["discovery_id"] = f"dry:{generator}:{len(run.discoveries)}"
        run.discoveries.append(row)
        return str(row["discovery_id"])
    did, created = R.record_discovery(
        source_id=source_id, source_type=source_type, mechanism=mechanism[:400],
        origin="EXTERNAL", generator=generator,
        assets=list(spec.get("assets") or ([spec["symbol"]] if spec.get("symbol") else [])),
        sessions=[spec.get("session") or "all"], horizons=[spec.get("chart") or "H1"],
        regimes=[spec.get("regime") or ""], information=str(spec.get("information") or ""),
        economic_rationale=str(spec.get("why") or "")[:800],
        exact_rule_if_known=str(spec.get("exact_rule") or ""),
        required_data=list(spec.get("required_data") or []),
        falsifier=str(spec.get("falsifier") or ""), novelty=spec.get("novelty"),
        confidence=spec.get("confidence"), parent_discovery_ids=list(parents),
        payload=payload, conn=run.conn)
    row["discovery_id"], row["created"] = did, created
    run.discoveries.append(row)
    return did


def expand(run: Run, parent_id: str, spec: Mapping[str, Any], generator: str) -> list[str]:
    """The twelve transformation miners on this parent; each surviving child is its own discovery.

    THE DESCENDANTS ARE THE POINT. A published claim about one instrument is one cell; the same
    constrained participant acting on the desk's other six targets, one chart slower, in the
    adjacent session and with the sign flipped where the ontology says the mechanism is symmetric
    is the part nobody tests -- and the part with the information gain left in it.
    """
    ctx = _context(run)
    parent = {**dict(spec), "discovery_id": parent_id}
    kids: list[str] = []
    for miner, rows in TM.run_all(parent, ctx).items():
        for child in rows:
            sym = str(child.get("symbol") or "")
            need = list(spec.get("required_data") or [])
            gaps = run.missing(need)
            cid = record(run, generator=f"{generator}:{miner}", spec={**child, "assets": [sym]},
                         mechanism=f"{spec.get('mechanism_id')} via {miner}: {child.get('why')}",
                         source_id=f"civ:{generator}", parents=[parent_id])
            if cid is None:
                continue
            kids.append(cid)
            if gaps and not run.dry_run:
                R.set_discovery_state(cid, "BLOCKED",
                                      reason=f"sensor legs UNMEASURED on this box: {gaps}",
                                      conn=run.conn)
                run.blocked.append({"discovery_id": cid, "legs": gaps})
    if not run.dry_run:
        R.set_discovery_state(parent_id, "EXPANDED", possible_cells=len(kids),
                              generated_cells=len(kids),
                              blocked_cells=sum(1 for b in run.blocked
                                                if b["discovery_id"] in kids), conn=run.conn)
    return kids


# ===================================================== L1VSUN 1: derivatives crowding ecology
#: THE TWELVE LEGS the family crosses. Not a feature list: each is a different constrained
#: participant, and the hypothesis is that the constraints COMPOUND -- a crowded book that is also
#: paying to stay crowded, in a thinning venue, into an options wall, in the session where the
#: marginal holder is asleep.
CROWDING_LEGS: tuple[str, ...] = (
    "funding_level", "funding_acceleration", "funding_persistence", "funding_dispersion",
    "oi_level", "oi_acceleration", "basis", "liquidation_state", "spot_perp_divergence",
    "options_state")


def family_funding_ecology(run: Run) -> list[str]:
    """Crowding in the derivative book as a STATE SENSOR for the desk's risk-on/risk-off targets.

    The mechanism is not "crypto goes up". It is that leveraged crowding is a measurable inventory
    somebody must eventually unwind, and the unwind is a risk event that reprices haven and
    risk-asset legs together. The published rule -- funding above the 35th percentile for three
    readings -- enters as two priors on a ladder, crossed with the session and the volatility
    regime, so eleven of the twelve legs are conditioners rather than a single trigger.
    """
    out: list[str] = []
    pct = PRIORS["funding_percentile"]
    runs = PRIORS["funding_readings"]
    for sym in TARGETS:
        side = "follow" if sym in RISK_ON else "revert"
        for p in pct.rungs():
            for k in runs.rungs():
                if run.left <= 0:
                    run.note("funding_ecology", "budget exhausted mid-ladder; the remaining rungs "
                                                "are owed, not refused")
                    return out
                spec = {
                    "symbol": sym, "asset_class": TARGET_CLASS[sym], "chart": "H1",
                    "session": "all", "regime": "", "information": "positioning",
                    "mechanism_id": "positioning_crowding",
                    "economic_actor": "crowded_speculator", "side": side,
                    "family": "", "params": {"funding_percentile": p, "funding_readings": k,
                                             "conditioners": list(CROWDING_LEGS)},
                    "assets": [sym], "required_data": list(CROWDING_LEGS),
                    "novelty": 0.6, "confidence": 0.35,
                    "exact_rule": (f"when the cross-venue funding level sits above its {p:.0f}th "
                                   f"percentile for {k:.0f} consecutive readings AND open "
                                   "interest is rising, take the crowding state as a conditioner "
                                   f"on {sym}"),
                    "falsifier": (f"{sym} forward returns do not separate between the crowded and "
                                  "uncrowded states at any rung of the ladder, at any horizon, "
                                  "once the round trip is charged"),
                    "why": ("a crowded leveraged book is an inventory somebody must unwind; the "
                            "unwind is a risk event and it reprices haven and risk legs together, "
                            f"so the crowding reading is a sensor for {sym} and never a trade in "
                            "the venue it was read from"),
                }
                did = record(run, generator="l1vsun:funding_ecology", spec=spec,
                             mechanism="derivatives crowding ecology as an MT5 state sensor",
                             source_id="civ:l1vsun:funding_ecology")
                if did is None:
                    continue
                out.append(did)
                if p == pct.published and k == runs.published:
                    out.extend(expand(run, did, spec, "l1vsun:funding_ecology"))
    return out


# ===================================================== L1VSUN 2: liquidation / forced-flow ecology
#: THREE POPULATIONS, and the published version only has one. A forced sale into a thin book
#: continues, or it reverses, or it reverses LATE -- and which of the three happens is decided by
#: whether the open interest was destroyed, whether the depth came back, and how synchronised the
#: burst was. Minting all three is what makes this a measurement instead of a directional opinion.
FORCED_POPULATIONS: tuple[tuple[str, str, str], ...] = (
    ("continuation", "follow",
     "the liquidation destroyed open interest and the book did not refill: the flow that moved "
     "the price is still there and the move extends"),
    ("reversal", "revert",
     "the liquidation was a price-insensitive seller into a book that refilled within the window: "
     "the taker moved the price alone and has to give it back"),
    ("delayed_reversal", "revert",
     "the book refilled only after the burst ended, so the give-back starts one window late -- "
     "which is why an instant fade loses and a delayed one does not"),
)
FORCED_LEGS: tuple[str, ...] = ("liquidation_state", "oi_acceleration", "book_depth",
                                "cross_venue_sync", "funding_level")


def family_forced_flow(run: Run) -> list[str]:
    """Abnormal forced flow into depleted depth: three populations, conditioned six ways.

    The prior the world published is "three times the six-hour median". Both halves of that are
    fitted -- the multiple AND the window -- so both are ladders here, and the population
    (continuation / reversal / delayed reversal) is conditioned on OI destruction, depth recovery,
    spread, funding, cross-venue synchronisation, the session and the volatility regime.
    """
    out: list[str] = []
    mult, win = PRIORS["liquidation_multiple"], PRIORS["liquidation_window_h"]
    for sym in TARGETS:
        for pop, side, story in FORCED_POPULATIONS:
            for m in mult.rungs():
                if run.left <= 0:
                    run.note("forced_flow", "budget exhausted; remaining rungs owed")
                    return out
                spec = {
                    "symbol": sym, "asset_class": TARGET_CLASS[sym], "chart": "M15",
                    "session": "all", "regime": "high_vol", "information": "positioning",
                    "mechanism_id": "forced_liquidation",
                    "economic_actor": "margin_called_trader", "side": side, "family": "",
                    "params": {"liquidation_multiple": m, "window_h": win.published,
                               "population": pop, "conditioners": list(FORCED_LEGS)},
                    "assets": [sym], "required_data": list(FORCED_LEGS),
                    "novelty": 0.65, "confidence": 0.3,
                    "exact_rule": (f"liquidation notional above {m:g}x the trailing "
                                   f"{win.published:g}h median, conditioned on the {pop} "
                                   f"population's state, read as a {side} conditioner on {sym}"),
                    "falsifier": (f"the three populations do not separate {sym}'s forward return "
                                  "distribution at any multiple or window: the forced flow is "
                                  "noise dressed as a mechanism"),
                    "why": story,
                }
                did = record(run, generator="l1vsun:forced_flow", spec=spec,
                             mechanism=f"forced-flow ecology, {pop} population",
                             source_id="civ:l1vsun:forced_flow")
                if did is None:
                    continue
                out.append(did)
                if m == mult.published and pop == "delayed_reversal":
                    out.extend(expand(run, did, spec, "l1vsun:forced_flow"))
    return out


# ===================================================== L1VSUN 3: narrative lifecycle
NARRATIVE_STAGES: tuple[str, ...] = (
    "birth", "velocity", "acceleration", "cross_platform_diffusion", "geographic_diffusion",
    "saturation", "price_confirmation", "price_disagreement", "peak", "half_life", "decay",
    "resurrection")


def narrative_state(claims: Sequence[Mapping[str, Any]], *, now: datetime | None = None,
                    saturation_pct: float | None = None, halflife_h: float | None = None,
                    active_sources: int | None = None) -> dict[str, Any]:
    """Where a story is in its life, from the claims the moat already captured.

    Velocity is claims per hour; acceleration is its change; cross-platform diffusion is the count
    of DISTINCT sources carrying it and geographic diffusion the count of distinct languages --
    both of which matter more than volume, because one source posting forty times is one source.
    Saturation is the share of the active source population carrying it, which is the honest read
    of "everybody already knows".
    """
    at = now or datetime.now(tz=UTC)
    sat = float(saturation_pct if saturation_pct is not None
                else PRIORS["narrative_saturation"].published)
    hl = float(halflife_h if halflife_h is not None else PRIORS["narrative_halflife_h"].published)
    stamps: list[datetime] = []
    sources: set[str] = set()
    langs: set[str] = set()
    for c in claims:
        try:
            stamps.append(datetime.fromisoformat(str(c.get("created_at") or c.get("at"))))
        except (TypeError, ValueError):
            continue
        sources.add(str(c.get("source_id") or ""))
        langs.add(str(c.get("language") or ""))
    if not stamps:
        return {"verdict": UNMEASURED, "why": "no timestamped claim carries this topic",
                "stage": UNMEASURED}
    stamps.sort()
    stamps = [s if s.tzinfo else s.replace(tzinfo=UTC) for s in stamps]
    age_h = max((at - stamps[0]).total_seconds() / 3600.0, 1e-6)
    recent = [s for s in stamps if (at - s) <= timedelta(hours=hl)]
    prior = [s for s in stamps if timedelta(hours=hl) < (at - s) <= timedelta(hours=2 * hl)]
    v_now = len(recent) / hl
    v_prev = len(prior) / hl
    accel = v_now - v_prev
    peak_v = max(v_now, v_prev, len(stamps) / age_h)
    decay_floor = PRIORS["narrative_decay_floor"].published / 100.0
    if v_now <= peak_v * decay_floor and prior:
        stage = "resurrection" if v_now > v_prev else "decay"
    # SATURATION IS A SHARE OF THE ACTIVE SOURCE POPULATION, and without that denominator it is
    # UNMEASURED -- not "not saturated". Comparing the carriers to themselves would make every
    # story saturated the moment two sources printed it, which is the shape of a metric that
    # always fires and therefore says nothing.
    share = None if not active_sources else len(sources) / float(active_sources)
    if accel > 0 and len(stamps) <= 3:
        stage = "birth"
    elif accel > 0:
        stage = "acceleration"
    elif share is not None and share * 100.0 >= sat and accel <= 0:
        stage = "saturation"
    else:
        stage = "velocity"
    return {"verdict": "MEASURED", "stage": stage, "n_claims": len(stamps),
            "velocity_per_h": v_now, "prior_velocity_per_h": v_prev, "acceleration": accel,
            "cross_platform_diffusion": len(sources), "geographic_diffusion": len(langs),
            "saturation_share": share if share is not None else UNMEASURED,
            "age_h": age_h, "saturation_prior_pct": sat, "halflife_prior_h": hl,
            "stages": list(NARRATIVE_STAGES)}


def _claims_for(run: Run, instrument: str, limit: int = 400) -> list[dict[str, Any]]:
    if run.conn is None:
        return []
    try:
        cur = run.conn.execute(
            "SELECT claim_id, source_id, created_at, language, instruments_json, text "
            "FROM claims ORDER BY created_at DESC LIMIT ?", (limit * 4,))
        rows = [dict(r) for r in cur.fetchall()]
    except Exception:
        return []
    out = []
    for r in rows:
        blob = f"{r.get('instruments_json') or ''} {r.get('text') or ''}".upper()
        if instrument.upper() in blob:
            out.append(r)
        if len(out) >= limit:
            break
    return out


def _active_sources(run: Run) -> int | None:
    """How many DISTINCT sources have printed anything lately -- the saturation denominator."""
    if run.conn is None:
        return None
    try:
        row = run.conn.execute("SELECT COUNT(DISTINCT source_id) AS n FROM claims").fetchone()
        return int(row["n"]) or None
    except Exception:
        return None


def family_narrative(run: Run) -> list[str]:
    """The attention lifecycle as a conditioner: a saturated story is a different trade.

    NOT A SENTIMENT SCORE. The claim is about WHERE IN THE LIFECYCLE the story is: a narrative
    still diffusing across platforms has marginal buyers left, and one that has saturated has
    only holders. Price confirmation and price DISAGREEMENT are both minted, because the case
    where attention rises and price does not is the one with information in it.
    """
    out: list[str] = []
    for sym in TARGETS:
        claims = _claims_for(run, sym)
        state = narrative_state(claims, active_sources=_active_sources(run))
        for stage in ("saturation", "price_disagreement", "resurrection"):
            spec = {
                "symbol": sym, "asset_class": TARGET_CLASS[sym], "chart": "H4",
                "session": "all", "regime": "", "information": "event",
                "mechanism_id": "regime_transition", "economic_actor": "stale_regime_positioner",
                "side": "revert" if stage == "saturation" else "follow", "family": "",
                "params": {"narrative_stage": stage,
                           "saturation_pct": PRIORS["narrative_saturation"].published,
                           "halflife_h": PRIORS["narrative_halflife_h"].published,
                           "decay_floor_pct": PRIORS["narrative_decay_floor"].published},
                "assets": [sym], "required_data": ["claims_store"],
                "novelty": 0.55, "confidence": 0.3,
                "exact_rule": (f"when the {sym} narrative is in the {stage} stage of "
                               f"{list(NARRATIVE_STAGES)}, condition the sleeve on it"),
                "falsifier": (f"{sym} forward returns are indistinguishable across lifecycle "
                              "stages, at every saturation and half-life rung"),
                "why": ("attention has a lifecycle and the marginal buyer is spent at the end of "
                        "it; the stage is a conditioner on an MT5 instrument, never a claim about "
                        "the platform the claims were read from"),
                "measured_state": state,
            }
            did = record(run, generator="l1vsun:narrative", spec=spec,
                         mechanism=f"narrative lifecycle: {stage}",
                         source_id="civ:l1vsun:narrative")
            if did is None:
                continue
            out.append(did)
            if stage == "saturation":
                out.extend(expand(run, did, spec, "l1vsun:narrative"))
        if state["verdict"] == UNMEASURED:
            run.note("narrative", f"{sym}: {state['why']}")
    return out


# ===================================================== L1VSUN 4: thesis / event staleness clocks
def _calendar_events(path: Path | None = None) -> list[dict[str, Any]]:
    doc = _read_json(path or CALENDAR)
    rows = doc.get("events") if isinstance(doc, dict) else doc
    return [r for r in (rows or []) if isinstance(r, dict)]


def next_catalyst(symbol: str, events: Sequence[Mapping[str, Any]],
                  now: datetime) -> dict[str, Any]:
    """The nearest scheduled event whose window this instrument sits inside.

    Matched on the event's own name and kind rather than a symbol list: a `central_bank` row or a
    `fixing` row is a catalyst for every instrument in the affected class, and a symbol list
    somebody maintains by hand is a list that rots.
    """
    sym = symbol.upper()
    best: tuple[float, Mapping[str, Any]] | None = None
    for e in events:
        raw = str(e.get("window_start_utc") or e.get("date") or "")
        try:
            when = datetime.fromisoformat(raw)
        except ValueError:
            continue
        when = when if when.tzinfo else when.replace(tzinfo=UTC)
        if when < now:
            continue
        blob = f"{e.get('name') or ''} {e.get('kind') or ''}".upper()
        kind = str(e.get("kind") or "")
        relevant = (sym in blob or sym[:3] in blob or sym[3:6] in blob
                    or kind in ("central_bank", "month_end", "quarter_end", "option_expiry",
                                "index_rebalance"))
        if not relevant:
            continue
        hours = (when - now).total_seconds() / 3600.0
        if best is None or hours < best[0]:
            best = (hours, e)
    if best is None:
        return {"verdict": UNMEASURED, "why": "no future calendar row matches this instrument"}
    hours, e = best
    return {"verdict": "MEASURED", "hours_away": hours, "kind": str(e.get("kind") or ""),
            "name": str(e.get("name") or ""), "at": str(e.get("window_start_utc")
                                                        or e.get("date") or "")}


def thesis_clocks(*, now: datetime | None = None, sleeves_path: Path | None = None,
                  shadow_path: Path | None = None, calendar_path: Path | None = None
                  ) -> dict[str, Any]:
    """Every enrolled forward candidate and every live sleeve gets a STALENESS AGE.

    NEVER A STANDALONE TRADE, and the artifact says so in its own body. A thesis clock does not
    enter, exit, size or veto anything: it publishes how long it has been since the reasoning
    behind a position was last examined, and how close the next scheduled catalyst is. The use is
    a reading list, not a signal -- a sleeve whose thesis was last refreshed forty days ago and
    whose catalyst is in six hours is the one a session should look at first.
    """
    at = now or datetime.now(tz=UTC)
    events = _calendar_events(calendar_path)
    rows: dict[str, dict[str, Any]] = {}
    doc = _read_json(sleeves_path or SLEEVES)
    sleeves = doc.get("sleeves") if isinstance(doc, dict) else doc
    for s in (sleeves or []):
        if not isinstance(s, dict) or not s.get("name"):
            continue
        sym = str(s.get("symbol") or "")
        rows[f"sleeve:{s['name']}"] = {
            "kind": "live_sleeve", "symbol": sym, "family": str(s.get("family") or ""),
            "status": str(s.get("status") or ""), "next_catalyst": next_catalyst(sym, events, at),
            "thesis_refreshed_at": str(s.get("thesis_refreshed_at") or "") or UNMEASURED,
            "expected_event_sensitivity": _event_sensitivity(str(s.get("family") or "")),
        }
    shadow = _read_json(shadow_path or SHADOW_STATE)
    for key, row in (shadow or {}).items():
        if not isinstance(row, dict):
            continue
        sym = str(key).split(".")[0]
        rows[f"clock:{key}"] = {
            "kind": "enrolled_clock", "symbol": sym, "family": str(row.get("family") or ""),
            "status": str(row.get("status") or ""), "n": row.get("n"),
            "next_catalyst": next_catalyst(sym, events, at),
            "thesis_refreshed_at": str(row.get("first_entry") or "") or UNMEASURED,
            "expected_event_sensitivity": _event_sensitivity(str(row.get("family") or "")),
        }
    for key, row in rows.items():
        refreshed = row.get("thesis_refreshed_at")
        age = UNMEASURED
        if isinstance(refreshed, str) and refreshed != UNMEASURED:
            try:
                d = datetime.fromisoformat(refreshed)
                d = d if d.tzinfo else d.replace(tzinfo=UTC)
                age = round((at - d).total_seconds() / 86400.0, 2)
            except ValueError:
                age = UNMEASURED
        row["thesis_age_days"] = age
        cat = row["next_catalyst"]
        row["model_still_applies"] = (
            UNMEASURED if age == UNMEASURED
            else bool(float(age) <= 30.0 and (cat.get("verdict") != "MEASURED"
                                              or float(cat.get("hours_away", 1e9)) > 12.0)))
        row["key"] = key
    return {"generated_at": at.isoformat(timespec="seconds"), "n": len(rows),
            "tradeable": False,
            "rule": "a thesis clock is a reading list, never a trade: it never enters, exits, "
                    "sizes or vetoes anything",
            "unmeasured_refresh": sum(1 for r in rows.values()
                                      if r["thesis_age_days"] == UNMEASURED),
            "clocks": rows}


_EVENT_SENSITIVE = ("macro", "gap", "news", "breakout", "session", "carry", "overnight")


def _event_sensitivity(family: str) -> str:
    f = family.lower()
    if not f:
        return UNMEASURED
    return "high" if any(k in f for k in _EVENT_SENSITIVE) else "low"


# ===================================================== L1VSUN 5 + 6: verification and discipline
def family_evidence_verification(run: Run) -> dict[str, Any]:
    """Delegated WHOLE to `evidence_watchtower`. One verifier, or two that disagree."""
    try:
        from research import evidence_watchtower as ew
    except Exception as exc:
        return {"verdict": UNMEASURED, "why": f"evidence_watchtower not importable: {exc}",
                "delegated_to": "desks/mt5/research/evidence_watchtower.py"}
    objects = [{"object_id": f"target:{s}", "kind": "dataset",
                "path": str(UNIVERSE / f"{s}_H1.parquet")} for s in TARGETS]
    try:
        transitions = ew.watch(objects, dry_run=run.dry_run)
    except Exception as exc:
        return {"verdict": UNMEASURED, "why": f"watch raised {type(exc).__name__}: {exc}"}
    return {"verdict": "MEASURED", "delegated_to": "evidence_watchtower.watch",
            "objects": len(objects), "transitions": len(transitions),
            "false_transition": ew.false_transition_rate()}


#: THE SPECIALIST PIPELINE, as a checklist of where each discipline is ALREADY ENFORCED here.
#: Published rather than re-implemented: a sixth copy of "verify before you execute" helps nobody,
#: and naming the enforcing file makes the claim falsifiable -- delete the file and the row lies.
SPECIALIST_DISCIPLINE: tuple[dict[str, str], ...] = (
    {"discipline": "role_separation",
     "enforced_by": "desks/mt5/research/wiring_ceo.py + the department locks under data/locks/",
     "how": "generation, judging and allocation are separate organs on separate clocks; no organ "
            "grades its own output (the compiler never sets TESTED)"},
    {"discipline": "second_source_verification",
     "enforced_by": "desks/mt5/research/evidence_watchtower.py",
     "how": "a claim needs a direct observable check AND a second source agreeing before it can "
            "become a candidate; disagreement resolves to UNRESOLVED, never to the nicer source"},
    {"discipline": "explicit_candidate_identity",
     "enforced_by": "libs/moat/registry.py content_hash + desks/mt5/research/shadow_admission",
     "how": "a candidate is (family, symbol, params, chart, session, regime, horizon); a lost "
            "parameter is UNRECONSTRUCTIBLE and is never guessed from a display name"},
    {"discipline": "falsification_before_execution",
     "enforced_by": "docs/UNIVERSAL_PROMOTION_PROTOCOL.md + external_gauntlet's ten gates",
     "how": "every discovery declares a falsifier at record time; the ten gates are the only "
            "promotion path and they run before capital, never after"},
    {"discipline": "single_execution_authority",
     "enforced_by": "desks/mt5/mt5desk/gateway.py",
     "how": "one process places orders; research organs write artifacts and the gateway reads "
            "them, so no miner can reach the account"},
    {"discipline": "permanent_failed_idea_log",
     "enforced_by": "desks/mt5/data/graveyard.json + the immutable trials_ledger",
     "how": "a killed cell keeps its failure class for ever and re-opening needs a NAMED enabling "
            "change addressing the cause of death (L1.16a)"},
)


# ===================================================== BL888M 4: counterfactual gate attribution
#: The gates on the promotion/enrolment path, in the order a candidate meets them.
PROMOTION_GATES: tuple[str, ...] = (
    "economic_prior", "in_sample_screen", "deflated_sharpe", "pbo", "reality_check_spa", "cpcv",
    "walk_forward", "cost_stress", "capacity", "forward_window")


def _forward_returns(shadow: Mapping[str, Any]) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {}
    for key, row in shadow.items():
        if not isinstance(row, dict):
            continue
        series = row.get("r_series") or row.get("returns") or row.get("r")
        if isinstance(series, list) and series:
            vals = [float(v) for v in series if isinstance(v, (int, float))]
            if vals:
                out[str(key)] = vals
        elif isinstance(row.get("cum_r"), (int, float)) and isinstance(row.get("n"), int) \
                and int(row["n"]) > 0:
            out[str(key)] = [float(row["cum_r"]) / float(row["n"])] * int(row["n"])
    return out


def _elog(rets: Sequence[float], fraction: float = 0.02) -> float | None:
    """E[log(1 + f R)] on a forward R series, at a small fixed fraction.

    The fraction is fixed and small ON PURPOSE: this measures what a GATE contributed, not what a
    sizing rule contributed, and letting the fraction vary would fold the allocator's decision
    into the gate's attribution.
    """
    arr = np.asarray([r for r in rets if math.isfinite(float(r))], dtype=float)
    if arr.size == 0:
        return None
    w = 1.0 + fraction * arr
    if np.any(w <= 0):
        return None
    return float(np.mean(np.log(w)))


def gate_attribution(*, shadow_path: Path | None = None, ledger_path: Path | None = None,
                     reconcile_path: Path | None = None, max_rows: int = 200_000
                     ) -> dict[str, Any]:
    """For every gate: E[log W] WITH it minus E[log W] WITHOUT it, on the forward record.

    THE COUNTERFACTUAL IS USUALLY UNAVAILABLE, AND THAT IS THE FINDING. A cell that fails
    `deflated_sharpe` is never enrolled, so it has no forward R series, so the "without the gate"
    arm is empty and the honest answer is UNMEASURED BY NAME -- not zero, and not "the gate is
    worth nothing". Where the record DOES carry both arms (a gate that some enrolled clock failed
    and was enrolled anyway, which the grandfathered hunt6 sleeves produced), the difference is
    real and is reported.

    This is the only way a desk learns whether a gate is paying for itself. A gate that has never
    had a measurable counterfactual is a gate nobody can defend on evidence, which is a different
    problem from a gate that is measurably bad -- and the report separates them.
    """
    shadow = _read_json(shadow_path or SHADOW_STATE) or {}
    reconcile = _read_json(reconcile_path or FORWARD_RECONCILE) or {}
    series = _forward_returns(shadow if isinstance(shadow, dict) else {})
    verdicts: dict[str, dict[str, bool]] = {}
    lp = ledger_path or GATE_LEDGER
    if lp.exists():
        with lp.open("r", encoding="utf-8", errors="replace") as fh:
            for i, line in enumerate(fh):
                if i >= max_rows:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(row, dict):
                    continue
                cell = str(row.get("cell") or "")
                gates = row.get("gates")
                if isinstance(gates, dict):
                    verdicts.setdefault(cell, {}).update(
                        {str(g): bool(v.get("passed")) for g, v in gates.items()
                         if isinstance(v, dict)})
                elif row.get("terminal_gate"):
                    verdicts.setdefault(cell, {})[str(row["terminal_gate"])] = bool(
                        row.get("passed"))
    out: dict[str, Any] = {}
    for gate in PROMOTION_GATES:
        with_arm: list[float] = []
        without_arm: list[float] = []
        for key, rets in series.items():
            passed = None
            for cell, gv in verdicts.items():
                if key.split(".")[0] and key.split(".")[0] in cell and gate in gv:
                    passed = gv[gate]
                    break
            if passed is True:
                with_arm.extend(rets)
            elif passed is False:
                without_arm.extend(rets)
        e_with, e_without = _elog(with_arm), _elog(without_arm)
        if e_with is None or e_without is None:
            out[gate] = {
                "verdict": UNMEASURED,
                "n_with": len(with_arm), "n_without": len(without_arm),
                "why": ("the counterfactual arm is empty: a cell this gate refused was never "
                        "enrolled, so no forward record of it exists. The gate's contribution is "
                        "UNMEASURED, which is not zero and not a licence to remove it")}
        else:
            out[gate] = {"verdict": "MEASURED", "elog_with": e_with, "elog_without": e_without,
                         "delta_elog": e_with - e_without, "n_with": len(with_arm),
                         "n_without": len(without_arm),
                         "pays_for_itself": bool(e_with > e_without)}
    measured = [g for g, r in out.items() if r["verdict"] == "MEASURED"]
    return {"generated_at": _now(), "fraction": 0.02, "gates": out,
            "n_forward_series": len(series), "n_cells_with_verdicts": len(verdicts),
            "measured_gates": measured, "unmeasured_gates": [g for g in out if g not in measured],
            "enrolled_reported": reconcile.get("enrolled"),
            "rule": "Elog(with gate) - Elog(without) on the forward record where both arms exist; "
                    "UNMEASURED BY NAME otherwise, never zero"}


# ===================================================== BL888M 5: bounded LLM contribution
#: The policy. A reasoning seat may move a PROBABILITY and nothing else, by at most this much, and
#: it may never name a size. Not a style preference: a seat that can write a size field has
#: capital authority through the back door, and the ONE execution authority law says it must not.
LLM_CONTRIBUTION: dict[str, Any] = {
    "max_probability_delta": PRIORS["llm_probability_delta"].published,
    "capital_authority": False,
    "may_write": ("probability_delta", "mechanism", "falsifier", "why", "symbols", "family",
                  "params", "required_data", "confidence"),
    "forbidden_fields": ("size", "lot", "lots", "volume", "risk_frac", "risk_fraction", "capital",
                         "heat", "fraction", "leverage", "notional", "units", "position_size",
                         "allocation", "weight"),
    "rule": "a seat proposes a bounded probability delta; capital is the allocator's decision by "
            "delta E[log W], and a seat that names a size is refused, not clipped",
}


def check_seat_row(row: Mapping[str, Any]) -> tuple[bool, str]:
    """May this seat intake row be admitted? REFUSED, never quietly clipped.

    Clipping a size field to zero would admit the row and teach the seat that writing one is fine.
    Refusing it with the field named is what changes the seat's next donation.
    """
    bad = [k for k in row if str(k).lower() in LLM_CONTRIBUTION["forbidden_fields"]]
    if bad:
        return False, (f"seat rows carry no capital authority: refused for the size field(s) "
                       f"{sorted(bad)}. Propose a probability delta instead")
    delta = row.get("probability_delta")
    if delta is not None:
        try:
            d = float(delta)
        except (TypeError, ValueError):
            return False, "probability_delta is not a number"
        cap = float(LLM_CONTRIBUTION["max_probability_delta"])
        if abs(d) > cap + 1e-12:
            return False, f"probability_delta {d:+.3f} exceeds the +-{cap:.2f} bound"
    return True, "admitted: a bounded probability contribution with no capital authority"


# ===================================================== BL888M 6: smart-participant archaeology
#: THE PROVENANCE FIREWALL. An action counts as the participant's OWN only when a receipt says
#: they initiated it. Dust, airdrops, copied trades and relayed orders are somebody else's
#: decision wearing this participant's identifier, and counting them is how a "smart money"
#: cohort ends up being a measurement of an airdrop distributor.
REFUSED_PROVENANCE: tuple[str, ...] = ("dust", "airdrop", "copied", "copy_trade", "relayed",
                                       "relay", "mirrored", "sponsored", "gifted", "faucet",
                                       "internal_transfer", "wash")


def genuine(action: Mapping[str, Any]) -> tuple[bool, str]:
    """Did this participant initiate this action? A receipt says so, or the answer is no."""
    kind = str(action.get("provenance") or action.get("kind") or "").lower()
    for bad in REFUSED_PROVENANCE:
        if bad in kind:
            return False, (f"provenance {kind!r}: this is somebody else's decision attributed to "
                           "this participant; it is not evidence about their skill")
    receipt = action.get("receipt")
    if not isinstance(receipt, Mapping):
        return False, "no receipt: an action with no confirmation of who initiated it is UNKNOWN"
    if str(receipt.get("initiator") or "") != str(action.get("participant") or ""):
        return False, (f"receipt initiator {receipt.get('initiator')!r} is not the participant "
                       f"{action.get('participant')!r}")
    if not receipt.get("confirmed"):
        return False, "receipt is unconfirmed"
    return True, "receipt confirms the participant initiated this action"


def skill_posterior(returns: Sequence[float], *, market: Sequence[float] | None = None,
                    leverage: float = 1.0, copy_share: float = 0.0,
                    liquidity_share: float = 0.0, survived: bool = True,
                    survival_rate: float = 1.0) -> dict[str, Any]:
    """P(theta > 0 | this participant's forward decisions), AFTER the four free explanations.

    BETA IS NOT SKILL. A long-only account in a rising market has a positive mean and no edge, so
    the return is residualised against the market leg first and the posterior is computed on what
    is LEFT. Leverage is divided out for the same reason: it scales both mean and variance, so it
    moves the P&L and not the t-stat, and an account that looks brilliant only because it is
    levered eight times is an account with the same information as one levered once. COPIED flow
    and LIQUIDITY-PROVISION flow are discounted from the effective sample, because neither is the
    participant's own information. And SURVIVAL is the last one: we only see accounts that did not
    blow up, so an observed positive mean is conditioned on survival and the posterior is shaded
    towards zero by the survival rate of the cohort.
    """
    r = np.asarray([float(v) for v in returns if math.isfinite(float(v))], dtype=float)
    if r.size < 3:
        return {"verdict": UNMEASURED, "why": f"{r.size} decisions is not a posterior", "n": r.size}
    beta = None
    resid = r
    if market is not None:
        m = np.asarray([float(v) for v in market], dtype=float)[: r.size]
        if m.size == r.size and float(np.var(m)) > 0:
            design = np.column_stack([np.ones(m.size), m])
            coef = np.linalg.pinv(design) @ r
            beta = float(coef[1])
            resid = r - design @ coef
    lev = max(float(leverage), 1e-9)
    unlevered = resid / lev
    own_share = max(0.0, 1.0 - float(copy_share) - float(liquidity_share))
    n_eff = max(1.0, r.size * own_share)
    sd = float(np.std(unlevered, ddof=1)) if unlevered.size > 1 else 0.0
    mean = float(np.mean(unlevered))
    # A RESIDUAL THAT IS ALL BUT GONE IS NOT INFINITE CONFIDENCE. An account whose return the
    # market leg explains entirely leaves a residual of numerical dust, and dust has a tiny sd --
    # so the naive t-stat divides a rounding error by a rounding error and reports certainty.
    # There is no information left to be confident about: the posterior is 0.5 and says why.
    share = float(np.var(resid) / np.var(r)) if float(np.var(r)) > 0 else 1.0
    if share < 1e-6 or sd <= 0:
        return {"verdict": "MEASURED", "n": int(r.size), "n_effective": n_eff, "beta": beta,
                "leverage": lev, "own_share": own_share, "mean_residual": mean, "t_stat": 0.0,
                "p_skill_raw": 0.5, "p_skill": 0.5, "residual_share": share,
                "survival_rate": min(max(float(survival_rate), 1e-6), 1.0),
                "why": "the market leg explains the whole return: there is no residual to have "
                       "skill in, and a t-stat on numerical dust is not evidence",
                "controls": ["beta", "leverage", "luck(t-stat)", "copying",
                             "liquidity_provision", "survival"]}
    t = mean / (sd / math.sqrt(n_eff))
    p = 0.5 * (1.0 + math.erf(t / math.sqrt(2.0)))
    surv = min(max(float(survival_rate), 1e-6), 1.0)
    p_adj = 0.5 + (p - 0.5) * surv if survived else 0.5
    return {"verdict": "MEASURED", "n": int(r.size), "n_effective": n_eff, "beta": beta,
            "leverage": lev, "own_share": own_share, "mean_residual": mean, "t_stat": t,
            "p_skill_raw": p, "p_skill": p_adj, "survival_rate": surv,
            "residual_share": share,
            "controls": ["beta", "leverage", "luck(t-stat)", "copying", "liquidity_provision",
                         "survival"]}


def cohort_information(members: Sequence[Sequence[float]]) -> dict[str, Any]:
    """TEN CORRELATED PARTICIPANTS ARE ONE EVENT, and this is the number that says so.

    n_eff = n / (1 + (n - 1) * rho_bar) with rho_bar the mean pairwise correlation. A cohort of
    copy-traders following one leader has rho_bar near 1 and n_eff near 1, which is the correct
    reading: their agreement carries one participant's information, not ten.
    """
    rows = [np.asarray(m, dtype=float) for m in members if len(m) > 1]
    if len(rows) < 2:
        return {"verdict": UNMEASURED, "why": "fewer than two members with a usable series",
                "n": len(rows)}
    k = min(r.size for r in rows)
    mat = np.vstack([r[:k] for r in rows])
    if float(np.min(np.std(mat, axis=1))) <= 0:
        return {"verdict": UNMEASURED, "why": "a member series is constant; correlation undefined",
                "n": len(rows)}
    corr = np.corrcoef(mat)
    n = len(rows)
    off = (corr.sum() - n) / (n * (n - 1))
    rho = float(np.clip(off, -1.0 / (n - 1) + 1e-9, 1.0))
    n_eff = n / (1.0 + (n - 1) * rho) if (1.0 + (n - 1) * rho) > 0 else float(n)
    return {"verdict": "MEASURED", "n": n, "mean_pairwise_corr": rho,
            "n_effective": float(min(max(n_eff, 1.0), n)),
            "rule": "n_eff = n / (1 + (n-1) rho_bar): correlated participants carry one event"}


# ===================================================== primitive (a): Hawkes event intensity
def event_times(symbol: str, chart: str = "H1", *, sigma_k: float = 2.5,
                universe_dir: Path | None = None, max_rows: int = 20000) -> dict[str, Any]:
    """Arrival times of LARGE MOVES on an MT5 instrument, in hours since the first bar.

    Large is relative to the instrument's own volatility (|r| > k sigma), so the same k means the
    same thing on gold and on the Nasdaq. Absent bars are UNMEASURED with the path named.
    """
    p = (universe_dir or UNIVERSE) / f"{symbol}_{chart.upper()}.parquet"
    if not p.exists():
        return {"verdict": UNMEASURED, "why": "no bars on this box", "path": str(p)}
    try:
        import pandas as pd
        df = pd.read_parquet(p)
    except Exception as exc:
        return {"verdict": UNMEASURED, "why": f"{type(exc).__name__}: {exc}", "path": str(p)}
    if "close" not in df.columns or len(df) < 200:
        return {"verdict": UNMEASURED, "why": "no close column or under 200 bars", "path": str(p)}
    df = df.tail(max_rows)
    close = np.asarray(df["close"], dtype=float)
    ret = np.diff(np.log(np.maximum(close, 1e-12)))
    sd = float(np.std(ret))
    if sd <= 0:
        return {"verdict": UNMEASURED, "why": "zero volatility", "path": str(p)}
    idx = np.flatnonzero(np.abs(ret) > sigma_k * sd)
    per_hour = {"M5": 1 / 12, "M15": 0.25, "H1": 1.0, "H4": 4.0, "D1": 24.0}.get(chart.upper(), 1.0)
    return {"verdict": "MEASURED", "times": (idx * per_hour).tolist(), "n": int(idx.size),
            "sigma_k": sigma_k, "bars": int(ret.size), "path": str(p)}


def hawkes_discoveries(run: Run, *, charts: Sequence[str] = ("H1", "H4")) -> list[str]:
    """Self-exciting arrival intensity per target x horizon, as a WORLD-MODEL FEATURE.

    The branching ratio is the feature: n near 1 means the last large move raised the probability
    of the next one, which is a cascade regime and a completely different sizing problem from a
    market where n is near 0. It is fitted with `libs.models.classical_baselines.HawkesIntensity`
    -- the permanent baseline, so nobody has to trust a second implementation of the same kernel.
    """
    from libs.models.classical_baselines import HawkesIntensity
    out: list[str] = []
    for sym in TARGETS:
        for chart in charts:
            if run.left <= 0:
                run.note("hawkes", "budget exhausted before every target x horizon")
                return out
            ev = event_times(sym, chart)
            if ev["verdict"] != "MEASURED" or ev["n"] < 30:
                run.note("hawkes", f"{sym} {chart}: {ev.get('why') or 'too few arrivals'}")
                fit_state: dict[str, Any] = {"verdict": UNMEASURED,
                                             "why": ev.get("why") or f"{ev.get('n')} arrivals"}
            else:
                fit_state = dict(HawkesIntensity().fit(ev["times"]).state)
            spec = {
                "symbol": sym, "asset_class": TARGET_CLASS[sym], "chart": chart,
                "session": "all", "regime": "high_vol", "information": "microstructure",
                "mechanism_id": "volatility_shock", "economic_actor": "short_gamma_hedger",
                "side": "follow", "family": "",
                "params": {"kernel": "exponential", "sigma_k": 2.5,
                           "branching_ratio": fit_state.get("branching_ratio"),
                           "decay_halflife_h": fit_state.get("decay_halflife")},
                "assets": [sym], "required_data": [f"{sym}_{chart}.parquet"],
                "novelty": 0.7, "confidence": 0.4,
                "exact_rule": (f"fit lambda(t) = mu + sum alpha exp(-beta (t - t_i)) to |r| > "
                               f"2.5 sigma arrivals on {sym} {chart}; condition the sleeve on the "
                               "branching ratio"),
                "falsifier": (f"the fitted intensity does not beat a homogeneous Poisson clock on "
                              f"{sym} {chart}, so arrivals are independent and the feature is "
                              "noise"),
                "why": ("large moves are not independent: one print raises the intensity of the "
                        "next, and the branching ratio says how close the market is to a cascade "
                        "-- which is a sizing state, not a direction"),
                "measured_state": fit_state,
            }
            did = record(run, generator="primitive:hawkes", spec=spec,
                         mechanism="self-exciting arrival intensity as a world-model feature",
                         source_id="civ:primitive:hawkes")
            if did is None:
                continue
            out.append(did)
            if chart == "H1" and sym == "XAUUSD":
                out.extend(expand(run, did, spec, "primitive:hawkes"))
    return out


# ===================================================== primitive (c): insider classifier
def classify_insider_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """ROUTINE when this insider traded in the same calendar month in prior years, else
    OPPORTUNISTIC -- and only the OPPORTUNISTIC BREADTH leaves this function.

    THE EVENT LANE ONLY. Single names are traded on news and disclosure here (principal
    2026-09-06) and are never hunted for statistical hypotheses, so this classifier is not allowed
    to emit a per-name signal. What it emits is a BREADTH number: the share of insider
    transactions across the whole filing population that were opportunistic, which is an
    index-level state sensor for NAS100 and US500. The distinction matters because routine sales
    are a diversification schedule and carry no information at all -- mixing them in is what makes
    naive insider indicators read as noise.
    """
    by_person: dict[str, list[tuple[int, int]]] = {}
    for r in rows:
        raw = str(r.get("date") or r.get("at") or "")
        try:
            d = datetime.fromisoformat(raw)
        except ValueError:
            continue
        by_person.setdefault(f"{r.get('insider')}|{r.get('ticker')}", []).append((d.year, d.month))
    classified: list[dict[str, Any]] = []
    for r in rows:
        raw = str(r.get("date") or r.get("at") or "")
        try:
            d = datetime.fromisoformat(raw)
        except ValueError:
            continue
        key = f"{r.get('insider')}|{r.get('ticker')}"
        prior_years = {y for y, m in by_person.get(key, []) if m == d.month and y < d.year}
        label = "routine" if prior_years else "opportunistic"
        classified.append({"insider": r.get("insider"), "ticker": r.get("ticker"),
                           "date": raw, "label": label,
                           "prior_years_same_month": sorted(prior_years)})
    n = len(classified)
    if n == 0:
        return {"verdict": UNMEASURED, "why": "no parseable Form-4 rows", "n": 0,
                "index_sensor": None}
    opp = [c for c in classified if c["label"] == "opportunistic"]
    breadth = len(opp) / n
    return {"verdict": "MEASURED", "n": n, "n_opportunistic": len(opp),
            "opportunistic_breadth": breadth, "rows": classified,
            "index_sensor": {"targets": ["NAS100", "US500"], "value": breadth,
                             "lane": "event",
                             "rule": "only the CROSS-SECTIONAL opportunistic share becomes a "
                                     "state sensor for the indices; no single name is hunted"},
            "single_name_signals": []}


def family_insider_breadth(run: Run, rows: Sequence[Mapping[str, Any]] = ()) -> list[str]:
    """The opportunistic breadth as an index-level conditioner. Never a single-name hunt."""
    state = classify_insider_rows(rows)
    out: list[str] = []
    for sym in ("NAS100", "US500"):
        spec = {
            "symbol": sym, "asset_class": "indices", "chart": "D1", "session": "all",
            "regime": "", "information": "positioning", "mechanism_id": "positioning_crowding",
            "economic_actor": "crowded_speculator", "side": "follow", "family": "",
            "params": {"sensor": "opportunistic_insider_breadth"},
            "assets": [sym], "required_data": ["form4_population"],
            "novelty": 0.6, "confidence": 0.3,
            "exact_rule": ("cross-sectional share of Form-4 transactions that are opportunistic "
                           "(no same-calendar-month trade by that insider in prior years), used "
                           f"as a daily state conditioner on {sym}"),
            "falsifier": f"{sym} forward returns do not separate across the breadth distribution",
            "why": ("routine insider sales are a diversification schedule and carry no "
                    "information; the opportunistic residual is a discretionary decision by "
                    "people who see the business, and only its BREADTH is an index sensor"),
            "measured_state": {k: v for k, v in state.items() if k != "rows"},
        }
        did = record(run, generator="primitive:insider_breadth", spec=spec,
                     mechanism="opportunistic insider breadth as an index state sensor",
                     source_id="civ:primitive:insider_breadth")
        if did is not None:
            out.append(did)
    return out


# ===================================================== primitive (d): multimodal collector contract
MULTIMODAL_CONTRACT: dict[str, Any] = {
    "owner": "desks/mt5/research/moat_collectors.py",
    "media_types": ("video", "audio"),
    "sources": ("central bank press conferences", "earnings calls", "scheduled policy readouts"),
    "claim_kind": "lead_stub",
    "quantitative": False,
    "features": {"tone": "a LEAD, never evidence", "pace": "a LEAD, never evidence",
                 "pause_density": "a LEAD, never evidence"},
    "provenance": ("source_url", "knowable_at from the publisher's own stamp", "capture sha256",
                   "media_path"),
    "rule": "tone and pace are LEAD STUBS in the claims store with quantitative=false, exactly "
            "like a chart: a number read off a voice has no error bars, no vintage and no way "
            "back to a source. The collector is DECLARED here and implemented by moat_collectors "
            "when a permitted feed exists; this module fetches nothing",
    "status": UNMEASURED,
}


# ===================================================== primitive (e): cheap/expensive router
@dataclass(frozen=True)
class RoutingPolicy:
    """Who reads what. Cheap deterministic monitors by default, expensive reasoning by exception.

    The threshold is on novelty x surprise x EVIG (expected value of information gain), because
    those three are what make an item worth a reasoning seat: something nobody has seen, that
    disagrees with the current state, and whose resolution would change a decision. Volume is not
    on the list -- routing by volume is how a desk spends its whole reasoning budget on a wire
    that repeats itself.
    """

    threshold: float = 0.25
    expensive_seat: str = "expensive_reasoner"
    cheap_seat: str = "deterministic_monitor"


def route(items: Sequence[Mapping[str, Any]], policy: RoutingPolicy | None = None
          ) -> dict[str, Any]:
    """Route items, and COUNT CORRELATED MONITORS ONCE.

    THE INFORMATION-INDEPENDENCE RULE. N monitors reading one wire is ONE information event. A
    desk that counts each monitor separately believes it has N confirmations of a thing one
    journalist wrote, which is how a single headline becomes an overwhelming consensus. Items are
    grouped by their `wire`, the group's score is the MAXIMUM over its members (the best reason
    anybody had to escalate), and the group is routed once.
    """
    pol = policy or RoutingPolicy()
    groups: dict[str, list[Mapping[str, Any]]] = {}
    for it in items:
        groups.setdefault(str(it.get("wire") or it.get("source") or it.get("id") or "?"),
                          []).append(it)
    routed: list[dict[str, Any]] = []
    for wire, members in sorted(groups.items()):
        scores = [float(m.get("novelty") or 0.0) * float(m.get("surprise") or 0.0)
                  * float(m.get("evig") or 0.0) for m in members]
        best = max(scores) if scores else 0.0
        routed.append({"wire": wire, "n_monitors": len(members), "score": best,
                       "destination": pol.expensive_seat if best >= pol.threshold
                       else pol.cheap_seat,
                       "information_events": 1})
    expensive = [r for r in routed if r["destination"] == pol.expensive_seat]
    return {"threshold": pol.threshold, "n_items": len(items),
            "n_information_events": len(routed), "n_wires": len(groups),
            "routed": routed, "n_expensive": len(expensive),
            "expensive_share": (len(expensive) / len(routed)) if routed else None,
            "rule": "score = novelty x surprise x EVIG; N monitors on one wire = ONE information "
                    "event, scored by the best reason any of them had"}


# ===================================================== primitive (f): source -> paper archaeology
#: Every family names its PRIMARY LITERATURE. The transmission engine's source scout expands
#: through these: a paper's references are sources, and their references are sources, and that
#: recursion is how the desk reaches ground nobody linked to it directly. Titles and authors only
#: -- no file is fetched here, and nothing is monitored.
LITERATURE: dict[str, tuple[dict[str, str], ...]] = {
    "funding_ecology": (
        {"title": "The Basis and Carry Trade in Futures Markets", "why": "the basis IS the "
         "crowding cost, and the literature on it predates every perpetual venue"},
        {"title": "Limits of Arbitrage (Shleifer & Vishny)", "why": "why a crowded position "
         "cannot simply be arbitraged away: the arbitrageur's own funding binds first"}),
    "forced_flow": (
        {"title": "Fire Sales in Finance and Macroeconomics (Shleifer & Vishny)",
         "why": "the price-insensitive seller is the whole mechanism"},
        {"title": "Liquidity and Market Crashes / order-book resiliency literature",
         "why": "depth recovery time is what separates continuation from reversal"}),
    "narrative_lifecycle": (
        {"title": "Narrative Economics (Shiller)", "why": "stories propagate epidemiologically, "
         "which is where birth / diffusion / saturation / decay come from"},
        {"title": "Attention and Asset Prices / limited-attention literature",
         "why": "the marginal buyer is an attention-constrained participant"}),
    "hawkes": (
        {"title": "Hawkes (1971), Spectra of some self-exciting point processes",
         "why": "the kernel itself"},
        {"title": "Bacry, Mastromatteo & Muzy, Hawkes processes in finance",
         "why": "branching ratio as a market-stability reading"}),
    "insider_breadth": (
        {"title": "Cohen, Malloy & Pomorski, Decoding Inside Information",
         "why": "the routine / opportunistic split, and why only the second carries information"},),
    "prediction_markets": (
        {"title": "Wolfers & Zitzewitz, Prediction Markets",
         "why": "the price-as-probability reading and its known biases"},
        {"title": "the favourite-longshot bias literature",
         "why": "the asymmetry the calibration slope corrects"}),
    "gate_attribution": (
        {"title": "Kelly (1956) / Breiman, on log-optimal growth",
         "why": "E[log W] is the objective a gate has to pay for itself in"},),
}


def seed_source_scout(run: Run) -> dict[str, Any]:
    """Register the primary literature as CLASSIFIED `sources` rows, and walk the three seeds.

    Two halves. The literature half plants one `paper` row per reference (access PUBLIC,
    credibility RELIABLE, predictive state UNTESTED) so the transmission engine's own scout can
    follow the citation graph. The seed half walks RohOnChain, L1vsun and bl888m as NODES through
    their public work -- never their feeds -- writing a provenance edge per hop so a survivor's
    credit can walk back to the pointer that found it.
    """
    planted = 0
    for family, refs in LITERATURE.items():
        for ref in refs:
            sid = f"paper:{family}:{ref['title'][:60]}"
            planted += int(_plant_source(
                run, sid, kind="paper",
                meta={**ref, "source_id": sid, "family": family, "access_label": "PUBLIC",
                      "credibility": "RELIABLE", "predictive_state": "UNTESTED"},
                discovered_via=f"literature:{family}"))
    if not run.dry_run and run.conn is not None:
        run.conn.commit()
    seeds = [expand_seed(run, s) for s in SEED_NODES]
    return {"families": len(LITERATURE), "references": sum(len(v) for v in LITERATURE.values()),
            "papers_planted": planted, "seeds": seeds,
            "seed_handles": [str(s["handle"]) for s in SEED_NODES],
            "any_seed_monitored": False,
            "rule": "every mechanism names its primary literature and every seed is a NODE: the "
                    "scout expands through papers, references, code, collaborators, datasets and "
                    "predecessors, recursively, and stops with a recorded reason"}


# ===================================================== THE CROSS-SOURCE INTERACTION FORGE
#: NINE CELLS where two civilizations' legs meet. Each mints TWO hypotheses -- agreement and
#: DISAGREEMENT -- because they are different economics: agreement is a crowded consensus (which
#: fades), and disagreement is one side holding information the other has not priced (which
#: resolves). Testing only the agreement arm is how a desk convinces itself consensus is alpha.
INTERACTION_CELLS: tuple[dict[str, Any], ...] = (
    {"cell": "funding_x_prediction", "legs": ("funding_level", "prediction_probability"),
     "targets": ("XAUUSD", "US500"), "mechanism_id": "positioning_crowding"},
    {"cell": "funding_x_narrative", "legs": ("funding_level", "narrative_stage"),
     "targets": ("NAS100", "XAUUSD"), "mechanism_id": "positioning_crowding"},
    {"cell": "liquidations_x_smart_flow", "legs": ("liquidation_state", "smart_participant_flow"),
     "targets": ("XAUUSD", "AUDUSD"), "mechanism_id": "forced_liquidation"},
    {"cell": "narrative_x_prediction_disagreement",
     "legs": ("narrative_stage", "prediction_disagreement"),
     "targets": ("US500", "USDJPY"), "mechanism_id": "regime_transition"},
    {"cell": "smart_flow_x_macro_surprise", "legs": ("smart_participant_flow", "macro_surprise"),
     "targets": ("USDJPY", "USDX"), "mechanism_id": "macro_release"},
    {"cell": "prediction_odds_x_rates_gold_oil_fx",
     "legs": ("prediction_probability", "rates_level"),
     "targets": ("XAUUSD", "XTIUSD", "USDJPY"), "mechanism_id": "macro_release"},
    {"cell": "crowding_x_options_x_news", "legs": ("oi_level", "options_state", "narrative_stage"),
     "targets": ("NAS100", "US500"), "mechanism_id": "gamma_hedging_state"},
    {"cell": "forced_flow_x_session_x_world_state",
     "legs": ("liquidation_state", "session_state", "world_risk_posterior"),
     "targets": ("XAUUSD", "AUDUSD"), "mechanism_id": "forced_liquidation"},
    {"cell": "hawkes_x_risk_off_x_gold",
     "legs": ("hawkes_branching_ratio", "world_risk_posterior"),
     "targets": ("XAUUSD",), "mechanism_id": "volatility_shock"},
)


def lead_lag(a: Sequence[float], b: Sequence[float], *, max_lag: int = 12,
             permutations: int = 200, seed: int = 11) -> dict[str, Any]:
    """Conditional lead-lag between two legs, WITH A PERMUTATION NULL.

    A cross-correlation peak over thirteen lags on a short series is a maximum of thirteen noisy
    numbers and it is essentially always somewhere. The null here shuffles one leg in blocks and
    re-takes the maximum, so the reported p-value is about the PEAK and not about a lag somebody
    chose after seeing it.
    """
    x = np.asarray([float(v) for v in a], dtype=float)
    y = np.asarray([float(v) for v in b], dtype=float)
    n = min(x.size, y.size)
    if n < 3 * max_lag or float(np.std(x[:n])) == 0 or float(np.std(y[:n])) == 0:
        return {"verdict": UNMEASURED,
                "why": f"{n} aligned points against max_lag {max_lag}, or a constant leg"}
    x, y = x[:n], y[:n]

    def peak(v: np.ndarray) -> tuple[float, int]:
        best, at = 0.0, 0
        for lag in range(-max_lag, max_lag + 1):
            xa = x[max(0, -lag): n - max(0, lag)]
            ya = v[max(0, lag): n - max(0, -lag)]
            if xa.size < 5 or float(np.std(xa)) == 0 or float(np.std(ya)) == 0:
                continue
            c = float(np.corrcoef(xa, ya)[0, 1])
            if abs(c) > abs(best):
                best, at = c, lag
        return best, at
    obs, at = peak(y)
    rng = np.random.default_rng(seed)
    block = max(1, n // 10)
    hits = 0
    for _ in range(max(1, permutations)):
        blocks = [y[i:i + block] for i in range(0, n, block)]
        rng.shuffle(blocks)
        null = np.concatenate(blocks)[:n]
        if abs(peak(null)[0]) >= abs(obs):
            hits += 1
    return {"verdict": "MEASURED", "peak_corr": obs, "peak_lag": at, "n": n,
            "p_value": (hits + 1) / (permutations + 1), "permutations": permutations,
            "null": "block permutation of the second leg, peak re-taken each draw"}


def interaction_forge(run: Run, legs: Mapping[str, Sequence[float]] | None = None
                      ) -> list[str]:
    """Nine cells, eighteen hypotheses, and a lead-lag screen wherever both legs exist here."""
    available = dict(legs or {})
    out: list[str] = []
    for cell in INTERACTION_CELLS:
        have = [lg for lg in cell["legs"] if lg in available]
        screen: dict[str, Any] = {"verdict": UNMEASURED,
                                  "why": f"legs present here: {have or 'none'}; the screen needs "
                                         "at least two"}
        if len(have) >= 2:
            screen = lead_lag(available[have[0]], available[have[1]])
        for stance, side in (("agreement", "follow"), ("disagreement", "revert")):
            for sym in cell["targets"]:
                spec = {
                    "symbol": sym, "asset_class": TARGET_CLASS.get(sym, ""), "chart": "H1",
                    "session": "all", "regime": "", "information": "cross_asset",
                    "mechanism_id": cell["mechanism_id"], "economic_actor": "", "side": side,
                    "family": "", "params": {"interaction_cell": cell["cell"],
                                             "legs": list(cell["legs"]), "stance": stance},
                    "assets": [sym], "required_data": list(cell["legs"]),
                    "novelty": 0.75, "confidence": 0.3,
                    "exact_rule": (f"cross {' x '.join(cell['legs'])} and take the {stance} "
                                   f"vector as a {side} conditioner on {sym}"),
                    "falsifier": (f"the {stance} vector of {cell['cell']} does not separate {sym} "
                                  "forward returns beyond either leg alone"),
                    "why": ("two constraints acting at once is a different claim from either "
                            "alone; the DISAGREEMENT arm is minted beside the agreement arm "
                            "because one side holding unpriced information is the better trade "
                            "and the one nobody tests"),
                    "lead_lag_screen": screen,
                }
                did = record(run, generator=f"forge:{cell['cell']}", spec=spec,
                             mechanism=f"interaction {cell['cell']} ({stance})",
                             source_id=f"civ:forge:{cell['cell']}")
                if did is not None:
                    out.append(did)
    return out


# ========== THE PARALLEL CIVILIZATION LAYER -- an expansion of frontier_intel, not a new miner
#
# THE PRINCIPAL'S EXPLICIT BUILDER INSTRUCTION (2026-09-17): "Do not build another frontier
# miner." So nothing below fetches. `frontier_intel/` already scouts and `moat_collectors`,
# `deep_forest_miner` and the regional collectors already capture; `libs.research.
# external_federation` already owns the roster, the five dispositions, the sandbox policy, the
# packet contract, the admission arithmetic, ROI and the twelve exhaustion conditions. This layer
# is the part none of them have: TWELVE PARALLEL ROLES that read material somebody else already
# fetched, one mandatory EXTRACTION SCHEMA so nothing useful stays prose, a PER-ENTITY CAPABILITY
# LEDGER with delta hashes so an unchanged repo costs near-zero compute, and the recursion that
# spawns new civilizations from the graph rather than from a human adding a line to a roster.
#
# CAPABILITIES, NOT BRANDS. A famous system is a search prior and never a verdict -- there is no
# prestige exemption anywhere below. What is absorbed is the CAPABILITY (joint factor/model
# optimisation, artifact-level search with an independent verifier, trajectory evolution, AST
# novelty, DSL-constrained expression search, research/live parity, order-state engineering), and
# the brand is only how the desk came to find it.

ENTITY_KINDS: tuple[str, ...] = ("system", "ecosystem", "public_lineage", "institution")

#: THE TWELVE ROLES, names exact. They run in PARALLEL over one civilization: a role that returns
#: nothing costs the other eleven nothing, and its refusal is a note rather than a silence.
CIVILIZATION_ROLES: tuple[str, ...] = (
    "SOURCE_SCOUT", "REPOSITORY_ARCHAEOLOGIST", "PAPER_CITATION_MINER", "DATA_AXIS_MINER",
    "REPRESENTATION_MINER", "SEARCH_ALGORITHM_MINER", "MECHANISM_DECOMPILER", "FAILURE_MINER",
    "REPLICATION_SCIENTIST", "DESCENDANT_SCIENTIST", "ADVERSARIAL_SCIENTIST",
    "SOURCE_ROI_ACCOUNTANT")

#: MAXIMUM-DEPTH REPO MINING, in order. The last third is where the value actually is: a README is
#: marketing, and the commit history, the closed issues and the archived releases are where a
#: project says what did NOT work. A DISAGREEMENT between documentation and implementation is not
#: a defect to reconcile -- it is a research object, because one of the two is what the authors
#: believed and the other is what they could actually make run.
REPO_SURFACES: tuple[str, ...] = (
    "readme", "source_tree", "tests", "configs", "examples", "notebooks", "data_loaders",
    "models", "evaluation", "scheduler_search", "execution", "issues", "discussions",
    "pull_requests", "commit_history", "releases", "contributors", "forks", "contributor_repos",
    "cited_papers", "datasets", "dependencies", "package_ecosystem", "archived_versions")

#: THE MANDATORY EXTRACTION SCHEMA. Every material discovery carries every one of these fields --
#: absent ones as UNMEASURED BY NAME. The rule it enforces is one line: NOTHING USEFUL REMAINS
#: PROSE-ONLY. A mechanism described in a paragraph is unqueryable, uncountable and invisible to
#: the compiler; the same mechanism in these fields is a cell the gauntlet can judge.
EXTRACTION_FIELDS: tuple[str, ...] = (
    "source_id", "canonical_url", "content_hash", "first_seen", "publication_time",
    "access_class", "evidence_grade", "author_entity", "project_repo", "commit_version",
    "capability", "mechanism", "causal_economic_rationale", "data_requirements",
    "representations", "targets", "horizons", "states_regimes", "execution_assumptions",
    "cost_assumptions", "exact_algorithm_rules", "selection_search_procedure",
    "validation_protocol", "claimed_results", "evidence_limitations", "leakage_risks",
    "selection_risks", "capacity_risks", "transferability", "mt5_fusion_feasibility",
    "known_failures", "falsifier", "novelty_lineage", "candidate_descendants",
    "dataset_descendants", "research_process_descendants")

#: THE PER-ENTITY CAPABILITY LEDGER, names exact. `external_federation.LEDGER_FIELDS` is the
#: FEDERATION's per-system ledger (disposition, sandbox, licence); this is the per-ENTITY one
#: (what was extracted and what it earned). The two are JOINED on the id rather than merged: a
#: system can be REJECTED_WITH_EVIDENCE by the federation and still be a productive civilization
#: to mine as text, and one ledger covering both would have to lie about one of those.
CAPABILITY_LEDGER_FIELDS: tuple[str, ...] = (
    "capabilities_discovered", "mechanisms_discovered", "datasets_discovered",
    "representations_discovered", "research_methods_discovered", "execution_methods_discovered",
    "candidate_descendants", "tested_descendants", "failed_descendants", "forward_survivors",
    "live_survivors", "incremental_portfolio_elog", "compute_spent", "trial_budget_spent",
    "source_roi", "last_deep_scan", "next_delta_scan")

#: CANDIDATE CONSERVATION. Everything discovered has exactly one of these states and the sum must
#: equal what was discovered. A conservation law is the only check that can notice a candidate
#: vanishing between two organs without anybody having suspected one had.
CANDIDATE_STATES: tuple[str, ...] = ("DEDUPLICATED", "TESTED", "WAITING", "BLOCKED", "REJECTED",
                                     "NONTESTABLE")

#: EVERY DATASET FOUND GETS ONE DOWNSTREAM STATE. "Interesting, filed away" is not one of them.
DATASET_STATES: tuple[str, ...] = ("WORLD_MODEL_INPUT", "CANDIDATE_INPUT", "INTERACTION_INPUT",
                                   "EXECUTION_INPUT", "PORTFOLIO_INPUT", "NEGATIVE_KNOWLEDGE",
                                   "AWAITING_EXPERIMENT", "RETIRED_WITH_EVIDENCE")

#: THE PARENT GENOME M = (D, R, S, T, H, E, P). A descendant moves one or two coordinates; the
#: brute Cartesian product of all seven is refused by PRICING in `descendant_value`, not by a cap.
GENOME_AXES: tuple[tuple[str, str], ...] = (
    ("D", "data: which observable the claim is made of"),
    ("R", "representation: how that observable is encoded"),
    ("S", "search: the procedure that found the rule"),
    ("T", "target: what is being predicted"),
    ("H", "horizon: over what span"),
    ("E", "execution: how the signal is expressed through a book"),
    ("P", "portfolio: how it is combined with everything else"))

#: ORTHOGONALITY IS MEASURED ACROSS ALL ELEVEN, never return correlation alone. Two sleeves with
#: uncorrelated returns that die to the same liquidity event are ONE bet, and the eleventh axis
#: (failure mode) is the one that says so.
ORTHOGONALITY_AXES: tuple[str, ...] = ("return", "tail", "mechanism", "information_source",
                                       "geography", "session", "horizon", "macro_factor",
                                       "liquidity", "execution_dependency", "failure_mode")

#: WHAT SPAWNS A NEW CIVILIZATION, automatically. No human adds a line to a roster: a citation
#: cluster, a contributor graph, a fork wave, a conference co-occurrence, a dependency edge, a
#: competition result, a benchmark table, unusual public performance evidence, a high-ROI author
#: or a recurring mention is enough, and `XF.admit` then decides whether it earns its own sandbox.
SPAWN_SIGNALS: tuple[str, ...] = ("citation_cluster", "contributor_graph", "stars_forks",
                                  "conference_co_occurrence", "package_dependency",
                                  "competition_winner", "benchmark_leader",
                                  "unusual_public_performance", "high_source_roi_author",
                                  "recurring_mention")

#: CAPABILITIES, NOT BRANDS. The key is how the desk found it; the value is what is absorbed, and
#: only the value ever reaches a descendant.
CAPABILITY_MAP: dict[str, tuple[str, ...]] = {
    "rd_agent": ("joint factor/model optimisation", "experiment-memory conditioning",
                 "scheduler/bandit allocation", "automated factor feedback"),
    "agonalpha": ("artifact-level search", "mcts", "fresh-context independent verifier",
                  "pending-aware scheduling", "re-execution/provenance"),
    "quantaalpha": ("research-trajectory evolution",
                    "mutation/crossover of reasoning procedures"),
    "alphaagent": ("ast novelty", "semantic consistency", "complexity regularisation"),
    "alphacrafter": ("constrained harness miner", "regime screen", "trader closure"),
    "hubble": ("dsl-constrained expression search", "deterministic evaluation",
               "positive/negative retrieval memory"),
    "lean": ("research/live parity", "deterministic replay", "order-state engineering"),
    "nautilus": ("research/live parity", "deterministic replay", "order-state engineering"),
    "hummingbot": ("execution architecture", "venue architecture", "microstructure"),
    "finrl": ("modular model -> allocation -> timing -> risk -> execution",),
    "qlib": ("data tooling", "walk-forward harness", "model zoo contest"),
    "vietnam_alpha": ("self-improving multi-agent alpha search",),
    "wq_research_engine": ("operator-constrained expression search at scale",),
}

#: CROSS-SYSTEM SYNTHESIS IS SEARCHED EXPLICITLY, not hoped for. The interesting object is
#: "AgonAlpha's independent verifier over QuantaAlpha's evolved trajectories" -- which neither
#: project would ever build and no paper describes, so nothing finds it except a deliberate search.
SYNTHESIS_CELLS: tuple[dict[str, Any], ...] = (
    {"cell": "search_x_verify_x_evolve",
     "systems": ("rd_agent", "agonalpha", "quantaalpha", "alphaagent", "hubble"),
     "question": "does a fresh-context independent verifier over evolved research trajectories "
                 "kill more false positives than any one system's own screen?"},
    {"cell": "execution_scientist",
     "systems": ("nautilus", "lean", "hummingbot"),
     "question": "research/live parity plus deterministic replay plus microstructure execution, "
                 "as Execution Scientist descendants for MT5/Fusion specifically"},
)


@dataclass(frozen=True)
class Entity:
    """One vertex of the source graph: a system, an ecosystem, a public lineage or an institution.

    `seed` marks a STARTING VERTEX and is never a ceiling -- `spawn()` adds entities the roster
    never named, and afterwards they are indistinguishable from seeds except by `discovered_via`.
    """

    entity_id: str
    name: str
    kind: str
    discovered_via: str
    access_label: str = "PUBLIC"
    credibility: str = "UNKNOWN"
    capabilities: tuple[str, ...] = ()
    seed: bool = True
    monitored: bool = False
    note: str = ""


#: The principal's short names against `frontier_intel.registry.FIRMS`'s fuller ones. Without this
#: the gap report lies in the expensive direction -- it would claim XTX, HRT and QRT are unwatched
#: when the registry holds all three under their long names, and a session would then "fix" a gap
#: that does not exist by adding duplicate rows to somebody else's table.
_FIRM_ALIASES: dict[str, str] = {
    "XTX": "XTX Markets", "HRT": "Hudson River Trading",
    "QRT": "Qube Research & Technologies",
}


def _firm_names() -> frozenset[str]:
    try:
        from frontier_intel.registry import FIRMS
        return frozenset(f.name for f in FIRMS)
    except Exception:
        return frozenset()


def _in_firms(name: str, firms: frozenset[str]) -> bool:
    return name in firms or _FIRM_ALIASES.get(name, "") in firms


def _system_entities() -> tuple[Entity, ...]:
    """The systems, READ FROM `XF.SEEDS`. Never re-listed here: two rosters drift within a week,
    and the federation's is the one `scripts/check_external_federation.py` fences."""
    return tuple(Entity(entity_id=f"system:{s.system_id}", name=s.name, kind="system",
                        discovered_via="external_federation.SEEDS",
                        capabilities=tuple(CAPABILITY_MAP.get(s.system_id, s.capabilities)),
                        credibility="UNKNOWN", note=s.role)
                 for s in XF.SEEDS)


#: The ecosystems the principal named as starting vertices.
_ECOSYSTEMS: tuple[tuple[str, str], ...] = (
    ("worldquant_brain", "WorldQuant BRAIN"), ("arxiv_qfin", "arXiv q-fin / cs.LG"),
    ("ssrn_nber", "SSRN / NBER"), ("public_competitions", "public quant competitions"),
    ("kaggle_market", "Kaggle-style market datasets"),
    ("mql5_research", "MQL5 / public MT5 research ecosystems"))
#: The institutional seeds. Most are already in `frontier_intel.registry.FIRMS`, which owns their
#: grading and investigation weights; these rows are the CIVILIZATION view of the same names and
#: join to it by name. The ones NOT in that registry are named as a GAP rather than silently
#: appended to another organ's table -- adding them there is that organ's owner's call.
_INSTITUTIONS: tuple[str, ...] = (
    "Renaissance Technologies", "D. E. Shaw", "Two Sigma", "Man AHL", "WorldQuant", "High-Flyer",
    "Lingjun", "Ubiquant", "Minghong", "Citadel", "Citadel Securities", "Jane Street", "XTX",
    "HRT", "Optiver", "IMC", "AQR", "Winton", "QRT", "Squarepoint", "Bridgewater")


def seed_universe() -> tuple[Entity, ...]:
    """The starting vertices. STARTING, not a ceiling -- `spawn()` is how the set actually grows."""
    firms = _firm_names()
    out: list[Entity] = list(_system_entities())
    out += [Entity(f"ecosystem:{eid}", name, "ecosystem", "principal_mandate_2026-09-17",
                   access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE")
            for eid, name in _ECOSYSTEMS]
    out += [Entity(f"lineage:{s['handle']}", str(s["handle"]), "public_lineage",
                   "principal_mandate_2026-09-17", credibility="UNKNOWN", monitored=False,
                   note="public papers, code, references, collaborators, datasets and "
                        "predecessors ONLY; feeds and posts are never monitored or mined")
            for s in SEED_NODES]
    out += [Entity(f"institution:{n.lower().replace(' ', '_').replace('.', '')}", n,
                   "institution", "principal_mandate_2026-09-17", access_label="PUBLIC",
                   credibility="AUTHORITATIVE" if _in_firms(n, firms) else "UNKNOWN",
                   note=("joins frontier_intel.registry.FIRMS" if _in_firms(n, firms)
                         else "NOT in frontier_intel.registry.FIRMS: named here as a GAP, never "
                              "silently added to another organ's table"))
            for n in _INSTITUTIONS]
    return tuple(out)


def registry_gaps() -> list[str]:
    """Institutional seeds the principal named that `frontier_intel.registry.FIRMS` does not hold.

    Published rather than fixed here: that table owns the firm grades and the investigation
    weights, and a second module appending rows to it is how two organs come to disagree about
    what the desk watches.
    """
    firms = _firm_names()
    return [] if not firms else sorted(n for n in _INSTITUTIONS if not _in_firms(n, firms))


def spawn(signals: Sequence[Mapping[str, Any]], existing: Sequence[Entity] = ()) -> dict[str, Any]:
    """New civilizations from the GRAPH, automatically -- and `XF.admit` decides the sandbox.

    A signal is a (signal, kind, name, evidence) row produced from material somebody already
    fetched. This never crawls: it reads the signal, mints the entity, and leaves the sandbox
    question to the federation. Ten forks of one framework spawn ten entities here and collapse to
    one sandbox there, which is the right division -- the graph may be redundant, the compute
    budget may not.
    """
    known = {e.entity_id for e in existing} or {e.entity_id for e in seed_universe()}
    spawned: list[Entity] = []
    refused: list[dict[str, Any]] = []
    for sig in signals:
        kind = str(sig.get("signal") or "")
        name = str(sig.get("name") or "").strip()
        if kind not in SPAWN_SIGNALS:
            refused.append({"name": name, "why": f"signal {kind!r} is not a spawn trigger"})
            continue
        if not name:
            refused.append({"name": "", "why": "a spawn signal with no named entity"})
            continue
        eid = f"{sig.get('kind') or 'system'}:{name.lower().replace(' ', '_')}"
        if eid in known:
            refused.append({"name": name, "why": "already a vertex of the source graph"})
            continue
        known.add(eid)
        spawned.append(Entity(eid, name, str(sig.get("kind") or "system"), discovered_via=kind,
                              access_label=str(sig.get("access_label") or "ACCESS_UNCLEAR"),
                              capabilities=tuple(sig.get("capabilities") or ()), seed=False,
                              note=str(sig.get("evidence") or "")[:300]))
    return {"spawned": spawned, "n_spawned": len(spawned), "refused": refused,
            "signals": list(SPAWN_SIGNALS),
            "rule": "new civilizations come from citation clusters, contributor graphs, forks, "
                    "co-occurrence, dependencies, competitions, benchmarks, unusual public "
                    "performance, high-ROI authors and recurring mentions -- never from a human "
                    "editing a roster"}


# ------------------------------------------------------------------ the extraction schema
def extraction_row(**fields: Any) -> dict[str, Any]:
    """One material discovery, with EVERY schema field present.

    A field nobody measured is the string UNMEASURED -- not a blank and not an omission. An absent
    key reads as "does not apply" and an UNMEASURED one reads as "nobody has looked", and those
    are different research states. Unknown keys are REFUSED rather than silently carried, because
    a schema that accepts anything cannot be queried for completeness.
    """
    unknown = sorted(k for k in fields if k not in EXTRACTION_FIELDS)
    if unknown:
        raise ValueError(f"{unknown} are not extraction-schema fields; the schema is closed so "
                         "that a query over it can be trusted to be complete")
    row: dict[str, Any] = dict.fromkeys(EXTRACTION_FIELDS, UNMEASURED)
    row.update({k: v for k, v in fields.items() if v is not None})
    return row


def schema_completeness(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """How much of the schema is actually filled, per field. THE ZEROS ARE THE FINDING: a field
    nobody ever fills is a role nobody is really running."""
    if not rows:
        return {"verdict": UNMEASURED, "why": "no extraction rows this pass", "n": 0}
    filled = {f: sum(1 for r in rows if r.get(f) not in (None, "", UNMEASURED))
              for f in EXTRACTION_FIELDS}
    return {"verdict": "MEASURED", "n": len(rows), "filled": filled,
            "share": {f: filled[f] / len(rows) for f in EXTRACTION_FIELDS},
            "never_filled": sorted(f for f, n in filled.items() if n == 0),
            "rule": "nothing useful remains prose-only"}


# ------------------------------------------------------------------ the twelve roles
@dataclass
class Material:
    """What somebody else ALREADY FETCHED about one entity, keyed by repo surface.

    This layer never opens a socket. `gather` reads the moat's claims, the frontier queue and the
    seat intelligence directories -- artifacts the existing collectors wrote -- and a surface with
    nothing behind it stays ABSENT, which is what lets `SOURCE_SCOUT` report which of the
    twenty-four surfaces were never reached instead of implying it read them all.
    """

    entity_id: str
    surfaces: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    fetched_by: list[str] = field(default_factory=list)

    def rows(self, *names: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for n in names:
            out.extend(self.surfaces.get(n) or [])
        return out

    def missing(self) -> list[str]:
        return [s for s in REPO_SURFACES if not self.surfaces.get(s)]


def gather(entity: Entity, run: Run, *, limit: int = 60) -> Material:
    """Assemble already-captured material for one entity. READS ONLY -- never a fetch."""
    mat = Material(entity_id=entity.entity_id)
    needle = entity.name.lower()
    if run.conn is not None:
        try:
            cur = run.conn.execute(
                "SELECT claim_id, source_id, text, language, knowable_at, kind FROM claims "
                "ORDER BY created_at DESC LIMIT ?", (limit * 20,))
            for r in (dict(x) for x in cur.fetchall()):
                blob = f"{r.get('text') or ''} {r.get('source_id') or ''}".lower()
                if needle in blob:
                    mat.surfaces.setdefault("readme", []).append(r)
            if mat.surfaces:
                mat.fetched_by.append("moat_collectors/claims")
        except Exception as exc:
            run.note("gather", f"{entity.entity_id}: claims unreadable ({type(exc).__name__})")
    fq = DESK / "frontier_intel" / "data" / "frontier_queue.jsonl"
    if fq.exists():
        try:
            with fq.open("r", encoding="utf-8", errors="replace") as fh:
                for i, line in enumerate(fh):
                    if i >= limit * 50:
                        break
                    if needle not in line.lower():
                        continue
                    try:
                        row = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(row, dict):
                        mat.surfaces.setdefault("issues", []).append(row)
            if mat.surfaces.get("issues"):
                mat.fetched_by.append("frontier_intel/frontier_queue.jsonl")
        except OSError:
            pass
    if not mat.surfaces:
        run.note("gather", f"{entity.entity_id}: no already-fetched material on this box; the "
                           "roles run and report UNMEASURED rather than fetching anything")
    return mat


def _mat_row(entity: Entity, role: str, capability: str, mechanism: str, *,
             rationale: str = "", falsifier: str = "", **extra: Any) -> dict[str, Any]:
    return extraction_row(source_id=f"{entity.entity_id}#{role}", author_entity=entity.name,
                          capability=capability, mechanism=mechanism,
                          causal_economic_rationale=rationale or UNMEASURED,
                          falsifier=falsifier or UNMEASURED, access_class=entity.access_label,
                          evidence_grade=entity.credibility, **extra)


def role_source_scout(e: Entity, m: Material, run: Run) -> list[dict[str, Any]]:
    """Which surfaces exist at all, and which of the twenty-four were never reached."""
    run.note("SOURCE_SCOUT", f"{e.entity_id}: {len(m.missing())} of {len(REPO_SURFACES)} repo "
                             "surfaces have no captured material on this box")
    reached = sorted(set(REPO_SURFACES) - set(m.missing()))
    return [_mat_row(e, "SOURCE_SCOUT", capability="information_acquisition",
                     mechanism=f"surfaces reached: {reached or 'none'}",
                     project_repo=e.name, novelty_lineage=e.discovered_via)]


def role_repository_archaeologist(e: Entity, m: Material, run: Run) -> list[dict[str, Any]]:
    """Read the shipped code against the documentation. THE DISAGREEMENT IS THE RESEARCH OBJECT.

    A README promising a walk-forward beside a test suite that shuffles is not a documentation bug:
    it is evidence about what the authors could not make work, which is the most valuable thing a
    public repository contains and the one thing nobody publishes on purpose.
    """
    docs = m.rows("readme", "discussions")
    code = m.rows("source_tree", "tests", "configs", "evaluation")
    if not docs and not code:
        return []
    if docs and not code:
        run.note("REPOSITORY_ARCHAEOLOGIST",
                 f"{e.entity_id}: documentation captured with no source tree beside it -- the "
                 "disagreement is UNMEASURED, which is not agreement")
    return [_mat_row(e, "REPOSITORY_ARCHAEOLOGIST", capability="research_reproduction",
                     mechanism="documentation vs implementation comparison",
                     validation_protocol="read from configs/tests" if code else UNMEASURED,
                     evidence_limitations=("only already-captured surfaces were compared; "
                                           f"{len(m.missing())} surfaces are UNMEASURED"))]


def role_paper_citation_miner(e: Entity, m: Material, run: Run) -> list[dict[str, Any]]:
    """Papers and the citation graph out of them: source -> paper -> citation, recursively."""
    refs = LITERATURE.get(e.entity_id.split(":")[-1], ())
    rows = [_mat_row(e, "PAPER_CITATION_MINER", capability="research_reproduction",
                     mechanism=str(ref["title"]), rationale=str(ref["why"]),
                     novelty_lineage=f"{e.entity_id} -> {ref['title']}")
            for ref in refs]
    return rows or [_mat_row(
        e, "PAPER_CITATION_MINER", capability="research_reproduction",
        mechanism="no primary literature declared for this entity yet",
        research_process_descendants="declare it in LITERATURE so the scout can expand it")]


def role_data_axis_miner(e: Entity, m: Material, run: Run) -> list[dict[str, Any]]:
    """Which OBSERVABLE the system uses -- and every dataset found gets one downstream state."""
    found = [str(r.get("kind") or r.get("name") or "") for r in m.rows("data_loaders", "datasets")]
    routed = route_dataset({"name": e.name, "description": " ".join(found)})
    return [_mat_row(e, "DATA_AXIS_MINER", capability="data_source",
                     mechanism="data axes this system's own loaders declare",
                     data_requirements=found or UNMEASURED,
                     dataset_descendants=routed["state"])]


def role_representation_miner(e: Entity, m: Material, run: Run) -> list[dict[str, Any]]:
    """How the observable is encoded before the search ever sees it."""
    return [_mat_row(e, "REPRESENTATION_MINER", capability="representation_learning",
                     mechanism="encoding applied before search",
                     representations=list(e.capabilities) or UNMEASURED)]


def role_search_algorithm_miner(e: Entity, m: Material, run: Run) -> list[dict[str, Any]]:
    """The PROCEDURE that found the rule, which transfers even when the rule does not."""
    return [_mat_row(e, "SEARCH_ALGORITHM_MINER", capability="artifact_search",
                     mechanism=f"search procedure of {e.name}",
                     selection_search_procedure=list(e.capabilities) or UNMEASURED,
                     research_process_descendants="the procedure is a meta-R&D descendant even "
                                                  "when every rule it found dies")]


def role_mechanism_decompiler(e: Entity, m: Material, run: Run) -> list[dict[str, Any]]:
    """COMPETING explanations, never the glamorous one alone, each carrying its own falsifier."""
    return [_mat_row(
        e, "MECHANISM_DECOMPILER", capability=str(cap),
        mechanism=f"{cap}: which constrained participant would this be exploiting?",
        falsifier=f"{cap} produces no descendant that separates forward returns on any MT5 "
                  "target, at any horizon, after the round trip",
        mt5_fusion_feasibility=UNMEASURED, transferability=UNMEASURED)
        for cap in (e.capabilities or ("unnamed capability",))]


def role_failure_miner(e: Entity, m: Material, run: Run) -> list[dict[str, Any]]:
    """Closed issues, reverted commits, abandoned branches: the half of the corpus that is free."""
    rows = m.rows("issues", "pull_requests", "commit_history")
    if not rows:
        run.note("FAILURE_MINER", f"{e.entity_id}: no issue/PR/commit material captured; the "
                                  "negative knowledge is UNMEASURED, not absent")
        return []
    return [_mat_row(e, "FAILURE_MINER", capability="research_reproduction",
                     mechanism=f"{len(rows)} captured failure surfaces",
                     known_failures=[str(r.get("title") or r.get("text") or "")[:120]
                                     for r in rows[:20]],
                     evidence_limitations="already-captured surfaces only")]


def role_replication_scientist(e: Entity, m: Material, run: Run) -> list[dict[str, Any]]:
    """Can the claim be reproduced HERE -- on this desk's PIT bars, under this desk's protocol?"""
    return [_mat_row(e, "REPLICATION_SCIENTIST", capability="research_reproduction",
                     mechanism="replication under the desk's own PIT bars and gate protocol",
                     validation_protocol="external_gauntlet ten gates",
                     leakage_risks=UNMEASURED,
                     selection_risks="the published result is the survivor of an unknown number "
                                     "of unpublished attempts; the trial count is UNMEASURED")]


def role_descendant_scientist(e: Entity, m: Material, run: Run) -> list[dict[str, Any]]:
    """Move one or two genome coordinates and PRICE the move. Never the Cartesian product."""
    prior = {"p_survive": 0.1, "d_elog": 0.01, "info": 0.5, "novelty": 0.5,
             "orthogonality": 0.5, "c_compute": 1.0}
    return [_mat_row(e, "DESCENDANT_SCIENTIST", capability="artifact_search",
                     mechanism=f"genome axis {axis} moved: {why}",
                     candidate_descendants=f"V(a)={descendant_value(prior):.4g}")
            for axis, why in GENOME_AXES]


def role_adversarial_scientist(e: Entity, m: Material, run: Run) -> list[dict[str, Any]]:
    """The case AGAINST, made with the same effort as the case for. NO PRESTIGE EXEMPTION."""
    return [_mat_row(e, "ADVERSARIAL_SCIENTIST", capability="independent_verifier",
                     mechanism=f"the strongest case that {e.name} carries no transferable edge",
                     leakage_risks=UNMEASURED, selection_risks=UNMEASURED,
                     capacity_risks=UNMEASURED,
                     evidence_limitations="reputation is a search prior and never a verdict; a "
                                          "famous entity gets no exemption from this row")]


def role_source_roi_accountant(e: Entity, m: Material, run: Run) -> list[dict[str, Any]]:
    """What this civilization EARNED -- and never a reason to shut it off, only to throttle it."""
    return [_mat_row(e, "SOURCE_ROI_ACCOUNTANT", capability="information_acquisition",
                     mechanism="ROI_s = (independent survivor value + information gain) / "
                               "(compute + data + trial budget + engineering)",
                     research_process_descendants="a low-ROI frontier drops to maintenance delta "
                                                  "scouting; it is never switched off")]


ROLE_FUNCS: dict[str, Any] = {
    "SOURCE_SCOUT": role_source_scout,
    "REPOSITORY_ARCHAEOLOGIST": role_repository_archaeologist,
    "PAPER_CITATION_MINER": role_paper_citation_miner,
    "DATA_AXIS_MINER": role_data_axis_miner,
    "REPRESENTATION_MINER": role_representation_miner,
    "SEARCH_ALGORITHM_MINER": role_search_algorithm_miner,
    "MECHANISM_DECOMPILER": role_mechanism_decompiler,
    "FAILURE_MINER": role_failure_miner,
    "REPLICATION_SCIENTIST": role_replication_scientist,
    "DESCENDANT_SCIENTIST": role_descendant_scientist,
    "ADVERSARIAL_SCIENTIST": role_adversarial_scientist,
    "SOURCE_ROI_ACCOUNTANT": role_source_roi_accountant,
}


def run_roles(entity: Entity, material: Material, run: Run,
              only: Sequence[str] | None = None) -> dict[str, Any]:
    """All twelve on the SAME material, independently.

    One role raising costs the other eleven nothing: its exception becomes a note, which is a
    disposition, and the pass continues.
    """
    wanted = set(only) if only is not None else set(CIVILIZATION_ROLES)
    out: dict[str, list[dict[str, Any]]] = {}
    for name in CIVILIZATION_ROLES:
        if name not in wanted:
            continue
        try:
            out[name] = list(ROLE_FUNCS[name](entity, material, run))
        except Exception as exc:
            run.note(name, f"{entity.entity_id}: role raised {type(exc).__name__}: {exc}; "
                           "counted, never swallowed")
            out[name] = []
    rows = [r for v in out.values() for r in v]
    return {"entity": entity.entity_id, "roles": {k: len(v) for k, v in out.items()},
            "rows": rows, "n_rows": len(rows), "surfaces_missing": material.missing(),
            "material_from": list(material.fetched_by),
            "completeness": schema_completeness(rows),
            "silent_roles": [k for k, v in out.items() if not v]}


# ------------------------------------------------------------------ descendant pricing
def descendant_value(a: Mapping[str, Any]) -> float:
    """V(a) = P(survive|D) x E[dG|survive] x I(a) x N(a) x O(a) / (C_compute + C_data + C_trial
    + C_delay).

    THE DELAY TERM IS WHY THIS IS A PRICE AND NOT A COUNT. A descendant needing a dataset nobody
    has yet is not cheap because its compute is small: the delay is real cost, and pricing it is
    what stops the queue filling with cells that cannot run for a month.
    """
    def f(k: str, d: float) -> float:
        try:
            return float(a.get(k, d))
        except (TypeError, ValueError):
            return d
    num = (f("p_survive", 0.1) * f("d_elog", 0.0) * f("info", 0.5) * f("novelty", 0.5)
           * f("orthogonality", 0.5))
    den = max(f("c_compute", 1.0) + f("c_data", 0.0) + f("c_trial", 0.0) + f("c_delay", 0.0),
              1e-9)
    return float(num / den)


def orthogonality(vectors: Mapping[str, Sequence[float]]) -> dict[str, Any]:
    """Independence across all eleven axes; the axis that is NOT independent is the answer."""
    have = {k: list(v) for k, v in vectors.items() if k in ORTHOGONALITY_AXES and len(v) > 1}
    missing = [a for a in ORTHOGONALITY_AXES if a not in have]
    if len(have) < 2:
        return {"verdict": UNMEASURED, "measured_axes": sorted(have), "unmeasured_axes": missing,
                "why": "fewer than two axes carry a series"}
    keys = sorted(have)
    k = min(len(have[x]) for x in keys)
    mat = np.vstack([np.asarray(have[x][:k], dtype=float) for x in keys])
    if float(np.min(np.std(mat, axis=1))) <= 0:
        return {"verdict": UNMEASURED, "why": "a constant axis", "measured_axes": keys,
                "unmeasured_axes": missing}
    off = np.abs(np.corrcoef(mat) - np.eye(len(keys)))
    idx = int(np.argmax(off))
    return {"verdict": "MEASURED", "measured_axes": keys, "unmeasured_axes": missing,
            "worst_abs_corr": float(np.max(off)), "binding_axis": keys[idx // len(keys)],
            "independent": bool(float(np.max(off)) < 0.5),
            "rule": "eleven axes, not return correlation alone: two sleeves that die to the same "
                    "liquidity event are ONE bet however uncorrelated their returns look"}


# ------------------------------------------------------------------ conservation and routing
def candidate_conservation(counts: Mapping[str, Any]) -> dict[str, Any]:
    """DISCOVERED = DEDUPLICATED + TESTED + WAITING + BLOCKED + REJECTED + NONTESTABLE.

    A conservation law that does not balance NAMES THE LEAK, and it is the only check on this desk
    that can notice a candidate vanishing between two organs without anybody suspecting one had.
    """
    disc = int(counts.get("DISCOVERED", 0) or 0)
    parts = {k: int(counts.get(k, 0) or 0) for k in CANDIDATE_STATES}
    total = sum(parts.values())
    return {"DISCOVERED": disc, "states": parts, "accounted": total,
            "unaccounted": disc - total, "balances": bool(disc == total),
            "states_vocabulary": list(CANDIDATE_STATES),
            "rule": "every discovered candidate has exactly one state; an unaccounted remainder "
                    "is a silent drop and a defect, never a rounding difference"}


#: How a dataset is routed. Keyword-driven and OPEN: a dataset matching nothing goes to
#: AWAITING_EXPERIMENT, which is a disposition with an owner rather than a shrug.
_DATASET_ROUTES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("NEGATIVE_KNOWLEDGE", ("failed", "retracted", "withdrawn", "refuted", "graveyard")),
    ("EXECUTION_INPUT", ("fill", "slippage", "spread", "book", "latency", "order", "venue")),
    ("PORTFOLIO_INPUT", ("covariance", "correlation", "portfolio", "allocation", "risk")),
    ("WORLD_MODEL_INPUT", ("macro", "rates", "cpi", "policy", "regime", "gdp", "inflation")),
    ("INTERACTION_INPUT", ("cross", "interaction", "pair", "relative", "basis")),
    ("CANDIDATE_INPUT", ("price", "bar", "tick", "return", "signal", "factor", "volume")),
)


def route_dataset(row: Mapping[str, Any]) -> dict[str, Any]:
    """One downstream state per dataset. "Interesting, filed away" is not one of them."""
    declared = str(row.get("state") or "").upper()
    if declared in DATASET_STATES:
        return {"state": declared, "why": "declared by the discovering role",
                "states": list(DATASET_STATES)}
    blob = " ".join(str(row.get(k) or "") for k in ("name", "kind", "description",
                                                    "mechanism")).lower()
    for state, keys in _DATASET_ROUTES:
        if any(k in blob for k in keys):
            return {"state": state, "why": f"matched the {state} vocabulary",
                    "matched": blob[:120], "states": list(DATASET_STATES)}
    return {"state": "AWAITING_EXPERIMENT",
            "why": "no route matched: the dataset waits for a NAMED experiment rather than "
                   "sitting in a directory nobody reads",
            "states": list(DATASET_STATES)}


# ------------------------------------------------------------------ the capability ledger
def delta_hash(surfaces: Mapping[str, Any]) -> str:
    """One content hash over every watched surface -- repos, commits, releases, docs, issues,
    papers, websites, datasets. An unchanged hash means near-zero compute next pass."""
    payload = json.dumps({str(k): surfaces[k] for k in sorted(surfaces)}, sort_keys=True,
                         default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:32]


def delta_scan(entity_id: str, surfaces: Mapping[str, Any],
               previous: Mapping[str, Any] | None = None, *, now: datetime | None = None,
               maintenance_h: float = 168.0, active_h: float = 24.0) -> dict[str, Any]:
    """Changed or unchanged, and what the next pass should therefore cost.

    NEVER SHUT A FRONTIER OFF. An unchanged entity drops to MAINTENANCE DELTA SCOUTING -- a hash
    comparison a week from now -- not to removal, because the usual reason a frontier is quiet
    this week is that nobody pushed, and not that it stopped being a frontier.
    """
    at = now or datetime.now(tz=UTC)
    h = delta_hash(surfaces)
    old = str((previous or {}).get("delta_hash") or "")
    changed = bool(old) and old != h
    first = not old
    gap = active_h if (changed or first) else maintenance_h
    return {"entity_id": entity_id, "delta_hash": h, "previous_hash": old or UNMEASURED,
            "changed": changed, "first_scan": first,
            "compute_posture": ("targeted_re_analysis" if (changed or first)
                                else "maintenance_delta_scouting"),
            "last_deep_scan": (at.isoformat(timespec="seconds") if (changed or first)
                               else str((previous or {}).get("last_deep_scan") or UNMEASURED)),
            "next_delta_scan": (at + timedelta(hours=gap)).isoformat(timespec="seconds"),
            "surfaces": sorted(surfaces),
            "rule": "unchanged costs near-zero compute; a frontier is throttled to maintenance "
                    "scouting, never switched off"}


def source_roi_s(row: Mapping[str, Any]) -> dict[str, Any]:
    """ROI_s = (future independent survivor value + information gain) / (compute + data + trial
    budget + engineering). UNMEASURED when nothing has been spent -- never a zero, never an
    infinity, and never a reason to close a frontier."""
    def f(k: str) -> float:
        try:
            return float(row.get(k, 0.0) or 0.0)
        except (TypeError, ValueError):
            return 0.0
    cost = f("compute_spent") + f("data_spent") + f("trial_budget_spent") + f("engineering_spent")
    value = f("forward_survivors") * f("incremental_portfolio_elog") + f("information_gain")
    if cost <= 0:
        return {"verdict": UNMEASURED, "source_roi": None, "value": value, "cost": cost,
                "why": "nothing has been spent on this civilization yet: an ROI on zero cost is "
                       "not a large number, it is not a number"}
    return {"verdict": "MEASURED", "source_roi": value / cost, "value": value, "cost": cost,
            "posture": "maintenance_delta_scouting" if value / cost < 0.1 else "active",
            "rule": "a low ROI throttles a frontier to delta scouting; it never closes one, and "
                    "reputation never substitutes for this number"}


def capability_ledger(entity: Entity, **state: Any) -> dict[str, Any]:
    """The per-entity ledger row, every field present, JOINED to the federation's own row."""
    row: dict[str, Any] = {"entity_id": entity.entity_id, "name": entity.name,
                           "kind": entity.kind, "seed": entity.seed,
                           "discovered_via": entity.discovered_via}
    for f in CAPABILITY_LEDGER_FIELDS:
        row[f] = state.get(f, 0 if f.endswith(("_discovered", "_descendants", "_survivors"))
                           else UNMEASURED)
    roi = source_roi_s(state)
    row["source_roi"] = roi.get("source_roi")
    row["source_roi_verdict"] = roi["verdict"]
    sid = entity.entity_id.split(":")[-1]
    fed = XF.SEED_BY_ID.get(sid)
    row["federation"] = ({"system_id": fed.system_id, "integration": fed.integration,
                          "licence": fed.licence, "axes": list(fed.axes)} if fed is not None
                         else {"verdict": UNMEASURED,
                               "why": "not a federation system; the capability ledger stands on "
                                      "its own and joins nothing"})
    return row


def exhaustion(entity_id: str, conditions: Mapping[str, Any]) -> dict[str, Any]:
    """The twelve conditions of LAWS 5g, evaluated by the FEDERATION'S OWN function.

    Delegated on purpose: a second implementation of "is this frontier exhausted" is how two
    organs come to disagree about whether a source is done, and the law-gate fence checks theirs.
    """
    ok, missing = XF.exhausted(conditions)
    return {"entity_id": entity_id, "exhausted": ok, "missing": list(missing),
            "status": "CURRENT_PUBLIC_FRONTIER_EXHAUSTED" if ok else "DEEP_MINING",
            "conditions": list(XF.EXHAUSTION_CONDITIONS),
            "rule": "provisional by construction: a commit tomorrow reopens it, and there is no "
                    "DONE_FOREVER in this vocabulary"}


# ------------------------------------------------------------------ the control plane
CONTROL_PLANE_FIELDS: tuple[str, ...] = (
    "component_id", "source_civilization", "input_queue", "output_contract", "cadence",
    "progress_watermark", "sla_s", "resource_budget_s", "producer", "consumer", "postcondition")


def register_worker(component_id: str, *, civilization: str, input_queue: str,
                    output_contract: str, cadence: str, producer: str, consumer: str,
                    postcondition: str, sla_s: float = 3600.0, resource_budget_s: float = 300.0,
                    watermark: str = UNMEASURED) -> dict[str, Any]:
    """Every worker declares itself, or it is not running -- it is hiding.

    An organ with no declared CONSUMER is this desk's most common defect (III.16): it produces an
    artifact on a schedule nothing reads, and from the outside that is indistinguishable from
    working. Naming the consumer and the postcondition is what makes the difference checkable.
    """
    return {"component_id": component_id, "source_civilization": civilization,
            "input_queue": input_queue, "output_contract": output_contract, "cadence": cadence,
            "progress_watermark": watermark, "sla_s": sla_s,
            "resource_budget_s": resource_budget_s, "producer": producer, "consumer": consumer,
            "postcondition": postcondition}


def control_plane() -> list[dict[str, Any]]:
    """This module's own workers, declared. Each is an hourly leg of the intel department."""
    return [
        register_worker("source_civilizations", civilization="all",
                        input_queue="registry.claims + frontier_intel/frontier_queue.jsonl",
                        output_contract="reports/SOURCE_CIVILIZATIONS.json + registry discoveries",
                        cadence="hourly (hourly_cycle leg `source_civilizations`, intel)",
                        producer="moat_collectors, deep_forest_miner, frontier_intel",
                        consumer="discovery_compiler (registry discoveries -> gauntlet cells)",
                        postcondition="every discovery has a state; every role has a count"),
        register_worker("evidence_watchtower", civilization="all",
                        input_queue="the desk artifacts named in default_objects()",
                        output_contract="data/watchtower.jsonl + reports/EVIDENCE_WATCHTOWER.json",
                        cadence="hourly (hourly_cycle leg `evidence_watchtower`, intel)",
                        producer="the desk's own organs",
                        consumer="discovery_compiler and any session reading the ledger",
                        postcondition="false_transition_rate is 0 on the missing-data fixture"),
        register_worker("prediction_markets", civilization="bl888m",
                        input_queue="fixtures (--no-fetch) or a permitted venue API",
                        output_contract="reports/PREDICTION_MARKETS.json + registry discoveries",
                        cadence="hourly (hourly_cycle leg `prediction_markets`, intel)",
                        producer="venue APIs within their published terms",
                        consumer="discovery_compiler",
                        postcondition="calibration fitted per cell or UNMEASURED by name"),
    ]


def civilization_pass(run: Run, *, max_entities: int = 8) -> dict[str, Any]:
    """One pass of the twelve roles over the civilizations whose watched surfaces changed.

    DELTA-FIRST. Entities are ordered by whether their surfaces moved, so an hour spends its
    budget where something actually happened and an unchanged civilization costs a hash.
    """
    universe = seed_universe()
    scans = [delta_scan(e.entity_id, {"name": e.name, "capabilities": list(e.capabilities)})
             for e in universe]
    order = sorted(zip(universe, scans, strict=True),
                   key=lambda pair: (not pair[1]["changed"], not pair[1]["first_scan"]))
    results: list[dict[str, Any]] = []
    ledger: list[dict[str, Any]] = []
    for entity, scan in order[:max(1, int(max_entities))]:
        if run.left <= 0:
            run.note("civilization_pass", "budget exhausted; the remaining civilizations are "
                                          "owed and are first in line next pass")
            break
        res = run_roles(entity, gather(entity, run), run)
        res["delta"] = scan
        results.append(res)
        ledger.append(capability_ledger(
            entity, capabilities_discovered=len(entity.capabilities),
            mechanisms_discovered=res["roles"].get("MECHANISM_DECOMPILER", 0),
            datasets_discovered=res["roles"].get("DATA_AXIS_MINER", 0),
            representations_discovered=res["roles"].get("REPRESENTATION_MINER", 0),
            research_methods_discovered=res["roles"].get("SEARCH_ALGORITHM_MINER", 0),
            candidate_descendants=res["roles"].get("DESCENDANT_SCIENTIST", 0),
            last_deep_scan=scan["last_deep_scan"], next_delta_scan=scan["next_delta_scan"]))
    rows = [r for res in results for r in res["rows"]]
    return {"universe": len(universe), "entities_processed": len(results),
            "roles": list(CIVILIZATION_ROLES), "repo_surfaces": list(REPO_SURFACES),
            "extraction_fields": list(EXTRACTION_FIELDS), "extraction_rows": len(rows),
            "completeness": schema_completeness(rows), "ledger": ledger,
            "ledger_fields": list(CAPABILITY_LEDGER_FIELDS),
            "results": [{k: v for k, v in r.items() if k != "rows"} for r in results],
            "synthesis_cells": [dict(c) for c in SYNTHESIS_CELLS],
            "genome_axes": [list(a) for a in GENOME_AXES],
            "orthogonality_axes": list(ORTHOGONALITY_AXES),
            "spawn_signals": list(SPAWN_SIGNALS), "dataset_states": list(DATASET_STATES),
            "registry_gaps": registry_gaps(),
            "candidate_conservation": candidate_conservation(
                {"DISCOVERED": len(rows), "WAITING": len(rows)}),
            "control_plane": control_plane(),
            "not_a_fetcher": "this layer reads material other organs already captured; "
                             "frontier_intel scouts and moat_collectors captures"}


# --------------------------------------------------------------------------- the organ
def run_pass(*, dry_run: bool = False, budget_s: float = 300.0,
             insider_rows: Sequence[Mapping[str, Any]] = (),
             forge_legs: Mapping[str, Sequence[float]] | None = None) -> dict[str, Any]:
    """One pass of every civilization, inside one budget, writing three artifacts."""
    run = Run(dry_run=dry_run, budget_s=budget_s)
    if not dry_run:
        run.conn = R.connect()
    run.sensors = sensor_bank()
    families: dict[str, Any] = {}
    try:
        families["l1vsun:funding_ecology"] = len(family_funding_ecology(run))
        families["l1vsun:forced_flow"] = len(family_forced_flow(run))
        families["l1vsun:narrative"] = len(family_narrative(run))
        clocks = thesis_clocks()
        families["l1vsun:thesis_clocks"] = clocks["n"]
        families["l1vsun:evidence_verification"] = family_evidence_verification(run)
        families["l1vsun:specialist_discipline"] = len(SPECIALIST_DISCIPLINE)
        attribution = gate_attribution()
        families["bl888m:gate_attribution"] = len(attribution["measured_gates"])
        families["bl888m:bounded_llm"] = dict(LLM_CONTRIBUTION)
        families["primitive:hawkes"] = len(hawkes_discoveries(run))
        families["primitive:insider_breadth"] = len(family_insider_breadth(run, insider_rows))
        families["primitive:multimodal"] = dict(MULTIMODAL_CONTRACT)
        families["forge"] = len(interaction_forge(run, forge_legs))
        families["civilizations"] = civilization_pass(run)
        literature = seed_source_scout(run)
        if not dry_run:
            _atomic(THESIS_CLOCKS, clocks)
            _atomic(GATE_ATTRIBUTION, attribution)
    finally:
        if run.conn is not None:
            run.conn.close()
    report = {
        "generated_at": _now(), "dry_run": dry_run, "budget_s": budget_s,
        "elapsed_s": round(time.monotonic() - run.started, 2),
        "targets": list(TARGETS),
        "mandate": "every family is a SENSOR or MECHANISM for an MT5 instrument; no "
                   "crypto-exchange universe is hunted, scouted, ranked or queued",
        "no_author_monitored": True,
        "access_policy": {
            "pipeline": list(SOURCE_PIPELINE),
            "access_labels": list(ACCESS_LABELS), "credibility": list(CREDIBILITY_LABELS),
            "predictive_states": list(PREDICTIVE_STATES),
            "behaviour": {k: dict(v) for k, v in ACCESS_BEHAVIOUR.items()},
            "evidence_weight": dict(EVIDENCE_WEIGHT),
            "hard_boundary": list(HARD_BOUNDARY),
            "classifier_module": ("libs.research.access_classifier"
                                  if _external_classifier() is not None else UNMEASURED),
            "removed_brakes": ["ACCESS_UNCLEAR quarantine",
                               "machine-extraction veto on PUBLIC_WITH_TERMS and LICENSED"],
            "rule": "access is a surgical router and a provenance label, never a research brake "
                    "(LAWS 5e, 2026-09-23): nothing is discarded for looking risky, "
                    "ACCESS_UNCLEAR is MINED AND TESTED with its label attached, and only "
                    "PRIVATE / CONFIDENTIAL_MNPI / STOLEN_UNAUTHORIZED -- the five refused "
                    "acts -- are recorded as refused with the reason"},
        "seed_nodes": [{k: v for k, v in dict(s).items() if k != "contributes"}
                       for s in SEED_NODES],
        "control_plane": control_plane(),
        "federation": {"module": "libs.research.external_federation",
                       "systems": len(XF.SEEDS), "dispositions": list(XF.DISPOSITIONS),
                       "exhaustion_conditions": list(XF.EXHAUSTION_CONDITIONS),
                       "why": "the roster, the dispositions, the packet contract, the admission "
                              "arithmetic and the exhaustion law are IMPORTED, never restated"},
        "priors": {k: {"published": p.published, "ladder": list(p.rungs()), "unit": p.unit,
                       "why": p.why} for k, p in PRIORS.items()},
        "sensors": {k: v.as_row() for k, v in run.sensors.items()},
        "sensor_gaps": [k for k, v in run.sensors.items() if not v.measured],
        "families": families,
        "specialist_discipline": [dict(d) for d in SPECIALIST_DISCIPLINE],
        "interaction_cells": [dict(c) for c in INTERACTION_CELLS],
        "literature": literature,
        "discoveries_recorded": len(run.discoveries),
        "blocked_descendants": len(run.blocked),
        "notes": run.notes,
        "rule": "published thresholds are PRIORS the genome mutates; a claim is a hypothesis and "
                "is judged by the same ten gates as everything else",
    }
    if not dry_run:
        _atomic(REPORT, report)
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="the source civilizations")
    ap.add_argument("--dry-run", action="store_true", help="plan the pass, write nothing")
    ap.add_argument("--budget-s", type=float, default=300.0)
    a = ap.parse_args(argv)
    rep = run_pass(dry_run=bool(a.dry_run), budget_s=float(a.budget_s))
    print(json.dumps({k: rep[k] for k in ("generated_at", "dry_run", "elapsed_s", "families",
                                          "sensor_gaps", "discoveries_recorded",
                                          "blocked_descendants")}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
