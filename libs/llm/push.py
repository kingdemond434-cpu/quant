"""THE PUSH LADDER -- exhaust a seat's inventory instead of accepting its first answer.

THE OBSERVATION (principal, 2026-07-31, and it is correct): these models -- GPT most obviously,
but all of them -- generate MORE when pushed. A short "is that everything? maximise it further,
what is left?" reliably produces additional high-value items the first answer omitted, because
the first answer is shaped by an implicit sense of "a reasonable amount to say", not by the
model's actual inventory. The desk was harvesting one answer per seat per call and throwing away
the rest of what each seat knew.

PUSH UNTIL IT ACTUALLY GIVES UP, NOT A FIXED NUMBER OF TIMES. Ten rungs are supplied, but the
stopping rule is EXHAUSTION, measured: a round that adds nothing genuinely new ends the ladder.
That distinction is the whole design. A fixed count either stops while the model still has
material (wasted inventory) or keeps paying for paraphrases (throughput without information --
the exact mode collapse batch_diversity() exists to catch). Novelty is measured per round against
everything already said, so "it gave up" is a number, not a guess.

WHY IT IS CHEAP, STATED HONESTLY. The expensive half of a call is the INPUT: a ~40k-char mission
plus dossier, graveyard and rulings. A push reuses all of it -- same conversation,
prompt-cache-eligible, nothing re-sent -- so round N costs only its OUTPUT tokens. Genuinely
cheap, but NOT free, and on high-effort reasoning models output is the pricier side. Honest
expectation: an exhausting ladder costs roughly 2-3x a single call and typically yields 3-6x the
distinct usable items. Not "barely any extra credits" -- rather, the best marginal use of credits
available on this desk, which is a stronger claim and a true one.

WHY THE LADDER ESCALATES RATHER THAN REPEATING. Asking "anything else?" ten times gets "no,
that's it" by round two: a repeated question reads as a signal that the model has finished. Each
rung therefore attacks a DIFFERENT suppression mechanism -- self-censorship, ranking pressure,
missing context, adversarial framing, inversion, constraint removal, cross-domain transfer,
time-horizon shift, second-order effects, and finally forced ranking of everything produced.
"""

from __future__ import annotations

import re

__all__ = [
    "COMPOUNDING_FILTER",
    "GENERATION_LADDER",
    "MAX_ROUNDS",
    "MIN_NOVELTY",
    "PUSH_LADDER",
    "PushResult",
    "build_turns",
    "novelty",
    "push_rounds",
]

#: Hard ceiling on rounds. Exhaustion normally stops the ladder well before this; the cap exists
#: so a model that hallucinates novelty forever cannot bill indefinitely.
MAX_ROUNDS = 10

#: A round must contribute at least this fraction of genuinely new content tokens or the model is
#: treated as exhausted. 0.15 is deliberately low: late rounds are SHORTER (the easy material is
#: gone) and a strict bar would cut the ladder exactly where the rare items live. Being too
#: generous costs one extra round; being too strict costs the item the whole ladder was for.
MIN_NOVELTY = 0.15

#: APPENDED TO EVERY RUNG. The ladder's own risk, named and closed.
#:
#: Exhausting a seat over ten rounds produces a LOT of suggestions, and the later rungs
#: deliberately ask what to stop, what breaks, and what adapts against us. Left unguarded that is
#: a machine for breeding timidity: round after round of "add a check", "reduce exposure", "be
#: careful here", each individually reasonable, collectively a desk that compounds slower. A push
#: ladder that makes the desk more conservative would be worse than no ladder at all, because it
#: would arrive dressed as thoroughness.
#:
#: So every item must name its COMPOUNDING PATH, and exactly three qualify. The third is not a
#: loophole for caution -- it is the log objective itself: a ruin event ends all future
#: compounding, so preventing one is the single most growth-positive act available. That
#: asymmetry is WHY maximum aggression on proven edge and zero aggression on unproven edge are
#: the same rule, not a compromise between two.
COMPOUNDING_FILTER = (
    "\n\nBEFORE YOU ANSWER -- THE COMPOUNDING FILTER, applied to every single item you propose. "
    "Each one must name which of exactly THREE paths it takes to long-run compounded capital: "
    "(1) it raises E[log(wealth)] NOW; (2) it raises the desk's CAPABILITY to raise E[log(wealth)] "
    "later -- more alpha discovered per unit time, more un-replicable data, better measurement; "
    "or (3) it prevents a RUIN event, which is the strongest growth argument there is because "
    "ruin ends all future compounding. If an item takes none of those three paths, DELETE IT and "
    "do not mention it. "
    "Anything that is merely tidier, more cautious, more 'best practice', more governed, or "
    "'safer' without naming path (3) explicitly is TIMIDITY, and timidity is a scored defect here "
    "-- it costs compounded capital exactly as a risk breach does, only invisibly. Do not "
    "recommend a smaller number than the evidence supports. Do not round down out of caution. Do "
    "not propose a control whose purpose is to feel careful. "
    "The two limits that DO bind: survival rails (ruin probability <=2%, never loosened, never "
    "traded for return) and PROVEN EDGE (size only on demonstrated edge -- the null is "
    "no-edge-until-evidence). Inside those two, be maximally aggressive and say so."
)

#: ANALYSIS ladder -- panel audits, strategic review, data recommendations, code review.
PUSH_LADDER: tuple[str, ...] = (
    "Is that everything? Name what you left out because it seemed too obvious, too expensive, "
    "too weird, or outside what you assumed I wanted. Cost is a DECISION for the principal, "
    "never a constraint you apply silently -- if an idea needs money, propose it anyway with the "
    "number attached." + COMPOUNDING_FILTER,

    "Now the highest-ROI items you have NOT yet said. New material only -- restating anything "
    "above in different words is a failed round. Rank strictly by expected effect on COMPOUNDED "
    "CAPITAL, and for each state the cost, what it displaces, and the falsifier that would prove "
    "it was the wrong call." + COMPOUNDING_FILTER,

    "Context you did not have: this desk's single un-replicable asset is ~4.4GB of order-book "
    "data captured at its OWN timestamps, scoring 5130x the next-best source on its own "
    "information-advantage ranking -- and it sits at 0.4% coverage with ZERO mechanisms tested. "
    "It has 0 deployed alphas and a validated-discovery rate of 0.00 per 45 days. Its last "
    "campaign ran 420 candidates for zero survivors, and relaxing the gates was MEASURED to "
    "promote nobody. Given that, what changes in your answer, and what did you miss?"
    + COMPOUNDING_FILTER,

    "Adversarially: what would a competitor with the same data find that you did not? What is "
    "the weakest claim you made above, and what would a hostile reviewer say about it?"
    + COMPOUNDING_FILTER,

    "Invert it. What should the desk STOP doing, delete, or refuse to build -- so the freed "
    "effort goes into GROWTH? Effort is conserved: every addition displaces something. Name the "
    "highest-value REMOVAL, say exactly what it frees, and what that buys in compounded capital. "
    "Removals that merely simplify are not interesting; removals that redirect effort toward "
    "alpha or un-replicable data are. Do NOT propose removing a survival rail."
    + COMPOUNDING_FILTER,

    "Remove the constraints. If budget, compute, headcount and time were 10x, what becomes worth "
    "doing that is not worth doing today? Then tell me which of those is ALREADY worth doing at "
    "1x and is only being skipped out of habit or false economy." + COMPOUNDING_FILTER,

    "Cross-domain transfer: what do market-making desks, high-frequency firms, insurance "
    "underwriters, sports-betting syndicates, ad-auction teams or epidemiologists do about this "
    "class of problem that a crypto research desk typically does not? Name the transferable "
    "mechanism, not the analogy." + COMPOUNDING_FILTER,

    "Shift the horizon. What compounds over 3 YEARS that looks worthless over 3 months? Option "
    "value, irreversibility, data that only accrues with calendar time, capability that unlocks "
    "other capability. What is the desk failing to START today purely because it pays late?"
    + COMPOUNDING_FILTER,

    "Second-order effects on your top 3: what gets crowded, what adapts against us, what does "
    "each make HARDER later? Then -- and this is the point -- say how to capture the edge ANYWAY: "
    "faster, earlier, at a different horizon, or on data others do not have. The answer to 'this "
    "decays' is to harvest it BEFORE it does, never to skip it. Which of the three survives, and "
    "what is the aggressive version of each?" + COMPOUNDING_FILTER,

    "Final. Rank EVERYTHING you have produced across all rounds by expected effect on compounded "
    "capital -- one ordered list, no ties, no tiers. State THE ONE THING the desk should do in "
    "the next 24 hours and why it beats every alternative. If you genuinely have nothing further "
    "of value to add, say exactly: NOTHING FURTHER." + COMPOUNDING_FILTER,
)

#: GENERATION ladder -- hypotheses. Same escalation, but every rung re-asserts the output
#: contract: a pushed model drifts toward prose, and a hypothesis without a mechanism, a test and
#: a kill condition is not a hypothesis.
GENERATION_LADDER: tuple[str, ...] = (
    "More. Same format, same hard rules -- NAME | MECHANISM | DATA SOURCE | TEST | KILL "
    "CONDITION, one per line. Give the ones you held back because they seemed too obvious, too "
    "hard to test, or too far from conventional crypto research. Nothing repeated."
    + COMPOUNDING_FILTER,

    "Now the ones a competitor would find and you did not offer. Push into FORCED FLOWS and HARD "
    "STRUCTURAL BARRIERS specifically -- on this desk every forecast-style hypothesis has died "
    "and every surviving candidate has been a spread with a hard constraint. Same format."
    + COMPOUNDING_FILTER,

    "This desk owns ~4.4GB of order-book snapshots taken at its OWN timestamps -- resting depth, "
    "queue dynamics, replenishment after liquidity withdrawal, per-venue microstructure nobody "
    "else has in this form -- and has tested ZERO mechanisms on it. Generate hypotheses ONLY "
    "testable with data like that, i.e. ones a competitor without it cannot run. Same format."
    + COMPOUNDING_FILTER,

    "Take your strongest mechanism above and BREED it: recombine with a different dataset, a "
    "different horizon bucket, a different market regime, a different structural relationship. A "
    "validated mechanism recombined beats a fresh invention. Same format." + COMPOUNDING_FILTER,

    "Who is FORCED to trade badly, and when? Margin calls, redemption gates, index rebalances, "
    "collateral swaps, mandate limits, liquidation cascades, token unlocks, validator exits, "
    "settlement windows, quarter-end. The counterparty with no choice is the most reliable edge "
    "source there is. Same format." + COMPOUNDING_FILTER,

    "Where do two prices for the SAME risk fail to converge because of a hard barrier -- licence, "
    "capital control, settlement delay, collateral incompatibility, custody, KYC, geography, "
    "time zone? Soft frictions arbitrage away; hard ones persist. Same format."
    + COMPOUNDING_FILTER,

    "What is publicly observable but expensive or awkward to MEASURE, such that most participants "
    "use a crude proxy? The edge is in measuring the real quantity while others trade the proxy. "
    "Same format." + COMPOUNDING_FILTER,

    "Take three signals that are known and crowded. For each, what is its DERIVATIVE, its "
    "DISPERSION, its PERSISTENCE, or its FAILURE MODE -- and is that untested? Crowded first "
    "moments often hide uncrowded second ones. Same format." + COMPOUNDING_FILTER,

    "What would only work in a REGIME that is not the current one -- a liquidity crisis, a depeg, "
    "an exchange failure, a funding blowout, a chain halt? Pre-registering the hypothesis before "
    "the regime arrives is the only way to trade it without fitting it afterwards. Same format."
    + COMPOUNDING_FILTER,

    "Final. Of everything you generated across all rounds, which 5 have the HIGHEST prior of "
    "surviving a gauntlet of walk-forward, CPCV, capacity, fragility and cost realism -- and why? "
    "If you have nothing further of value, say exactly: NOTHING FURTHER." + COMPOUNDING_FILTER,
)

#: Explicit surrender signals. Checked before novelty so a model that says it is done is believed
#: immediately rather than billed for one more round to prove it.
_DONE = ("nothing further", "no further", "nothing more to add", "nothing else to add",
         "i have nothing", "that is everything", "that's everything", "exhausted the")

_WORD = re.compile(r"[a-z0-9]+")
#: Tokens too common to indicate novelty. Kept short on purpose -- an aggressive stop-list would
#: make paraphrases look novel, which defeats the exhaustion test.
_STOP = frozenset((
    "the", "a", "an", "and", "or", "of", "to", "in", "is", "it", "that", "this", "for", "on"
    + COMPOUNDING_FILTER,
    "with", "as", "by", "at", "be", "are", "not", "but", "if", "then", "than", "from", "you"
    + COMPOUNDING_FILTER,
    "your", "we", "our", "can", "will", "would", "should", "could", "may", "its", "has", "have"
    + COMPOUNDING_FILTER,
))


def _tokens(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if len(w) > 3 and w not in _STOP}


def novelty(new_text: str, seen: set[str]) -> float:
    """Fraction of `new_text`'s content tokens not already present in `seen` (0.0 .. 1.0).

    Token-level rather than semantic on purpose: it is deterministic, free, and needs no second
    model call. It over-credits a genuine paraphrase that uses different words -- but that error
    costs one extra round, whereas an embedding call per round would cost money on every round
    forever and add a dependency to a hot path.
    """
    toks = _tokens(new_text)
    if not toks:
        return 0.0
    return len(toks - seen) / len(toks)


class PushResult:
    """Everything the ladder produced, plus WHY it stopped -- so a short run is auditable.

    `stop_reason` matters as much as the text. "exhausted after 4 rounds" and "hit the round cap"
    are opposite diagnoses: the first says the seat was drained, the second says MAX_ROUNDS is
    now the binding constraint and should probably rise.
    """

    __slots__ = ("novelties", "rounds", "stop_reason", "text", "texts")

    def __init__(self, texts: list[str], novelties: list[float], stop_reason: str) -> None:
        self.texts = texts
        self.novelties = novelties
        self.stop_reason = stop_reason
        self.rounds = max(0, len(texts) - 1)
        self.text = "\n".join(t for t in texts if t.strip())

    def __repr__(self) -> str:  # pragma: no cover - diagnostic only
        return (f"PushResult(rounds={self.rounds}, stop={self.stop_reason!r}, "
                f"novelty={[round(n, 2) for n in self.novelties]})")


def build_turns(system: str, user: str) -> list[dict[str, str]]:
    """Opening conversation. Separate so callers can inspect or extend before sending."""
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def push_rounds(ask, system: str, user: str, *,
                ladder: tuple[str, ...] = PUSH_LADDER,
                max_rounds: int = MAX_ROUNDS,
                min_novelty: float = MIN_NOVELTY) -> PushResult:
    """Ask, then push until the model is EXHAUSTED, it surrenders, or the cap binds.

    `ask(messages) -> str` is supplied by the caller so this stays transport-agnostic and
    dependency-free: every organ here posts to the same endpoint with a different token budget,
    and none should have to move to share this.

    THREE STOP CONDITIONS, in priority order:
      1. SURRENDER  -- the model says it has nothing further. Believed immediately; paying for a
                       round to confirm a "no" is pure waste.
      2. EXHAUSTION -- the round's novelty falls below `min_novelty`. The model is recycling, and
                       recycled text is throughput without information.
      3. CAP        -- `max_rounds` reached. Recorded distinctly, because hitting the cap means
                       the LIMIT stopped the ladder, not the model, and the cap should probably
                       rise. A ladder that always ends at the cap is a ladder that is too short.

    A FAILED PUSH NEVER LOSES THE ANSWER. If round 6 times out, rounds 0-5 are returned intact.
    Losing completed output because a follow-up failed would make pushing strictly worse than not
    pushing, which guarantees it gets switched off.
    """
    n = max(0, min(int(max_rounds), len(ladder)))
    msgs = build_turns(system, user)
    first = ask(msgs)
    if not (first or "").strip():
        return PushResult([""], [0.0], "opening call returned nothing -- not pushed")

    texts = [first]
    novelties = [1.0]
    seen = _tokens(first)
    stop = f"cap: {n} round(s)"

    for i in range(n):
        msgs = [*msgs, {"role": "assistant", "content": texts[-1]},
                {"role": "user", "content": ladder[i]}]
        try:
            nxt = ask(msgs)
        except Exception as e:
            stop = f"push {i + 1} failed ({type(e).__name__}) -- prior rounds kept"
            break
        if not (nxt or "").strip():
            stop = f"empty response at round {i + 1}"
            break
        low = nxt.strip().lower()
        if any(d in low for d in _DONE) and len(low) < 400:
            stop = f"model surrendered at round {i + 1}"
            texts.append(nxt)
            novelties.append(novelty(nxt, seen))
            break
        nov = novelty(nxt, seen)
        texts.append(nxt)
        novelties.append(nov)
        seen |= _tokens(nxt)
        if nov < min_novelty:
            stop = f"exhausted at round {i + 1} (novelty {nov:.0%} < {min_novelty:.0%})"
            break
    return PushResult(texts, novelties, stop)
