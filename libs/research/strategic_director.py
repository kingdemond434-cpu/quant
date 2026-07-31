"""STRATEGIC DIRECTOR -- a runtime ROLE with an enforced output contract (RANK 3).

The principal was explicit: *"not as another dormant doctrine document."* So this is not prose about
strategy. It is three mechanical things -- an input dossier assembled from artifacts that already
exist, a prompt, and an OUTPUT CONTRACT that is validated in code -- wired into the intelligence
cycle, with every accepted recommendation written to the recommendation ledger so §41 forces a
disposition. A recommendation that lands in the ledger cannot be quietly forgotten; that is the
whole difference between this and a document.

WHY THE CONTRACT IS THE PRODUCT. An LLM asked for strategy returns fluent, plausible, unfalsifiable
advice -- "improve research throughput", "strengthen the validation stack" -- and fluent advice is
worse than none because it FEELS like progress and cannot be checked. So a recommendation is
REJECTED here unless it names, as separate fields: the measurable bottleneck it removes, the
expected impact, the opportunity cost, and a success metric. Those four are exactly what turn advice
into something that can later be judged wrong. Parsing is strict and rejections are reported, never
silently dropped.

THE PRIORITY RULE IS ENFORCED, NOT REQUESTED. *"Find unused capability BEFORE inventing new
capability"* is in the prompt, but a rule that lives only in a prompt is advisory -- the model can
ignore it and usually will, because proposing new construction is more rhetorically satisfying than
proposing activation. So every recommendation must DECLARE its ``kind`` (activate / merge / retire /
unlock / build), and when the dormancy report shows unused capabilities, a ``build`` recommendation
is rejected unless it carries an explicit ``why_not_activation``. Enforcing on a declared field
rather than on keyword-sniffing the prose is what makes this robust: the model cannot dodge it by
rewording, and the desk's actual measured state (171 dormant capabilities on 2026-07-30) is what
sets the bar.

ACTIVATION-READY BY CONSTRUCTION. Execution is blocked on OpenRouter credit -- the same 402 that
blocks the panel and ``llm_code_auditor.py``. Everything here except the network call is pure and
tested, so when credit lands nothing is redesigned: the dossier assembles, the prompt builds, the
contract validates, the ledger commands emit. ``scripts/run_strategic_director.py --dry-run`` proves
the whole path today without spending a cent, and that is deliberately the default when no key
exists.

Pure stdlib. Import from ``libs.research.strategic_director``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]

#: The dossier. Artifacts that ALREADY EXIST -- the queue's constraint, and why this needs no new
#: collection. A missing one is reported as missing, never silently omitted: a director reasoning
#: off a dossier with invisible holes is GAP_REGISTER #77 in a new costume.
DOSSIER_SOURCES: dict[str, str] = {
    "dormancy": "web/intelligence_cycle.json",
    "data_registry": "data/data_assets.json",
    "enforcement_matrix": "data/enforcement_matrix.json",
    "gate_histogram": "data/gate_histogram.json",
    "reality_gap": "web/reality_gap.json",
    "desk_brief": "data/executive_kpis.json",
    "execution_intel": "web/execution_intel.json",
    "moat_audit": "data/moat_quality.json",
    "recommendation_ledger": "docs/research/recommendation_ledger.json",
}

#: A recommendation's disposition kind. ``build`` is last on purpose: it is what the priority rule
#: constrains, because it grows the surface the desk already fails to wire.
KIND_ACTIVATE = "activate"
KIND_MERGE = "merge"
KIND_RETIRE = "retire"
KIND_UNLOCK = "unlock"
KIND_BUILD = "build"
KINDS = (KIND_ACTIVATE, KIND_MERGE, KIND_RETIRE, KIND_UNLOCK, KIND_BUILD)

#: The four fields that separate a judgeable recommendation from fluent advice.
REQUIRED_FIELDS = ("bottleneck", "expected_impact", "opportunity_cost", "success_metric")

#: Below this many characters a required field is boilerplate, not an answer. "improves things" is
#: 15 characters and says nothing.
MIN_FIELD_CHARS = 25


@dataclass
class Dossier:
    """What the director is allowed to reason from, and what was missing when it did."""

    present: dict[str, Any] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)
    dormant_count: int = 0

    @property
    def complete(self) -> bool:
        return not self.missing

    def summary(self) -> str:
        return (f"{len(self.present)}/{len(DOSSIER_SOURCES)} artifacts present, "
                f"{self.dormant_count} dormant capabilities")


@dataclass
class Recommendation:
    """One judgeable proposal. Every field here exists so it can later be shown to be wrong."""

    title: str
    kind: str
    bottleneck: str
    expected_impact: str
    opportunity_cost: str
    success_metric: str
    why_not_activation: str = ""
    roi_bps: float | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "title": self.title, "kind": self.kind, "bottleneck": self.bottleneck,
            "expected_impact": self.expected_impact, "opportunity_cost": self.opportunity_cost,
            "success_metric": self.success_metric,
            "why_not_activation": self.why_not_activation, "roi_bps": self.roi_bps,
        }


@dataclass
class Rejection:
    title: str
    reason: str


@dataclass
class DirectorResult:
    accepted: list[Recommendation] = field(default_factory=list)
    rejected: list[Rejection] = field(default_factory=list)
    dossier_summary: str = ""

    @property
    def n_seen(self) -> int:
        return len(self.accepted) + len(self.rejected)


def assemble_dossier(root: Path | None = None) -> Dossier:
    """Read the existing artifacts. Missing ones are NAMED, not skipped."""
    root = root or _ROOT
    d = Dossier()
    for name, rel in sorted(DOSSIER_SOURCES.items()):
        p = root / rel
        try:
            d.present[name] = json.loads(p.read_text("utf-8"))
        except (OSError, ValueError):
            d.missing.append(f"{name} ({rel})")
    cyc = d.present.get("dormancy")
    if isinstance(cyc, dict):
        for cap in cyc.get("capabilities", []):
            if isinstance(cap, dict) and cap.get("capability") == "dormancy_hunter":
                rep = cap.get("report")
                if isinstance(rep, dict):
                    counts = rep.get("counts")
                    if isinstance(counts, dict):
                        d.dormant_count = int(sum(int(v) for v in counts.values()))
                    elif isinstance(rep.get("dormant"), list):
                        d.dormant_count = len(rep["dormant"])
    return d


def build_prompt(dossier: Dossier) -> str:
    """The director's instruction. States the contract AND the priority rule the code enforces."""
    dormant = dossier.dormant_count
    return f"""You are the desk's STRATEGIC DIRECTOR. Produce ranked recommendations, as JSON only.

YOUR CHARTER, and why your seat exists at all: you are the INDEPENDENT MODEL FAMILY. Every other
reasoning organ on this desk is Claude, so the desk's self-review shares one set of priors and one
set of blind spots. Your job is to see what the desk cannot see about itself -- agreeing with the
desk's own framing is your failure mode, not your deliverable. Challenge assumptions by name.

AGGRESSION IS LAW HERE, not mood (constitution L1.21a/L1.28, binding on you too): timidity is a
scored defect of the same class as a blown risk limit. Size, cost, effort and ambition carry ZERO
weight against expected ROI -- never recommend the smaller version because it feels safer, and
never withhold a recommendation because it is a lot of work. The one thing this does NOT loosen:
statistical bars and survival rails are immutable (L2.8a); aggression in scope, never in evidence.

UNKNOWN-UNKNOWNS DUTY (L1.9, every cycle): at least ONE recommendation must name something the
desk neither measures nor lists -- a market behaviour, data asymmetry, failure mode or capability
class absent from the dossier AND from the gap register. "Everything important is already on the
register" is the claim you exist to attack; if you genuinely find nothing, say what you searched
and why it came up empty, which is itself evidence.

MEASURED STATE: {dossier.summary()}.
{"MISSING FROM YOUR DOSSIER: " + ", ".join(dossier.missing) if dossier.missing else ""}

THE PRIORITY RULE, and it is enforced in code, not merely requested here:
FIND UNUSED CAPABILITY BEFORE INVENTING NEW CAPABILITY. This desk has {dormant} capabilities that
are BUILT and never execute. Authoring capability number {dormant + 1} while {dormant} sit
disconnected is negative-ROI by the desk's own arithmetic. A recommendation with kind="build" is
REJECTED AUTOMATICALLY unless it also supplies "why_not_activation" explaining why no existing
capability can be wired to do the job.

OUTPUT CONTRACT. A JSON array. Every element MUST have all of:
  title              short, specific
  kind               one of {list(KINDS)}
  bottleneck         the MEASURABLE constraint this removes -- name the metric and its value now
  expected_impact    what changes, quantified, with a direction
  opportunity_cost   what does NOT get done because this does
  success_metric     the number that will later show this worked or failed
  why_not_activation required only for kind="build"
  roi_bps            optional numeric estimate

Each of the four required prose fields must exceed {MIN_FIELD_CHARS} characters of real content.
"Improves research throughput" is not a bottleneck; "0 of 434 tested candidates reached Stage B,
so the binding constraint is the promotion gate, not idea supply" is.

Rank by (bottleneck severity x tractability). Do not pad the list -- three judgeable
recommendations beat ten unfalsifiable ones. Return ONLY the JSON array."""


def _field_ok(v: Any) -> bool:
    return isinstance(v, str) and len(v.strip()) >= MIN_FIELD_CHARS


def parse_recommendations(raw: str, dossier: Dossier) -> DirectorResult:
    """Validate the model's output against the contract AND the priority rule.

    Strict on purpose. Every rejection is recorded with its reason, because a director whose bad
    output is silently discarded looks identical to one that produced nothing -- and the desk would
    have no way to tell a credit problem from a quality problem.
    """
    res = DirectorResult(dossier_summary=dossier.summary())
    text = raw.strip()
    # models wrap JSON in prose or fences however they like; find the array
    if "```" in text:
        parts = [p for p in text.split("```") if "[" in p]
        text = parts[0] if parts else text
        text = text.split("\n", 1)[-1] if text.lstrip().startswith(("json", "JSON")) else text
    start, end = text.find("["), text.rfind("]")
    if start < 0 or end <= start:
        res.rejected.append(Rejection("<whole response>",
                                      "no JSON array found -- the output contract requires a JSON "
                                      "array and prose cannot be validated or ledgered"))
        return res
    try:
        items = json.loads(text[start:end + 1])
    except ValueError as e:
        res.rejected.append(Rejection("<whole response>", f"unparseable JSON: {e}"))
        return res
    if not isinstance(items, list):
        res.rejected.append(Rejection("<whole response>", "top-level JSON is not an array"))
        return res

    for raw_item in items:
        if not isinstance(raw_item, dict):
            res.rejected.append(Rejection("<non-object>", "array element is not an object"))
            continue
        title = str(raw_item.get("title") or "<untitled>").strip()
        kind = str(raw_item.get("kind") or "").strip().lower()

        if kind not in KINDS:
            res.rejected.append(Rejection(title, f"kind {kind!r} is not one of {list(KINDS)}; the "
                                                 "priority rule is enforced on this field, so an "
                                                 "undeclared kind cannot be accepted"))
            continue
        bad = [f for f in REQUIRED_FIELDS if not _field_ok(raw_item.get(f))]
        if bad:
            res.rejected.append(Rejection(
                title, f"missing or boilerplate required field(s): {bad}. Each needs >"
                       f"{MIN_FIELD_CHARS} chars of real content -- these four are what make a "
                       "recommendation judgeable rather than fluent advice"))
            continue
        why = str(raw_item.get("why_not_activation") or "").strip()
        # THE PRIORITY RULE, enforced. Only bites when there is genuinely unused capability.
        if kind == KIND_BUILD and dossier.dormant_count > 0 and len(why) < MIN_FIELD_CHARS:
            res.rejected.append(Rejection(
                title, f"kind='build' with {dossier.dormant_count} capabilities already built and "
                       "unwired, and no why_not_activation given. Find unused capability BEFORE "
                       "inventing new capability -- authoring another subsystem while these sit "
                       "disconnected is negative-ROI by the desk's own arithmetic"))
            continue
        roi = raw_item.get("roi_bps")
        res.accepted.append(Recommendation(
            title=title, kind=kind,
            bottleneck=str(raw_item["bottleneck"]).strip(),
            expected_impact=str(raw_item["expected_impact"]).strip(),
            opportunity_cost=str(raw_item["opportunity_cost"]).strip(),
            success_metric=str(raw_item["success_metric"]).strip(),
            why_not_activation=why,
            roi_bps=float(roi) if isinstance(roi, (int, float)) else None))
    return res


def to_ledger_commands(res: DirectorResult, *,
                       source: str = "strategic_director") -> list[list[str]]:
    """``scripts/recommendations.py add`` argv per accepted recommendation.

    Routing through the ledger is what makes this a role rather than a report: §41 then forces every
    row to reach IMPLEMENTED / REJECTED / SCHEDULED, and an undisposed row past its grace window is
    a DEFECT rather than backlog. A director whose output nobody had to answer for would be a
    document with extra steps.
    """
    out = []
    for r in res.accepted:
        summary = (f"[{r.kind}] {r.title} -- BOTTLENECK: {r.bottleneck} "
                   f"| IMPACT: {r.expected_impact} | COST: {r.opportunity_cost} "
                   f"| SUCCESS: {r.success_metric}")
        argv = ["add", "--source", source, "--summary", summary]
        if r.roi_bps is not None:
            argv += ["--roi-bps", str(r.roi_bps)]
        out.append(argv)
    return out


def rank(recs: Sequence[Recommendation]) -> list[Recommendation]:
    """Activation before authoring, then by declared ROI.

    The ordering encodes the same rule the parser enforces: an ``activate``/``merge`` recommendation
    outranks a ``build`` one at equal ROI, because the desk's demonstrated failure mode is building
    capability faster than it wires it.
    """
    order = {k: i for i, k in enumerate(KINDS)}
    return sorted(recs, key=lambda r: (order.get(r.kind, 99), -(r.roi_bps or 0.0)))


def director_report(res: DirectorResult, dossier: Dossier) -> Mapping[str, Any]:
    return {
        "dossier": {"present": sorted(dossier.present), "missing": dossier.missing,
                    "dormant_count": dossier.dormant_count},
        "n_seen": res.n_seen,
        "accepted": [r.to_json() for r in rank(res.accepted)],
        "rejected": [{"title": x.title, "reason": x.reason} for x in res.rejected],
        "contract": {"required_fields": list(REQUIRED_FIELDS), "kinds": list(KINDS),
                     "min_field_chars": MIN_FIELD_CHARS},
    }
