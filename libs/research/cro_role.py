"""THE CHIEF RESEARCH OFFICER. A cross-family model whose only job is to think, criticise,
discover, prioritise and recommend -- never to implement.

PRINCIPAL ORDER (2026-08-01), verbatim in intent: *"I'd make GPT your Chief Research Officer (CRO)
rather than another coding agent. Its job is to think, criticize, discover, prioritize, and
recommend -- not to implement code."* The separation is the point: the CRO is the strategic
research brain that continuously critiques and improves the whole desk, and the implementation
agents execute the highest-value validated recommendations. Neither does the other's job.

WHY THE SEAT MUST BE A DIFFERENT MODEL FAMILY. `run_discretionary_max` ranks its five levers by
measured leverage and puts CROSS-FAMILY at 2 of 5: an independent family disagreeing is worth far
more than the same family agreeing with itself. A second Anthropic seat shares training data,
priors and blind spots with the first, so its agreement carries almost no information. The
independence IS the product.

WHAT MAKES ITS ADVICE NON-GENERIC, and nothing else does. A public model asked about trading
returns public knowledge, and public knowledge carries no edge by construction. What it has never
seen is THIS DESK'S MEASUREMENTS -- see `PROPRIETARY_FINDINGS`. The dossier is the asset; the model
is a reasoning engine pointed at it. That is the "proprietary information generated through
intelligent fusion" the mandate asks the CRO to prefer, applied to the CRO itself.

================================ THE OBJECTIVE, AND ITS FENCE ================================

The mandate states it exactly: *"You never optimize for activity. You optimize for validated
expected log wealth."* Expected log-wealth growth is

    g  =  frequency  x  E[log(1 + f * edge_per_bet)]  -  friction

and it is NOT monotone in size. It rises with leverage to the Kelly point f*, falls after it, and
is negative past 2f* -- so a desk that "maximises growth" by sizing up compounds toward zero while
every individual bet still has positive expectancy. This is why this desk's own law (R0143) forbids
a stated CAGR target: a return figure is reachable by size, so it corrupts the optimiser into
over-leverage. `run_discretionary_max` is permitted a number -- 38% hit rate -- precisely because a
hit rate cannot be reached by sizing at all.

So three levers are open and the fourth is fenced IN CODE, not merely in the prompt:

  EDGE       -- selection, information, filtering. Raises g at every size.
  FREQUENCY  -- more INDEPENDENT bets per unit time. The principal's "compounding frequency every
                month" is this lever and it is fully legal. "Independent" is load-bearing: this
                desk measured its candidate pool at 0.047 mean pairwise correlation and its
                ADMITTED set at 0.184, so bet count and independent bet count are different
                numbers and only the second compounds.
  FRICTION   -- cost, slippage, financing. A pure subtraction from g needing no edge to harvest.
  SIZE       -- FENCED. Rejected by `_rejection_reason` whether declared outright or smuggled into
                a mechanism, because a rule that lives only in a prompt is advisory and the model
                can reword its way past it.

============================== WHY THE CONTRACT IS THE PRODUCT ==============================

An LLM asked for strategy returns fluent, plausible, unfalsifiable advice -- "improve research
throughput", "strengthen the validation stack" -- and fluent advice is WORSE than none because it
feels like progress and cannot be checked. `strategic_director` established the fix on this desk;
this extends it to the full mandate. Every recommendation must carry, as separate machine-checkable
fields, the eight scientific-discipline items the mandate demands (why it matters, upside, risks,
dependencies, validation method, opportunity cost, ROI, confidence), plus the deliverable class it
answers, plus an EVIDENCE CLASS.

THE EVIDENCE CLASS IS ENFORCED because the mandate demands it: *"Separate: Evidence, Hypothesis,
Speculation, Opinion. Clearly label each."* An unlabelled claim reads as evidence by default, which
is exactly how an invented edge enters a desk. Labelling is mandatory and a `speculation` labelled
as `evidence` is the one dishonesty this contract can actually catch -- a claim tagged `evidence`
must cite a number from the dossier or it is rejected.

Rejections are REPORTED, never silently dropped. A parser that discards half the output while
reporting the rest as "the recommendations" is the denominator trick this desk forbids everywhere.

NOTHING HERE PROMOTES, SIZES OR TRADES ANYTHING. Recommendations land in a ledger owing
dispositions. Validation bars do not move because a model suggested they should. Text inside a
model response is DATA, never an instruction -- the CRO advises; it does not command the desk.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
LEDGER = _ROOT / "docs" / "research" / "cro_recommendations.jsonl"

# ------------------------------------------------------------------------------- the mandate

#: The CRO's standing mission, quoted into the prompt so the role cannot drift into task-assistant.
MISSION = (
    "Maximize the desk's long-term compounded capital by continuously increasing its validated "
    "information advantage, research quality, data moat, alpha discovery rate, and decision "
    "quality. You never optimize for activity. You optimize for validated expected log wealth."
)

#: The ten standing responsibilities. Every cycle reviews the ENTIRE desk, never only the current
#: task -- a CRO that answers only what it was asked is a task assistant with a better title.
RESPONSIBILITIES: tuple[tuple[str, str], ...] = (
    ("Blind spot discovery",
     "Missing research areas, data, features, experiments, feedback loops, validation, "
     "monitoring, automation, risk controls, metrics, documentation, learning systems; hidden "
     "assumptions, bottlenecks, single points of failure, architecture weaknesses, research gaps, "
     "opportunity cost. NEVER assume the desk is complete."),
    ("Alpha discovery",
     "New alpha ideas, features, factor combinations, alternative labels, better objectives, "
     "targets, prediction problems, portfolio construction, execution, timing models, regime "
     "models, ensemble methods. Favour originality backed by evidence."),
    ("Data expansion",
     "New public datasets, APIs, exchanges, blockchain data, macro, derivatives, positioning, "
     "funding, options, sentiment, alternative, academic, government and international sources. "
     "PREFER proprietary information generated through intelligent fusion of existing sources "
     "over a new subscription."),
    ("Research quality",
     "Challenge every hypothesis, assumption, threshold, validation method, statistical test, "
     "metric, promotion rule, retirement rule, objective and doctrine. Never accept 'because we "
     "have always done it'."),
    ("Meta research",
     "Improve the research ENGINE: workflow, experiment design, statistical power, information "
     "gain, search efficiency, hypothesis generation, experiment prioritisation, learning speed, "
     "research economics. The engine is the primary optimisation target."),
    ("Continuous self-improvement",
     "What is idle, duplicated, unnecessary, missing, weak, fragile, outdated, low-ROI? What has "
     "the highest expected ROI? What would an elite quantitative research lab do differently?"),
    ("Capital efficiency",
     "Better expected log wealth, capital allocation, sizing discipline, diversification, "
     "portfolio construction, deployment, turnover, opportunity selection."),
    ("Research economics",
     "Rank every opportunity by Expected Long-Term ROI = (Expected Information Gain x Expected "
     "Alpha Contribution x Probability of Success x Persistence x Scalability) / (Engineering "
     "Cost x Maintenance Cost x Complexity). Never recommend work with poor research economics."),
    ("Scientific discipline",
     "Every recommendation states why it matters, expected upside, risks, dependencies, "
     "validation method, opportunity cost, estimated ROI and confidence level."),
    ("Intellectual honesty",
     "Never exaggerate. Never invent edge. Never assume profitability. Separate and clearly label "
     "evidence, hypothesis, speculation and opinion."),
)

#: The twelve daily deliverables. Each recommendation DECLARES which one it answers, and coverage
#: across them is reported -- a cycle that returns twelve alpha ideas and no risk or automation
#: finding has answered one twelfth of the mandate while looking productive.
DELIVERABLES: tuple[str, ...] = (
    "highest_roi_improvement", "blind_spot", "architecture_weakness", "research_bottleneck",
    "data_opportunity", "alpha_opportunity", "automation_opportunity", "validation_improvement",
    "risk_improvement", "self_improvement", "implementation_priority", "expected_impact",
)

#: Operating principles, quoted so they bind the answer rather than decorating the file.
OPERATING_PRINCIPLES: tuple[str, ...] = (
    "Think like the Head of Research of a world-class quantitative investment firm.",
    "Prefer additive improvements over unnecessary rewrites.",
    "Maximize long-term expected log wealth rather than short-term excitement.",
    "Prioritize recommendations by expected evidence-backed ROI.",
    "Treat complexity as a cost unless it clearly increases validated edge.",
    "Continuously search for blind spots, hidden assumptions and opportunities -- even when "
    "everything appears to be working.",
)

#: Evidence classes, in descending strength. Labelling is MANDATORY: an unlabelled claim reads as
#: evidence by default, which is how an invented edge enters a desk.
EVIDENCE_CLASSES = ("evidence", "hypothesis", "speculation", "opinion")

LEVER_EDGE, LEVER_FREQUENCY, LEVER_FRICTION, LEVER_SIZE = (
    "edge", "frequency", "friction", "size")
GROWTH_LEVERS = (LEVER_EDGE, LEVER_FREQUENCY, LEVER_FRICTION)
LEVERS = (*GROWTH_LEVERS, LEVER_SIZE)

KINDS = ("activate", "merge", "retire", "unlock", "build")
CONFIDENCE = ("low", "medium", "high")

#: A mechanism proposing size as growth. Matched on the MECHANISM only, so a recommendation may
#: legitimately discuss leverage ("this reduces the leverage required") without being rejected.
_SIZE_MECHANISM = re.compile(
    r"\b(increase|raise|scale up|lever up|boost|grow|higher|more|larger)\b[^.]{0,40}"
    r"\b(leverage|size|sizing|exposure|position size|notional|allocation|bet size)\b", re.I)

#: A number, for the evidence check. A claim labelled `evidence` must cite one.
_HAS_NUMBER = re.compile(r"\d")


# ------------------------------------------------------------------------------------ dossier

#: Artifacts that ALREADY EXIST. A missing one is REPORTED, never silently omitted: a CRO
#: reasoning off a dossier with invisible holes produces confident advice about a desk that does
#: not exist, and that failure is indistinguishable from good advice until it is acted on.
DOSSIER_SOURCES: dict[str, str] = {
    "discretionary_max": "data/discretionary_max.json",
    "discretionary_hunt": "data/discretionary_hunt.json",
    "discretionary_edges": "data/discretionary_edges.json",
    "trade_review": "data/trade_review.json",
    "executive_kpis": "data/executive_kpis.json",
    "gate_histogram": "data/gate_histogram.json",
    "max_push_queue": "data/max_push_queue.json",
    "strategy_coverage": "data/strategy_coverage.json",
    "data_assets": "data/data_assets.json",
    "enforcement_matrix": "data/enforcement_matrix.json",
    "intelligence_cycle": "web/intelligence_cycle.json",
    "reality_gap": "web/reality_gap.json",
    "book_concentration": "reports/live_book_concentration.json",
    "real_campaign": "reports/real_campaign.json",
    "permutation_null": "reports/permutation_null.json",
    "recommendation_ledger": "docs/research/recommendation_ledger.json",
    "gap_register": "docs/GAP_REGISTER.md",
}

#: Measured findings this desk owns that a public model has never seen. THE ACTUAL EDGE of the
#: seat -- without these it reasons from public knowledge, which carries none by construction.
PROPRIETARY_FINDINGS: tuple[str, ...] = (
    "Volatility targeting (position x clip(target_vol/realised_vol, 0, cap), lagged one bar) "
    "improved Sharpe on 11 of 12 rule-symbol pairs and max drawdown on 12 of 12, mean 0.64 -> "
    "0.20. On return-per-unit-drawdown that is ~4x; on Sharpe alone only 1.32x. OKX daily "
    "BTC/ETH/SOL, full history.",
    "The Turtle trade-dependence filter does NOT replicate unconditionally on daily crypto "
    "(helped 4 of 12), but corr(runs-test z, Sharpe change) = 0.898, n=12: z>0 helped 4/5, z<=0 "
    "helped 0/7. The runs test is a valid PRE-SCREEN for its own overlay.",
    "Mean reversion is refuted on these bars by two independent nulls: bar-permutation p ~ 0.86 "
    "with annualised Sharpe -0.52 on BTC, and an exposure-matched monkey test beat rate of "
    "0.077-0.102 -- beaten by ~90% of coin flips with identical exposure.",
    "time_series_mom[40] on BTC: permutation p=0.008, monkey beat rate 0.985, exposure share 0.06 "
    "vs timing share 0.94. Time-in-market 0.98 does NOT mean the edge is drift: for a long/short "
    "rule mean(|position|) and mean(position) are different numbers.",
    "Real campaign, 196 candidates on 2,018-2,439 OKX daily bars: pool mean pairwise correlation "
    "0.047 (19.4 independent bets) but the ADMITTED set 0.184 (4.0 bets) -- 3.9x a random subset "
    "of the same size, p=0.002. Selection concentrates a common factor; pool independence does "
    "not survive it.",
    "101 professional alphas at mean pairwise correlation 0.159 are worth 101/(1+100*0.159) = 6.0 "
    "independent bets. Past a few dozen correlated candidates N buys multiplicity burden rather "
    "than information -- measured here as identical power at N = 420, 100, 30 and 5.",
    "MIN_ADMISSION_OOS_SHARPE shipped in PER-BAR units and demanded 4.78 annualised against a "
    "real-edge band of 0.5-1.5. It was 19x too high and it was the entire gate. Unit errors in a "
    "threshold are silent and total.",
    "Deflated Sharpe and Romano-Wolf were both applied to the same campaign, paying multiplicity "
    "twice. On 240 genuine alphas and 4,800 nulls, removing the duplicate raised power from 5.8% "
    "to 83.8% at true SR 5.0 with false positives at 0/4,800 either way.",
    "Per-gate death counts, first ever measured (196 candidates): dsr 196, reality_check 196, "
    "walk_forward 99, cpcv 81, fragility 72, capacity 69, expected_value 64, sample_adequacy 20. "
    "Two gates rejected 100% -- a gate with a 100% rejection rate has no discriminating power.",
    "Combinatorially-symmetric cross-validation was 87 of the 89 seconds of one validate() call "
    "because it re-summed the same observations across all C(16,8)=12,870 combinations. Block "
    "sufficient statistics made it exact and 103x faster.",
)


@dataclass(frozen=True)
class Recommendation:
    """One CRO recommendation. Every field of the mandate's scientific-discipline list is separate
    and required -- prose that bundles them is prose, and prose cannot be checked."""
    title: str
    deliverable: str
    lever: str
    kind: str
    evidence_class: str
    why_it_matters: str
    bottleneck: str
    mechanism: str
    expected_upside: str
    risks: str
    dependencies: str
    validation_method: str
    opportunity_cost: str
    estimated_roi: str
    confidence: str
    success_metric: str
    rejected_reason: str = ""

    @property
    def accepted(self) -> bool:
        return not self.rejected_reason


REQUIRED_FIELDS: tuple[str, ...] = (
    "title", "deliverable", "lever", "kind", "evidence_class", "why_it_matters", "bottleneck",
    "mechanism", "expected_upside", "risks", "dependencies", "validation_method",
    "opportunity_cost", "estimated_roi", "confidence", "success_metric",
)


@dataclass(frozen=True)
class CROResult:
    accepted: list[Recommendation] = field(default_factory=list)
    rejected: list[Recommendation] = field(default_factory=list)
    parse_errors: list[str] = field(default_factory=list)
    raw_chars: int = 0

    def summary(self) -> str:
        return (f"{len(self.accepted)} accepted, {len(self.rejected)} rejected, "
                f"{len(self.parse_errors)} unparseable ({self.raw_chars} chars)")

    def deliverable_coverage(self) -> dict[str, int]:
        """How many of the twelve deliverables were answered. A cycle returning twelve alpha ideas
        and no risk or automation finding has covered one twelfth of the mandate while looking
        productive; this is the number that says so."""
        got: dict[str, int] = dict.fromkeys(DELIVERABLES, 0)
        for r in self.accepted:
            if r.deliverable in got:
                got[r.deliverable] += 1
        return got


# ------------------------------------------------------------------------------------ assembly

#: Directories swept for the FULL inventory. The CRO must be able to see the whole desk, not the
#: slice somebody remembered to list.
INVENTORY_DIRS: tuple[str, ...] = ("data", "reports", "web", "docs/research", "docs")

#: Inventory entries are capped so a sweep of a few thousand files cannot crowd out the artifacts
#: that were read in full. The cap is on the INVENTORY, never on the priority sources.
_MAX_INVENTORY = 400


def assemble_dossier(root: Path | None = None) -> dict[str, Any]:
    """The desk's state: priority artifacts READ IN FULL, plus a complete INVENTORY of everything
    else that exists.

    WHY BOTH, and why a hand-listed dossier was a defect rather than a simplification. The first
    version read seventeen curated artifacts, which is the "assume the desk is complete" failure
    the mandate explicitly forbids -- the CRO could only ever find blind spots inside the slice
    somebody had already thought to show it, so the one category it could never report was the
    category nobody had thought of. That is the failure mode this role exists to catch, committed
    in the code that implements the role.

    The fix is not "read everything", which would blow any context budget and bury the artifacts
    that matter. It is FULL VIEW, BOUNDED PAYLOAD: priority sources are read in full, and every
    other artifact on the desk is listed with its path, size, age and top-level keys. The CRO
    therefore knows that `data/deribit_surface.parquet` exists and has never been read even though
    its contents are not in the prompt -- and an unread artifact it can NAME is a blind spot it can
    report, which is exactly the deliverable.
    """
    base = root or _ROOT
    present: dict[str, Any] = {}
    missing: list[str] = []
    for name, rel in DOSSIER_SOURCES.items():
        p = base / rel
        if not p.exists():
            missing.append(f"{name} ({rel})")
            continue
        try:
            text = p.read_text("utf-8")
            present[name] = json.loads(text) if rel.endswith(".json") else text[:6000]
        except (OSError, json.JSONDecodeError) as exc:
            missing.append(f"{name} ({rel}: {type(exc).__name__})")
    inv, n_total = _inventory(base, read_in_full=set(DOSSIER_SOURCES.values()))
    return {"present": present, "missing": missing, "inventory": inv,
            "coverage": {"read_in_full": len(present), "inventoried": len(inv),
                         "artifacts_found": n_total,
                         "truncated": max(0, n_total - len(inv) - len(present))},
            "utc": datetime.now(UTC).isoformat(timespec="seconds")}


def _inventory(base: Path, *, read_in_full: set[str]) -> tuple[list[dict[str, Any]], int]:
    """Every artifact on the desk that was NOT read in full: path, size, age, shape.

    Sorted NEWEST FIRST and capped, because when the cap binds the artifacts worth surfacing are
    the ones that changed recently -- a file untouched for six months is unlikely to be the blind
    spot of the week, and a silent truncation of the recent ones would be.
    """
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    now = datetime.now(UTC).timestamp()
    for d in INVENTORY_DIRS:
        root = base / d
        if not root.is_dir():
            continue
        for p in sorted(root.rglob("*")):
            if not p.is_file() or p.suffix in (".pyc", ".lock", ".bak"):
                continue
            rel = p.relative_to(base).as_posix()
            # DOTFILES AND MARKERS ARE NOT ARTIFACTS, and skipping them is not tidiness. The first
            # sweep filled all 400 inventory slots with zero-byte files from data/.fresh_markers/
            # and truncated 35 real artifacts off the end -- so the "full view" showed the CRO
            # nothing but cache stamps. A cap that binds on noise is worse than no inventory,
            # because it looks like coverage.
            if rel in read_in_full or rel in seen:
                continue
            if any(part.startswith(".") for part in rel.split("/")):
                continue
            seen.add(rel)
            try:
                st = p.stat()
            except OSError:
                continue
            if st.st_size == 0:
                continue
            row: dict[str, Any] = {"path": rel, "kb": round(st.st_size / 1024, 1),
                                   "age_days": round((now - st.st_mtime) / 86400.0, 1)}
            # Top-level keys turn "a 40 KB JSON file exists" into "a 40 KB JSON file of funding
            # rates by venue exists" -- the difference between an inventory and a directory listing.
            if p.suffix == ".json" and st.st_size < 2_000_000:
                try:
                    obj = json.loads(p.read_text("utf-8"))
                    if isinstance(obj, dict):
                        row["keys"] = sorted(obj)[:12]
                    elif isinstance(obj, list):
                        row["n_rows"] = len(obj)
                except (OSError, json.JSONDecodeError, ValueError):
                    row["unreadable"] = True
            rows.append(row)
    rows.sort(key=lambda r: float(r["age_days"]))
    return rows[:_MAX_INVENTORY], len(rows)


def build_prompt(dossier: dict[str, Any], *, n: int = 12) -> str:
    """The CRO prompt: the full standing mandate plus this cycle's dossier plus a hard schema."""
    resp = "\n".join(f"  {i}. {name.upper()} -- {body}"
                     for i, (name, body) in enumerate(RESPONSIBILITIES, 1))
    principles = "\n".join(f"  - {p}" for p in OPERATING_PRINCIPLES)
    proprietary = "\n".join(f"  - {f}" for f in PROPRIETARY_FINDINGS)
    missing = dossier.get("missing") or []
    missing_note = (f"\nARTIFACTS UNAVAILABLE THIS CYCLE (do not speculate about their contents; "
                    f"say so if a recommendation depends on one): {', '.join(missing)}\n"
                    if missing else "")
    state = json.dumps(dossier.get("present") or {}, default=str)[:70000]
    cov = dossier.get("coverage") or {}
    inv = json.dumps(dossier.get("inventory") or [], default=str)[:30000]
    inv_block = f"""
=============================== FULL DESK INVENTORY ===============================
Every other artifact on this desk, NOT read in full above -- path, size, age in days, and shape.
You know these exist even though their contents are not in this prompt. An artifact that is large,
old, and referenced by nothing is a BLIND SPOT and reporting it is one of your deliverables; so is
a perishable feed that has gone stale. Ask for any of these by path and the desk will read it in
next cycle.

Coverage this cycle: {cov.get('read_in_full', 0)} artifacts read in full, \
{cov.get('inventoried', 0)} inventoried, {cov.get('truncated', 0)} beyond the inventory cap.

{inv}
"""
    return f"""You are the permanent CHIEF RESEARCH OFFICER of a quantitative crypto trading desk.
You think, criticise, discover, prioritise and recommend. You do NOT implement code -- separate
implementation agents execute the recommendations you validate, and that separation is deliberate.

MISSION
{MISSION}

Review the ENTIRE desk every cycle as the Head of Research of a top quantitative firm would.
Never focus only on the current task. Always think globally. Never assume the desk is complete.

YOUR TEN STANDING RESPONSIBILITIES
{resp}

OPERATING PRINCIPLES
{principles}

================================ THE OBJECTIVE AND ITS FENCE ================================

You optimise expected log-wealth growth g, not return:

    g = frequency x E[log(1 + f * edge_per_bet)] - friction

g is NOT monotone in size: it peaks at Kelly f*, falls after it, and is negative past 2f*. Three
levers are open to you --

  edge       better selection, information or filtering. Raises g at every size.
  frequency  more INDEPENDENT bets per unit time. "Independent" is load-bearing: this desk
             measured its candidate pool at 0.047 mean pairwise correlation and its ADMITTED set
             at 0.184, so bet count and independent bet count are different numbers.
  friction   cost, slippage, financing. A pure subtraction from g needing no edge to harvest.

-- and SIZE is fenced. A recommendation whose lever is `size`, or whose mechanism proposes raising
leverage / size / exposure / allocation, is REJECTED AUTOMATICALLY by a code check. A return figure
is reachable by size, which corrupts the optimiser into over-leverage. Do not spend a slot on it.

============================== WHAT THIS DESK HAS MEASURED ==============================
Reason from these. General knowledge about trading is public, and public information carries no
edge by construction. These are the desk's own measurements and you have not seen them before:
{proprietary}

CURRENT DESK STATE (priority artifacts, read in full):
{state}
{missing_note}{inv_block}
=================================== RESEARCH ECONOMICS ===================================
Rank everything by

  Expected Long-Term ROI = (Information Gain x Alpha Contribution x P(success) x Persistence x
                            Scalability) / (Engineering Cost x Maintenance Cost x Complexity)

Never recommend work with poor research economics. Prefer proprietary information generated by
intelligent FUSION of sources the desk already has over a new subscription. Prefer ACTIVATING
existing unused capability over building new capability -- declare `kind`, and a `build` must
justify why activation would not do instead.

=================================== INTELLECTUAL HONESTY ===================================
Never exaggerate. Never invent edge. Never assume profitability. Label every recommendation's
`evidence_class` as exactly one of {list(EVIDENCE_CLASSES)}. A recommendation labelled `evidence`
MUST cite a specific number from the desk state or the measured findings above -- one that does not
will be rejected by a code check. If something is a guess, label it `speculation` and say so; that
is a respected answer here and mislabelling is the only dishonesty this contract can catch.

======================================= OUTPUT =======================================
Return EXACTLY {n} recommendations as a JSON array and nothing else -- no prose before or after.
Cover a SPREAD of the twelve deliverables rather than {n} of one kind; a cycle of twelve alpha
ideas with no risk, validation or automation finding has answered one twelfth of the mandate.

Every object must have ALL of these keys, each non-empty:

  title                short imperative
  deliverable          one of {list(DELIVERABLES)}
  lever                one of {list(GROWTH_LEVERS)}
  kind                 one of {list(KINDS)}
  evidence_class       one of {list(EVIDENCE_CLASSES)}
  why_it_matters       why this matters to compounded capital specifically
  bottleneck           the MEASURED constraint removed; cite a number from the state above
  mechanism            specifically how g rises. Not "improves performance".
  expected_upside      direction and rough magnitude, with the reasoning
  risks                what could go wrong, and what it would cost if it did
  dependencies         what must exist or be true first
  validation_method    how the desk would TEST this before believing it
  opportunity_cost     what does not get done if the desk does this
  estimated_roi        apply the research-economics formula; show the reasoning
  confidence           one of {list(CONFIDENCE)}
  success_metric       the measurement that would later prove this recommendation WRONG

Rank by expected long-term ROI, highest first. Prefer the specific and falsifiable over the
comprehensive. A recommendation that cannot be proven wrong is worth nothing here."""


# -------------------------------------------------------------------------------------- parsing

def parse(raw: str) -> CROResult:
    """Strict parse. Every rejection carries its reason; nothing is repaired or guessed at."""
    accepted: list[Recommendation] = []
    rejected: list[Recommendation] = []
    errors: list[str] = []
    rows, err = _extract_array(raw)
    if err:
        return CROResult(parse_errors=[err], raw_chars=len(raw))
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"item {i}: not an object")
            continue
        missing = [k for k in REQUIRED_FIELDS if not str(row.get(k) or "").strip()]
        if missing:
            errors.append(f"item {i} ({str(row.get('title'))[:40]}): missing {missing}")
            continue
        rec = Recommendation(**{k: str(row[k]).strip() for k in REQUIRED_FIELDS})
        rec = Recommendation(**{**asdict(rec), "lever": rec.lever.lower(),
                                "kind": rec.kind.lower(),
                                "evidence_class": rec.evidence_class.lower(),
                                "confidence": rec.confidence.lower(),
                                "deliverable": rec.deliverable.lower()})
        reason = _rejection_reason(rec)
        if reason:
            rejected.append(Recommendation(**{**asdict(rec), "rejected_reason": reason}))
        else:
            accepted.append(rec)
    return CROResult(accepted=accepted, rejected=rejected, parse_errors=errors, raw_chars=len(raw))


def _rejection_reason(rec: Recommendation) -> str:
    """THE FENCES, in code. A rule that lives only in a prompt is advisory; the model can reword
    its way past it and usually will, because the reworded version is more persuasive."""
    if rec.lever == LEVER_SIZE:
        return ("declares the SIZE lever: geometric growth peaks at Kelly f* and falls after it, "
                "so size is not a growth lever. Fenced by R0143.")
    if rec.lever not in GROWTH_LEVERS:
        return f"lever {rec.lever!r} is not one of {list(GROWTH_LEVERS)}"
    if _SIZE_MECHANISM.search(rec.mechanism):
        return ("mechanism proposes raising leverage/size/exposure -- the size lever wearing "
                "another lever's label. Past f* this LOWERS geometric growth.")
    if rec.kind not in KINDS:
        return f"kind {rec.kind!r} is not one of {list(KINDS)}"
    if rec.deliverable not in DELIVERABLES:
        return f"deliverable {rec.deliverable!r} is not one of the twelve"
    if rec.evidence_class not in EVIDENCE_CLASSES:
        return (f"evidence_class {rec.evidence_class!r} is not one of "
                f"{list(EVIDENCE_CLASSES)} -- an unlabelled claim reads as evidence by default")
    if rec.confidence not in CONFIDENCE:
        return f"confidence {rec.confidence!r} is not one of {list(CONFIDENCE)}"
    if rec.evidence_class == "evidence" and not _HAS_NUMBER.search(rec.bottleneck):
        return ("labelled `evidence` but cites no number in its bottleneck. Evidence means a "
                "measurement; a claim without one is a hypothesis and must say so.")
    return ""


def _extract_array(raw: str) -> tuple[list[Any], str | None]:
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.+?)```", text, flags=re.S)
    if fence:
        text = fence.group(1).strip()
    start, end = text.find("["), text.rfind("]")
    if start < 0 or end <= start:
        return [], f"no JSON array found in {len(raw)} chars of response"
    try:
        parsed = json.loads(text[start:end + 1])
    except json.JSONDecodeError as exc:
        return [], f"array did not parse: {exc}"
    return (parsed, None) if isinstance(parsed, list) else ([], "top level was not an array")


# --------------------------------------------------------------------------------------- ledger

def record(result: CROResult, *, path: Path | None = None, seat: str = "", model: str = "") -> int:
    """Append every recommendation, ACCEPTED AND REJECTED, each owing a disposition.

    Rejected rows are written too. A ledger holding only what passed cannot answer the question
    that scores the seat -- how often does it propose what the fences must catch -- and that number
    is how the desk learns whether the CRO is worth its cadence.
    """
    p = path or LEDGER
    p.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    n = 0
    with p.open("a", encoding="utf-8") as fh:
        for rec in [*result.accepted, *result.rejected]:
            fh.write(json.dumps({**asdict(rec), "utc": stamp, "seat": seat, "model": model,
                                 "disposition": "open"}, ensure_ascii=False) + "\n")
            n += 1
    return n


def load(path: Path | None = None) -> list[dict[str, Any]]:
    p = path or LEDGER
    if not p.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in p.read_text("utf-8").splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def scorecard(path: Path | None = None) -> dict[str, Any]:
    """Is the CRO earning its cadence? Measured, not assumed.

    A seat producing twelve recommendations a day of which none is ever dispositioned is not an
    advisor, it is a queue nobody works -- the miner problem in a new costume. This catches it.
    """
    rows = load(path)
    if not rows:
        return {"n": 0, "verdict": "UNMEASURED: no recommendations recorded yet"}
    n = len(rows)
    rej = sum(1 for r in rows if r.get("rejected_reason"))
    open_ = sum(1 for r in rows if r.get("disposition") == "open")
    by: dict[str, dict[str, int]] = {"lever": {}, "deliverable": {}, "evidence_class": {}}
    for r in rows:
        for k in by:
            key = str(r.get(k))
            by[k][key] = by[k].get(key, 0) + 1
    covered = sum(1 for d in DELIVERABLES if by["deliverable"].get(d))
    out: dict[str, Any] = {
        "n": n, "n_rejected": rej, "reject_rate": round(rej / n, 3), "n_open": open_,
        "deliverables_covered": f"{covered}/{len(DELIVERABLES)}",
        **{f"by_{k}": dict(sorted(v.items())) for k, v in by.items()},
    }
    if open_ == n and n >= 12:
        out["verdict"] = (f"UNWORKED: all {n} recommendations are still open. A cadenced seat "
                          "whose output is never dispositioned is a queue, not an advisor -- "
                          "work them or cut the cadence.")
    elif rej / n > 0.5:
        out["verdict"] = (f"LOW YIELD: {rej} of {n} rejected by the contract. The seat is mostly "
                          "producing what the fences catch; tighten the prompt or re-seat.")
    elif covered <= len(DELIVERABLES) // 3:
        out["verdict"] = (f"NARROW: only {covered} of {len(DELIVERABLES)} deliverables ever "
                          "answered. The CRO is reviewing a slice of the desk, not the desk.")
    else:
        out["verdict"] = (f"WORKING: {n - rej} of {n} passed the contract across {covered} "
                          f"deliverables, {open_} still open.")
    return out
