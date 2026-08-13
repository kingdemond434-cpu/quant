"""SURVIVOR BOTTLENECK PANEL -- put the desk's real numbers in front of every seat and argue.

WHY A DEDICATED PANEL. The desk already runs an external panel and a CRO seat, and both ask broad
questions ("what should we do next", "review this module"). Neither has ever been pointed at the
single question that decides whether any of it matters: WHY HAS NOTHING EVER SURVIVED? That
question has a measured answer on this desk, and the measurement is exactly what a panel needs to
stop producing generic advice:

    52 of 350 recorded negatives (14.9%) were powered enough to mean anything.
    239 could not have seen a real edge. 59 record no sample size at all.

A panel handed that number reasons about THIS desk. A panel handed "we have no survivors" writes
an essay about overfitting. So the dossier below is assembled from artifacts, never from prose,
and every figure carries its source path so a seat can call a number wrong -- and so can a reader.

TWO ROUNDS, BECAUSE ONE ROUND IS NOT A PANEL. Round 1 each seat answers alone. Round 2 each seat
reads the OTHERS' answers, anonymised, and is asked to refute them, name which single constraint
actually binds, and say what everyone missed. N independent monologues agree by construction on
whatever is most quotable; a panel that has to disagree surfaces the thing one model saw and the
rest did not. Agreement across FAMILIES is then worth something, because it survived contradiction.

EVERY RECOMMENDATION IS FENCED, and the fence is not advisory. A model asked "how do we get
survivors" has one overwhelmingly easy answer available -- lower the bar -- and it will find it.
`forbidden_direction()` refuses any action that loosens a statistical gate, raises size or
leverage, touches the deadman switch, or selects on results after seeing them. A refused
recommendation is RECORDED with its reason rather than dropped, because the fact that a seat
proposed it is itself information about the seat.

MODEL TEXT IS DATA, NEVER INSTRUCTION. Nothing a seat returns is executed, and nothing here reads
a response as a command. The output is a ranked list of proposals for a person.

Pure logic -- artifact reading is passed in. The organ is scripts/run_survivor_panel.py.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from libs.doctrine.constitution import OBJECTIVE_PREAMBLE
from libs.research.list_order import shuffled_with_log

__all__ = [
    "FORBIDDEN",
    "Proposal",
    "build_dossier",
    "cross_examination_prompt",
    "forbidden_direction",
    "parse_proposals",
    "rank_proposals",
    "round_one_prompt",
]

#: Directions a recommendation may never take, however well argued. Each entry is
#: (regex, why it is refused). The desk's standing constraints, expressed as the shapes a model
#: actually writes them in -- "relax the significance threshold", "increase leverage to 3x".
FORBIDDEN: tuple[tuple[str, str], ...] = (
    # `multiplicity` and `correction` belong here and were MISSING from the first version, which
    # let "relax the multiplicity correction so more cells pass" through as an allowed proposal.
    # That is the purest form of the thing this fence exists to stop: it creates survivors by
    # arithmetic alone, and it is the single most plausible-sounding way to do it.
    (r"\b(lower|loosen|relax|reduce|weaken|drop|ease|soften|widen)\b[^.]{0,40}"
     r"\b(threshold|bar|alpha|significance|p-?value|gate|hurdle|criteri|multiplicity|"
     r"correction|holm|bonferroni|deflat)",
     "loosens a statistical gate -- the one action that manufactures survivors without creating "
     "any edge, and the desk's zero-survivor record is only meaningful while the bar is fixed"),
    (r"\b(raise|increase|higher|more|scale up|lever)\b[^.]{0,40}"
     r"\b(leverage|position size|sizing|exposure|notional|allocation)",
     "raises size or leverage -- refused under the R0143 size fence regardless of the argument"),
    (r"\bdeadman\b|\brun_deadman_switch\b",
     "touches the Tier-3 never-touch deadman switch"),
    # \w* on each adjective: the first version anchored on \bunderperform\b, so
    # "drop the underperforming strategies" -- the way anyone would actually write it -- did not
    # match and was allowed through.
    (r"\b(drop|remove|exclude|discard|filter out|prune|cull)\b[^.]{0,50}"
     r"\b(underperform\w*|losing|los\w+|weak\w*|fail\w*|bad|worst)\b[^.]{0,25}"
     r"\b(strateg|candidate|hypothes|cell|sleeve|column)",
     "selects on results after seeing them -- survivorship by another name, and it produces a "
     "backtest that cannot be wrong"),
    (r"\b(skip|bypass|disable|turn off|remove)\b[^.]{0,40}"
     r"\b(validation|forward|out-?of-?sample|holdout|multiplicity|correction)",
     "removes a validation stage -- Stage B is the desk's ONLY promotion authority"),
)

#: Bottleneck classes a seat is asked to choose between. Named so answers can be COUNTED across
#: seats rather than read one by one -- an unstructured panel produces prose nobody aggregates.
BOTTLENECK_CLASSES: tuple[tuple[str, str], ...] = (
    ("SAMPLE_LENGTH", "not enough observations per hypothesis"),
    ("MULTIPLICITY", "too many hypotheses tested against the same data"),
    ("SIGNAL_ABSENT", "the mechanisms tested genuinely carry no exploitable edge"),
    ("MEASUREMENT", "the harness mismeasures -- alignment, leakage, annualisation, units"),
    ("PLUMBING", "results exist but never reach the stage that could confirm them"),
    ("HORIZON_MISMATCH", "edges are at timescales the data or the screens do not resolve"),
    ("UNIVERSE", "the assets/venues screened exclude where the edge lives"),
    ("COST_MODEL", "edges exist gross but are killed by an over- or under-stated cost"),
    ("DATA_QUALITY", "the inputs are wrong in ways no statistic would reveal"),
    ("OTHER", "something not in this list -- name it"),
)


@dataclass
class Proposal:
    """One seat's concrete proposal, with the fence verdict attached."""

    seat: str
    action: str
    bottleneck: str = ""
    rationale: str = ""
    testable_in_days: float | None = None
    refused: str = ""
    agreed_by: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"seat": self.seat, "action": self.action, "bottleneck": self.bottleneck,
                "rationale": self.rationale[:600],
                "testable_in_days": self.testable_in_days,
                "refused": self.refused, "agreed_by": sorted(set(self.agreed_by)),
                "n_agreeing_seats": len(set(self.agreed_by))}


def forbidden_direction(text: str) -> str:
    """The reason this text is refused, or "". Substring-and-shape matched, deliberately broad.

    A false REFUSAL costs one proposal a person can still read in the record. A false ACCEPT puts
    "relax the significance threshold" on a ranked action list under a heading that says the desk
    is hunting survivors. The asymmetry decides the tuning.
    """
    low = " ".join(str(text).lower().split())
    for pattern, why in FORBIDDEN:
        if re.search(pattern, low):
            return why
    return ""


def _fig(doc: Any, *path: str, default: Any = None) -> Any:
    cur = doc
    for key in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
    return cur if cur is not None else default


def build_dossier(root: Path) -> dict[str, Any]:
    """Every number that bears on the survivor question, with its source path.

    ARTIFACTS ONLY. A dossier written from memory is a dossier that drifts from the desk, and the
    whole value of putting numbers in front of a panel is that they can be checked. Anything
    missing is reported as MISSING with the path, never silently omitted -- a seat reasoning about
    a gap it cannot see gives advice about a desk that does not exist.
    """
    def _read(rel: str) -> Any:
        try:
            return json.loads((root / rel).read_text("utf-8"))
        except (OSError, ValueError):
            return None

    t2 = _read("data/type2_cost.json")
    slots = _read("data/forward_slots.json")
    fwd = _read("web/paper_sleeve_forward.json")
    queue = _read("data/paper_sleeve_queue.json")
    moat = _read("reports/moat_campaign.json")
    missing: list[str] = []
    for rel, doc in (("data/type2_cost.json", t2), ("data/forward_slots.json", slots),
                     ("web/paper_sleeve_forward.json", fwd),
                     ("data/paper_sleeve_queue.json", queue),
                     ("reports/moat_campaign.json", moat)):
        if doc is None:
            missing.append(rel)

    clocks = []
    for name, s in sorted((_fig(fwd, "sleeves", default={}) or {}).items()):
        if not isinstance(s, dict):
            continue
        clocks.append({"clock": name[:64], "trial": str(s.get("trial", ""))[:64],
                       "evidence": s.get("evidence"),
                       "rows_added": s.get("rows_added"),
                       "rows_needed": s.get("n_needed_for_forward_rejection")})

    return {
        "question": ("Why has this desk never produced a survivor -- a hypothesis that cleared "
                     "pre-registered FORWARD evidence and earned capital?"),
        "type2": {
            "source": "data/type2_cost.json",
            "headline": str(_fig(t2, "headline", default="") or _fig(t2, "desk_headline",
                                                                     default=""))[:600],
            "n_negatives": _fig(t2, "counts", "total"),
            "n_powered": _fig(t2, "counts", "powered"),
            "n_underpowered": _fig(t2, "counts", "underpowered"),
        },
        "forward_slots": {
            "source": "data/forward_slots.json",
            "cap": _fig(slots, "cap"), "m_concurrent": _fig(slots, "m_concurrent"),
            "m_upper": _fig(slots, "m_upper"), "idle": _fig(slots, "idle_slots"),
            "accruing": _fig(slots, "accruing"),
        },
        "forward_clocks": clocks[:20],
        "queue_depth": len(_fig(queue, "queued", default=[]) or []),
        "moat": {"source": "reports/moat_campaign.json",
                 "status": _fig(moat, "status"),
                 "blocker": str(_fig(moat, "blocker", default=""))[:300]},
        "missing_artifacts": missing,
        "known_facts": [
            "Stage A (backtest screens) has ZERO promotion authority by law; Stage B (forward "
            "clocks, Holm-corrected, 12 concurrent slots) is the sole promotion authority.",
            "Power to detect a TRUE annualised Sharpe of 3, by campaign shape: N=420/T=310 -> "
            "0.8%; N=126/T=619 -> 4.9%; N=66/T=48 -> 0.0%; N=12/T=5553 -> 100%. Only the last "
            "can honestly report a zero.",
            "Same data, varying only the hypothesis count: N=420 -> 2.1% power, N=48 -> 9.6%, "
            "N=12 -> 24.0%, N=4 -> 46.3%, N=1 -> 83.1%. N is an accident of generation volume, "
            "not a design decision.",
            "The desk's proprietary L2 moat tape is the only dataset it owns that competitors "
            "cannot buy. Its cells carry SECOND-scale horizons: a 30-second cell at |ic| 0.02 "
            "needs ~17,400 bars, which is six days of tape.",
            "Every cheapest-fix the desk's own power model returns is the same shape: MORE "
            "OBSERVATIONS (T=2500), never a looser bar and never fewer hypotheses post hoc.",
        ],
        "constraints_on_answers": [
            "NEVER propose loosening a threshold, alpha, or any statistical gate.",
            "NEVER propose raising leverage or position size.",
            "NEVER propose dropping candidates after seeing their results.",
            "NEVER propose removing a validation stage.",
            "Prefer actions testable within 90 days, and say how many days each needs.",
        ],
    }


def _dossier_text(d: dict[str, Any]) -> str:
    return json.dumps(d, indent=1)[:9000]


def round_one_prompt(dossier: dict[str, Any]) -> tuple[str, str]:
    """(system, user) for the independent round.

    THE MENU IS SHUFFLED PER CALL (R0457). `BOTTLENECK_CLASSES` is a hardcoded tuple, so
    `SAMPLE_LENGTH` led this list on every run this panel has ever done, and
    `run_survivor_panel.py` TALLIES `bottleneck_votes` across seats -- a cross-seat vote count on a
    fixed-order menu. arXiv 2509.08713 measured 100% metric-ordering dependence in exactly this
    shape, so an unshuffled tally cannot distinguish "the seats agree" from "the seats all read the
    same first line". The permutation is logged, which is what makes the sensitivity measurable
    rather than merely removed.
    """
    ordered, _perm = shuffled_with_log(
        BOTTLENECK_CLASSES, organ="survivor_panel", field="bottleneck_classes")
    classes = "\n".join(f"  {k} -- {v}" for k, v in ordered)
    system = (
        OBJECTIVE_PREAMBLE + "\n"
        "You are a seat on a quantitative research desk's bottleneck panel. You are handed the "
        "desk's REAL measured artifacts. Your job is root-cause analysis, not encouragement and "
        "not a literature review.\n\n"
        "Rules that are not negotiable:\n"
        "- Never propose loosening a threshold, alpha, significance bar or any statistical gate. "
        "That manufactures survivors without creating edge and it will be automatically refused.\n"
        "- Never propose raising leverage or position size.\n"
        "- Never propose dropping candidates after seeing their results.\n"
        "- Prefer what is FALSIFIABLE within 90 days over what is merely true.\n"
        "- If the evidence does not support a confident answer, say which measurement would "
        "settle it. 'Collect X and the answer follows' is a better answer than a guess.\n\n"
        "Answer in STRICT JSON, no prose outside it:\n"
        '{"primary_bottleneck": "<one class>", "confidence": 0.0-1.0, '
        '"why": "<=150 words citing the numbers you used>", '
        '"proposals": [{"action": "<imperative, specific>", "bottleneck": "<class>", '
        '"rationale": "<=80 words>", "testable_in_days": <number>}], '
        '"what_the_numbers_do_not_show": "<the gap you would need filled>"}')
    user = (f"BOTTLENECK CLASSES:\n{classes}\n\n"
            f"THE DESK'S MEASURED STATE:\n{_dossier_text(dossier)}\n\n"
            "Give 3-6 proposals. Rank them yourself by expected value per unit of desk effort.")
    return system, user


def cross_examination_prompt(dossier: dict[str, Any],
                             others: list[tuple[str, str]]) -> tuple[str, str]:
    """(system, user) for round two -- the seat argues with its anonymised colleagues.

    ANONYMISED ON PURPOSE. A seat told which model produced an answer rates the brand as much as
    the argument, and this panel exists to find the claim one model can defend and the rest
    cannot -- not to poll reputations.
    """
    system = (
        OBJECTIVE_PREAMBLE + "\n"
        "You are the same seat, now in cross-examination. Below are the other seats' answers, "
        "anonymised. Do NOT summarise them and do NOT try to be agreeable.\n\n"
        "Your job:\n"
        "1. REFUTE. Name at least one specific claim that is wrong or unsupported by the "
        "evidence, and say exactly why. If you genuinely cannot fault any, say so and explain "
        "what would have to be true for that to be the case.\n"
        "2. DECIDE. Which SINGLE constraint actually binds first? If it were removed tomorrow, "
        "would the next one make a survivor possible or merely move the wall?\n"
        "3. FIND THE GAP. What did every seat, including you, miss?\n\n"
        "The same non-negotiable rules apply: no loosened gates, no added leverage, no post-hoc "
        "selection.\n\n"
        "STRICT JSON only:\n"
        '{"refutations": [{"claim": "<quoted>", "why_wrong": "<=60 words>"}], '
        '"binding_constraint": "<one class>", "would_removing_it_produce_a_survivor": '
        '"yes|no|moves-the-wall", "why": "<=120 words>", '
        '"everyone_missed": "<=100 words>", '
        '"proposals": [{"action": "...", "bottleneck": "...", "rationale": "...", '
        '"testable_in_days": <number>}]}')
    # SEAT ORDER IS SHUFFLED TOO (R0457), and it is the same bias one level up: `others` arrives in
    # roster order, which is stable across runs, so the SAME model was SEAT A every week while this
    # prompt asks the reader to REFUTE a specific claim and then DECIDE. Position 1 gets refuted or
    # adopted disproportionately. `run_external_panel.py:538` already fixed exactly this for the
    # CRO's inbox and the fix was never propagated here.
    shuffled_others, _seat_perm = shuffled_with_log(
        list(others), organ="survivor_panel", field="round_two_seat_order")
    blocks = "\n\n".join(f"--- SEAT {chr(65 + i)} ---\n{txt[:2600]}"
                         for i, (_name, txt) in enumerate(shuffled_others))
    user = (f"THE DESK'S MEASURED STATE:\n{_dossier_text(dossier)}\n\n"
            f"THE OTHER SEATS SAID:\n{blocks}")
    return system, user


def _json_blob(text: str) -> dict[str, Any] | None:
    """The first JSON object in a response. Models fence it, prefix it, or apologise around it."""
    raw = str(text or "")
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, flags=re.S)
    if fence:
        try:
            got = json.loads(fence.group(1))
        except ValueError:
            got = None
        if isinstance(got, dict):
            return got
    start = raw.find("{")
    while start != -1:
        depth, i, in_str, esc = 0, start, False, False
        while i < len(raw):
            ch = raw[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        got = json.loads(raw[start:i + 1])
                    except ValueError:
                        break
                    return got if isinstance(got, dict) else None
            i += 1
        start = raw.find("{", start + 1)
    return None


def parse_proposals(seat: str, text: str) -> tuple[list[Proposal], dict[str, Any]]:
    """(proposals, the seat's structured answer). A response that will not parse is NOT dropped.

    An unparseable answer is recorded with its raw head, because "the seat replied and we could
    not read it" and "the seat said nothing" are different facts, and treating the first as the
    second is how a panel silently shrinks to whichever models format well.
    """
    doc = _json_blob(text)
    if doc is None:
        return [], {"seat": seat, "parse": "FAILED",
                    "why": ("response carried no parseable JSON object -- recorded, not dropped: "
                            "an unreadable answer is not an absent one"),
                    "raw_head": str(text or "")[:400]}
    out: list[Proposal] = []
    for p in doc.get("proposals") or []:
        if not isinstance(p, dict):
            continue
        action = str(p.get("action") or "").strip()
        if not action:
            continue
        days = p.get("testable_in_days")
        out.append(Proposal(
            seat=seat, action=action[:400],
            bottleneck=str(p.get("bottleneck") or doc.get("primary_bottleneck") or "")[:40],
            rationale=str(p.get("rationale") or "")[:600],
            testable_in_days=float(days) if isinstance(days, (int, float)) else None,
            refused=forbidden_direction(f"{action} {p.get('rationale', '')}")))
    return out, {"seat": seat, "parse": "OK",
                 "primary_bottleneck": str(doc.get("primary_bottleneck")
                                           or doc.get("binding_constraint") or "")[:40],
                 "confidence": doc.get("confidence"),
                 "why": str(doc.get("why") or "")[:900],
                 "refutations": doc.get("refutations") or [],
                 "would_removing_it_produce_a_survivor":
                     doc.get("would_removing_it_produce_a_survivor"),
                 "everyone_missed": str(doc.get("everyone_missed") or "")[:700],
                 "what_the_numbers_do_not_show":
                     str(doc.get("what_the_numbers_do_not_show") or "")[:700]}


_STOP = frozenset({"the", "a", "an", "of", "to", "and", "or", "in", "on", "for", "with", "at",
                   "by", "from", "into", "over", "per", "is", "are", "be", "that", "this", "it",
                   "run", "use", "add", "more", "data", "desk"})


def _key(action: str) -> frozenset[str]:
    words = re.findall(r"[a-z0-9_]{4,}", str(action).lower())
    return frozenset(w for w in words if w not in _STOP)


def rank_proposals(proposals: list[Proposal]) -> list[Proposal]:
    """Merge near-duplicates across seats, then rank by cross-seat agreement and speed.

    AGREEMENT IS THE SIGNAL, and only because round two forced disagreement first. Two seats
    landing on the same action after each was asked to refute the other is evidence; two seats
    agreeing in parallel monologues is a shared prior. Speed breaks ties, because a proposal
    testable in 30 days is worth more than a better one testable in 900.
    """
    merged: list[Proposal] = []
    for p in proposals:
        if p.refused:
            continue
        k = _key(p.action)
        hit = None
        for m in merged:
            other = _key(m.action)
            if k and other and len(k & other) / len(k | other) >= 0.5:
                hit = m
                break
        if hit is None:
            p.agreed_by = [p.seat]
            merged.append(p)
            continue
        hit.agreed_by = [*hit.agreed_by, p.seat]
        if (p.testable_in_days or 1e9) < (hit.testable_in_days or 1e9):
            hit.testable_in_days = p.testable_in_days
    return sorted(merged, key=lambda m: (-len(set(m.agreed_by)),
                                         m.testable_in_days if m.testable_in_days else 1e9,
                                         m.action))
