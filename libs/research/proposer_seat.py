"""THE PROPOSER SEAT: an optional external model that proposes CANDIDATES, never verdicts.

WHAT THIS IS AND WHY IT IS SAFE TO HAVE. Every generator on this desk invents inside a typed
grammar it was handed by whoever wrote it -- the expression factory draws random trees from
`alpha_grammar`, mathlab's traditions enumerate their own object shapes, `model_search` walks six
representations and ten families. Those grammars are complete in the sense that anything the desk
can TRADE is expressible in them, and radically incomplete in the sense that the SKELETONS worth
drawing are a vanishing subset nobody has enumerated. A language model has read more strategy
descriptions than this desk will ever crawl, so it is a cheap prior over which skeletons and which
mechanism names are worth a trial.

IT IS A PRIOR AND NOTHING ELSE, and that is the whole design:

  * NO VERDICT LEAVES THIS MODULE. A proposal carries a shape and a name; it never carries a
    score, a p-value, a t-statistic, an expected return, a rank, a promotion or a certificate.
    Any such field in a model's reply is STRIPPED and the strip is recorded -- a model that
    volunteers "sharpe 2.4, promote" has its numbers deleted and its skeleton kept, because the
    skeleton is the only part it is competent to supply. `verdict_leak` is the test of this.
  * PROPOSALS ENTER THE POPULATION AS ORDINARY CANDIDATES. An accepted skeleton goes into the
    same queue the factory's own inventions go into and is judged by the identical deterministic
    path -- cheap screens, nulls, the gauntlet, the ten gates. There is no shortcut, no priority
    lane, and no bar that moves because a model suggested something.
  * EVERY PROPOSAL IS CHARGED. A prior that costs no trials is a free lunch, and a free lunch in
    a multiple-testing budget is a lie told to every other hypothesis. Proposals are priced
    through `libs.research.trial_ledger` exactly as machine-generated cells are, so a seat that
    floods the population pays for the flood.
  * INVALID IS DISCARDED WITH A REASON. A proposal that does not parse in the factory's grammar,
    or that the factory's own validator rejects, is dropped and the reason is counted. The desk
    learns what fraction of a model's output is usable instead of assuming it.
  * IT IS OPTIONAL. When no panel resolves, `enabled()` is False, every entry point returns
    nothing, every factory runs EXACTLY as it does today, and the report says UNMEASURED. A dark
    seat is a measurement, never an error and never a crash in a scheduled organ (L1.28a).

PROMPT HYGIENE IS ENFORCED, NOT INTENDED. `build_prompt` is the only function that composes text
for a model, it accepts whitelisted fields only, and every composed prompt is scanned against
`FORBIDDEN_PROMPT_TOKENS` (the sealed lockbox, any held-out slice, PIT-future language, and every
spelling of a credential) plus the live key material of every resolved seat. A prompt that trips
the scan is REFUSED -- the proposal is never requested rather than being requested and filtered.

ROUTING IS NOT DUPLICATED HERE. `libs.ops.llm_seat` resolves the seat, discovers the flagship,
enforces the free-tier request budget and records spend; `libs.research.free_panel` rotates the
zero-cost roster on a rate limit; `libs.ops.llm_route` reports what the roster can reach. This
module composes a prompt, calls one of those, and parses the reply. It owns no transport.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
REPORT = DESK / "reports" / "PROPOSER_SEAT.json"
#: Where a proposal waits for the factory that will judge it. One file per factory, append-only
#: within a pass and drained by the factory -- a factory that never runs simply never drains, and
#: nothing is lost or silently re-proposed.
QUEUE_DIR = DESK / "data" / "proposer_seat"
NAMING_QUEUE = DESK / "data" / "hypotheses" / "mechanism_naming_queue.json"

UNMEASURED = "UNMEASURED"
SEAT_NAME = "proposer_seat"

#: The factories this seat may propose into. A name absent from here is refused: a proposal with
#: nowhere deterministic to be judged is not a candidate, it is a suggestion.
FACTORIES: tuple[str, ...] = (
    "expression_factory", "math_lab", "physics_lab", "factor_model_coevolution",
    "model_search", "mechanism_naming_queue",
)

#: EVERY RESEARCH PROCESS THAT CAN CONSUME A PROPOSAL (principal 2026-09-23, widening the seat
#: from the four factories: "the proposer seat should be for all miners, crawlers etc, all
#: research processes there, not just factories -- rather everything, even sandboxed").
#:
#: organ -> what a proposal MEANS to it, in one line. The registry exists so that "is the seat
#: everywhere?" is answerable by MEASUREMENT: `run()` reports every name here with its counts,
#: and an organ that has never called reads UNMEASURED rather than being invisible. Adding an
#: organ is one line here plus one `ask(...)` call -- which is the whole point of having a
#: single entry point instead of five copies of a routing block.
ORGANS: dict[str, str] = {
    "expression_factory": "expression skeletons in alpha_grammar, drained into the invention "
                          "stage and screened like any other invention",
    "math_lab": "candidate mechanism names for objects no tradition could interpret",
    "physics_lab": "candidate mechanism names for uninterpreted MathHypothesisCards",
    "factor_model_coevolution": "an ORDER over the measured-healthy model zoo",
    "model_search": "an ORDER over the registered model families",
    "mechanism_naming_queue": "candidate causes for measured effects with no named mechanism",
    "forest_runner": "native-script query terms for a forest's own source scouts",
    "seed_miners": "query terms and source NAMES for the miner fleet to look up in its registry",
    "world_crawler": "what to look for next, and which neighbourhoods are worth expanding",
    "deep_forest_miner": "which forest neighbourhoods and practitioner vocabularies to expand",
    "sandbox_runner": "which system to run against which data, and what to extract from it",
    "archaeology": "mechanism names for relations the dig found",
    "understanding_seat": "candidate explanations for what the desk has measured and not named",
    "residual_hunt": "what might explain a world-model residual",
    "data_acquisition_scientist": "which dataset to seek next, by NAME, for the registry to vet",
    "meta_controller": "an ORDER over the curriculum the controller already holds",
    "standing_questions": "candidate phrasings of the questions the desk has not answered",
}

#: What an `ask` may ask for. Four kinds, and the difference between them is what the organ is
#: allowed to do with the answer -- which is the whole safety argument:
#:
#:   order       reorder the organ's OWN option list. Never adds, never removes.
#:   names       a candidate cause for something already measured. Never a status, never a gate.
#:   terms       new SEARCH STRINGS (a query, a vocabulary item, a dataset name). Additive, and
#:               therefore the one that needs a rule: a term is not a permission. The organ's own
#:               source registry and legality router still decide what may be fetched, so a
#:               proposed term can never become a new ground by being named -- `_valid_term`
#:               refuses anything shaped like a URL or a host for exactly that reason.
#:   candidates  free-form JSON in the ORGAN'S own grammar, validated by the organ's own callable.
KINDS: tuple[str, ...] = ("order", "names", "terms", "candidates")

#: THE KILL LIST. Any of these keys in a model's reply is a VERDICT, and a verdict is the one
#: thing this seat may never produce. They are stripped rather than rejected: the model is
#: competent at shape and at naming, incompetent at judging, and throwing away the shape because
#: it arrived with an unasked-for number would waste the only part worth having.
VERDICT_KEYS: frozenset[str] = frozenset({
    "score", "sharpe", "sortino", "calmar", "p_value", "pvalue", "p", "t_stat", "tstat", "t",
    "significance", "confidence", "verdict", "promote", "promotion", "certificate", "certified",
    "passed", "pass", "fail", "failed", "rank", "ranking", "expected_return", "expected_sharpe",
    "edge", "pnl", "profit", "win_rate", "winrate", "accuracy", "ic", "information_ratio",
    "decision", "approve", "approved", "reject", "rejected", "recommendation", "recommend",
    "weight", "size", "allocation", "capital", "leverage", "priority", "conviction",
    "probability", "prob", "odds", "backtest", "returns", "drawdown", "cagr",
})

#: A verdict stated in PROSE rather than as a field. Matched on the free-text parts of a reply
#: (a claim, a mechanism name) so a mechanism called "sharpe 3.1 momentum edge" is discarded
#: instead of carrying a number into the population under a name.
_VERDICT_PROSE = re.compile(
    r"\b(sharpe|t[-_ ]?stat|p[-_ ]?value|win[-_ ]?rate|cagr|drawdown|annual(?:ised|ized)?"
    r"[-_ ]returns?|expected[-_ ]returns?|profit[-_ ]factor)\b", re.I)

#: NEVER IN A PROMPT. The first three are the sealed evidence the desk's whole validity rests on
#: -- a model that has seen the lockbox can propose the answer back and every gate downstream
#: becomes theatre. The rest are credentials, which never leave the box in any direction.
FORBIDDEN_PROMPT_TOKENS: tuple[str, ...] = (
    "lockbox", "locked_holdout", "lockedholdout", "sealed slice", "sealed_slice",
    "holdout", "hold-out", "out_of_sample_tail", "oos_tail",
    "pit_future", "point_in_time_future", "future bar", "future_bar", "future_return",
    "look-ahead", "lookahead", "unreleased", "not yet published",
    "data/secrets", "data\\secrets", "llm_panel.json", "api_key", "api key", "apikey",
    "secret_key", "private_key", "password", "bearer ", "authorization:",
)

#: A credential by SHAPE rather than by name. A bare "sk-" cannot be a forbidden token: `risk-`
#: contains it, and `risk` is a declared grammar terminal -- a substring rule there would refuse
#: every expression prompt the desk ever built and the seat would look dark for a reason nobody
#: could find.
_KEYLIKE = re.compile(r"\b(?:sk|hf|xai|gsk|ghp|glpat)[-_][A-Za-z0-9_-]{16,}")


class PromptRefused(ValueError):
    """A composed prompt tripped the hygiene scan. Raised, never logged and sent anyway."""


# ------------------------------------------------------------------------------ the proposal
@dataclass(frozen=True)
class Provenance:
    """Who proposed this, with what, when. Carried onto every candidate that enters a population.

    A candidate whose origin cannot be reconstructed is a candidate whose SOURCE cannot be
    credited or blamed, and the desk's whole credit-assignment machinery is source-keyed.
    """

    seat: str
    model: str
    prompt_sha256: str
    utc: str
    role: str
    factory: str

    def to_row(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class Proposal:
    """One candidate from the seat. NOTE WHAT IS NOT HERE: no score, no rank, no verdict field.

    The absence is the invariant. `tests/research/test_proposer_seat.py` asserts that this
    dataclass carries no field whose name is in `VERDICT_KEYS`, so a later edit that adds one
    fails the suite rather than quietly creating a seat that judges.
    """

    kind: str                       #: skeleton | mechanism_name | order_hint | law
    factory: str
    payload: Any                    #: grammar-shaped JSON for a skeleton; a string for a name
    provenance: Provenance
    accepted: bool = False
    reason: str = ""                #: why it was discarded, empty when accepted
    stripped: tuple[str, ...] = ()  #: verdict fields deleted from the model's reply
    context: dict[str, str] = field(default_factory=dict)

    def to_row(self) -> dict[str, Any]:
        row = asdict(self)
        row["provenance"] = self.provenance.to_row()
        row["stripped"] = list(self.stripped)
        return row


# ------------------------------------------------------------------------------ availability
def _seat_module() -> Any:
    try:
        from libs.ops import llm_seat
    except Exception:                                    # pragma: no cover - import guard
        return None
    return llm_seat


def _panel_module() -> Any:
    try:
        from libs.research import free_panel
    except Exception:                                    # pragma: no cover - import guard
        return None
    return free_panel


def _route_module() -> Any:
    try:
        from libs.ops import llm_route
    except Exception:                                    # pragma: no cover - import guard
        return None
    return llm_route


def enabled() -> bool:
    """True when a panel resolves AND the seat is not switched off.

    CHEAP AND OFFLINE. Every factory calls this on its hot path, so it reads the environment and
    the roster file and never touches the network. A seat that cost a round trip to ask "are you
    there" would be a seat every factory learned to stop asking.
    """
    if os.environ.get("QUANT_PROPOSER_SEAT", "1") == "0":
        return False
    seat = _seat_module()
    if seat is None:
        return False
    try:
        return bool(seat.seats())
    except Exception:                                    # pragma: no cover - defensive
        return False


def seat_status() -> dict[str, Any]:
    """What the seat can reach, WITHOUT printing a key and without a network call.

    UNMEASURED when dark: an absent panel is a state of the box, not a failure of this organ,
    and reporting it as an error would teach every reader to ignore the report (L1.28a).
    """
    seat, route = _seat_module(), _route_module()
    out: dict[str, Any] = {"seat": SEAT_NAME, "enabled": enabled(),
                           "switched_off": os.environ.get("QUANT_PROPOSER_SEAT", "1") == "0"}
    if seat is None:
        out.update({"verdict": UNMEASURED, "why": "libs.ops.llm_seat did not import"})
        return out
    try:
        resolved = seat.seats()
    except Exception as exc:                             # pragma: no cover - defensive
        out.update({"verdict": UNMEASURED, "why": f"{type(exc).__name__}: {exc}"})
        return out
    out["n_seats"] = len(resolved)
    out["sources"] = sorted({s.source for s in resolved})
    if route is not None:
        try:
            out["roster_seats"] = len(route.load_seats(seat.SECRETS))
        except Exception:                                # pragma: no cover - defensive
            out["roster_seats"] = None
    out["free_tier_only"] = bool(getattr(seat, "free_tier_only", lambda: True)())
    if not resolved:
        out.update({"verdict": UNMEASURED,
                    "why": ("no LLM seat resolves on this box: every factory runs exactly as it "
                            "does without this seat, which is the designed absent path and not "
                            "a defect. Export OPENROUTER_API_KEY or write "
                            "data/secrets/llm_panel.json to light it.")})
        return out
    out["verdict"] = "AVAILABLE"
    return out


# ------------------------------------------------------------------------------ prompt hygiene
def _live_key_fragments() -> list[str]:
    """Fragments of every resolved key, so a prompt can be checked for carrying one.

    Never returned to a caller and never logged -- only compared against inside `scrub`.
    """
    seat = _seat_module()
    if seat is None:
        return []
    frags: list[str] = []
    try:
        for s in seat.seats():
            k = str(getattr(s, "key", "") or "")
            if len(k) >= 8:
                frags.append(k)
    except Exception:                                    # pragma: no cover - defensive
        return []
    return frags


def scrub(text: str) -> str:
    """Return `text` unchanged, or raise PromptRefused naming the token that must not be sent.

    RAISED RATHER THAN FILTERED. Filtering would send a prompt that was ALMOST a leak, built by
    code that believed it was allowed to reference the sealed slice; the bug is upstream and a
    silent repair hides it. A refusal is loud, local, and caught by the caller as a discard.
    """
    low = text.lower()
    for tok in FORBIDDEN_PROMPT_TOKENS:
        if tok in low:
            raise PromptRefused(
                f"prompt contains {tok!r}: no sealed holdout, no PIT-future datum and no "
                f"credential may ever reach an external model")
    m = _KEYLIKE.search(text)
    if m:
        raise PromptRefused("prompt carries a credential-shaped token")
    for frag in _live_key_fragments():
        if frag in text:
            raise PromptRefused("prompt carries live key material")
    return text


def prompt_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def build_prompt(factory: str, task: str, *, grammar: str, context: Sequence[str],
                 n: int) -> str:
    """The ONLY composer of model-facing text. Whitelisted fields, then the hygiene scan.

    `context` is a sequence of SHORT descriptive strings the caller has already decided are
    public -- a symbol name, an operator census, an unnamed effect's feature label. Nothing here
    reads a file, so there is no path by which a sealed slice or a secret can arrive by accident:
    a leak would have to be handed in by the caller, and `scrub` then refuses it.
    """
    if factory not in ORGANS:
        raise PromptRefused(f"unknown organ {factory!r}; nothing would judge its proposals")
    lines = [
        f"You are proposing CANDIDATES for the {factory} of a quantitative research desk.",
        "",
        "HARD RULES:",
        "  * Propose SHAPES and NAMES only. Never a score, a p-value, a t-statistic, an "
        "expected return, a win rate, a ranking, or any judgement of quality.",
        "  * Every proposal you make will be tested by a deterministic pipeline that ignores "
        "your opinion of it. Confidence language is discarded; only the shape survives.",
        "  * Stay inside the grammar below. Anything outside it is discarded unparsed.",
        "",
        "GRAMMAR:", grammar, "",
        "TASK:", task, "",
    ]
    if context:
        lines += ["CONTEXT (public facts about the search, nothing held out):",
                  *[f"  - {c}" for c in context[:40]], ""]
    lines += [f"Return at most {int(n)} proposal(s), one JSON object per line, no prose, "
              "no markdown fence."]
    return scrub("\n".join(lines))


# ------------------------------------------------------------------------------ verdict stripping
def strip_verdicts(obj: Any) -> tuple[Any, tuple[str, ...]]:
    """Remove every verdict-shaped key, recursively. Returns (clean, names removed).

    THE POINT IS NOT TIDINESS. A number that travels beside a candidate gets read as evidence by
    the next reader, and this desk has already paid for a threshold that sat next to results and
    started being treated as a bar. The strip is recorded so the rate is visible.
    """
    removed: list[str] = []

    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            out: dict[str, Any] = {}
            for k, v in node.items():
                if str(k).strip().lower() in VERDICT_KEYS:
                    removed.append(str(k))
                    continue
                out[str(k)] = walk(v)
            return out
        if isinstance(node, list):
            return [walk(v) for v in node]
        return node

    clean = walk(obj)
    return clean, tuple(sorted(set(removed)))


def verdict_leak(obj: Any) -> str:
    """The verdict this object still carries after stripping, or "" when it carries none.

    Belt AND braces: `strip_verdicts` removes verdict FIELDS; this catches a verdict asserted in
    PROSE inside a value that survived -- a mechanism name of "sharpe 3.1 carry" would otherwise
    walk a number into the population under a label.
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).strip().lower() in VERDICT_KEYS:
                return f"verdict field {k!r}"
            leak = verdict_leak(v)
            if leak:
                return leak
        return ""
    if isinstance(obj, list):
        for v in obj:
            leak = verdict_leak(v)
            if leak:
                return leak
        return ""
    if isinstance(obj, str):
        m = _VERDICT_PROSE.search(obj)
        return f"verdict prose {m.group(0)!r}" if m else ""
    return ""


# ------------------------------------------------------------------------------ the call
def _ask(role: str, prompt: str, *, timeout: float) -> tuple[str, str, str | None]:
    """One completion. Returns (text, model, error). NEVER raises -- a scheduled organ survives it.

    THE FREE PANEL FIRST, THE SEAT SECOND, AND NEITHER IS REIMPLEMENTED HERE. `free_panel.ask`
    rotates a zero-cost roster on rate limits, which is what an hourly cadence wants;
    `llm_seat.chat` resolves and discovers a flagship under the request/spend caps and is the
    route that exists when the free roster is exhausted. Both already encode policies -- the
    monthly cap, the daily free-request budget, the observed ceiling -- that a third transport
    here would drift from on exactly the properties that must not drift.
    """
    panel = _panel_module()
    if panel is not None:
        try:
            reply = panel.ask(role, "Propose candidates. Shapes and names only.", prompt,
                              max_tokens=1600, temperature=0.9)
            text = str(getattr(reply, "text", "") or "")
            if text.strip():
                return text, str(getattr(reply, "model", "") or "free_panel"), None
        except Exception as exc:                          # includes PanelExhausted
            last = f"free_panel: {type(exc).__name__}: {str(exc)[:160]}"
        else:
            last = "free_panel: empty completion"
    else:
        last = "free_panel: unimportable"
    seat = _seat_module()
    if seat is None:
        return "", "", last
    try:
        text, err = seat.chat(prompt, system="Propose candidates. Shapes and names only.",
                              max_tokens=1600, timeout=timeout, temperature=0.8)
    except Exception as exc:                              # pragma: no cover - defensive
        return "", "", f"{last}; llm_seat: {type(exc).__name__}: {str(exc)[:160]}"
    if err:
        return "", "", f"{last}; llm_seat: {err[:200]}"
    model = ""
    try:
        s = seat.primary_seat()
        model = str(getattr(s, "model", "") or getattr(s, "name", "") or "")
    except Exception:                                     # pragma: no cover - defensive
        model = ""
    return text, model or "llm_seat", None


def _rows(text: str, limit: int) -> list[Any]:
    """Every JSON object the reply contains, one per line, junk skipped silently.

    Models fence, preamble, and number their lists. Parsing line by line and dropping what does
    not parse costs nothing and turns a formatting habit into zero lost proposals instead of a
    whole call lost to a stray backtick.
    """
    out: list[Any] = []
    for raw in text.splitlines():
        line = raw.strip().strip("`").strip()
        if line.startswith(("-", "*")):
            line = line[1:].strip()
        line = re.sub(r"^\d+[.)]\s*", "", line)
        if not line.startswith(("{", "[")):
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
        if len(out) >= limit:
            break
    return out


# ------------------------------------------------------------------------------ the proposals
def propose(factory: str, *, role: str, task: str, grammar: str,
            context: Sequence[str] = (), n: int = 6, kind: str = "skeleton",
            extract: Callable[[Any], Any] | None = None,
            validate: Callable[[Any], str | None] | None = None,
            timeout: float = 120.0) -> list[Proposal]:
    """Ask for `n` candidates of `kind` and return them JUDGED ONLY FOR VALIDITY.

    `extract` pulls the payload out of one parsed row (default: the row itself); `validate`
    is the FACTORY'S OWN rule -- it returns a discard reason or None, and it is the only thing
    that decides whether a proposal is usable. This module does not know any factory's grammar
    and deliberately never will: a validator living here would rot the day a factory's grammar
    moved, and it would rot silently by accepting shapes the factory no longer builds.

    Returns [] when the seat is dark. That is the designed absent path: a caller wraps this in
    nothing and simply gets no proposals, exactly as it did before the seat existed.
    """
    if not enabled():
        return []
    try:
        prompt = build_prompt(factory, task, grammar=grammar, context=context, n=n)
    except PromptRefused as exc:
        prov = Provenance(SEAT_NAME, "", "", datetime.now(UTC).isoformat(timespec="seconds"),
                          role, factory)
        return [Proposal(kind=kind, factory=factory, payload=None, provenance=prov,
                         accepted=False, reason=f"prompt refused: {exc}")]
    text, model, err = _ask(role, prompt, timeout=timeout)
    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    prov = Provenance(SEAT_NAME, model, prompt_hash(prompt), stamp, role, factory)
    if err or not text.strip():
        return [Proposal(kind=kind, factory=factory, payload=None, provenance=prov,
                         accepted=False,
                         reason=f"no reply: {err or 'empty completion'}"[:300])]
    out: list[Proposal] = []
    for row in _rows(text, limit=max(1, int(n))):
        clean, removed = strip_verdicts(row)
        payload = extract(clean) if extract else clean
        leak = verdict_leak(payload)
        if leak:
            out.append(Proposal(kind, factory, payload, prov, False,
                                f"discarded: {leak} -- this seat may not produce verdicts",
                                removed))
            continue
        if payload in (None, "", [], {}):
            out.append(Proposal(kind, factory, payload, prov, False,
                                "discarded: empty payload after stripping", removed))
            continue
        reason = validate(payload) if validate else None
        out.append(Proposal(kind, factory, payload, prov, reason is None,
                            "" if reason is None else f"discarded: {reason}", removed))
    if not out:
        out.append(Proposal(kind, factory, None, prov, False,
                            "discarded: reply held no parseable JSON row", ()))
    return out


def charge_trials(proposals: Sequence[Proposal]) -> float:
    """Effective trials this batch costs, through the desk's ONE pricing library.

    ACCEPTED PROPOSALS ONLY. A discarded proposal consumed no evaluation, so charging it would
    inflate the denominator with work nobody did -- and an inflated denominator is a bar every
    other hypothesis has to clear for nothing. A seat that proposes ten near-identical skeletons
    is priced as far less than ten by `trial_ledger`'s similarity census, which is exactly the
    property that makes a generative prior affordable.
    """
    rows = [{"trial_id": f"{p.factory}:{prompt_key(p)}", "family": f"seat/{p.factory}",
             "method": p.kind, "mechanism": str(p.context.get("mechanism", "")),
             "symbol": str(p.context.get("symbol", "")),
             "params": {"payload": json.dumps(p.payload, sort_keys=True, default=str)[:400]}}
            for p in proposals if p.accepted]
    if not rows:
        return 0.0
    try:
        from libs.research import trial_ledger as tl
        return round(float(tl.effective_count_of_records(rows)), 4)
    except Exception:                                     # pragma: no cover - defensive
        return float(len(rows))


def prompt_key(p: Proposal) -> str:
    return hashlib.sha256(
        json.dumps(p.payload, sort_keys=True, default=str).encode()).hexdigest()[:12]


# ------------------------------------------------------------------------------ the queue
def _queue_path(factory: str) -> Path:
    return QUEUE_DIR / f"{factory}.json"


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _atomic(path: Path, doc: Any) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        pass                     # a queue write must never take down the organ that made it


def enqueue(proposals: Sequence[Proposal], *, cap: int = 400) -> int:
    """Park the ACCEPTED proposals where their factory will drain them. Returns how many landed.

    Only accepted ones are parked: a discarded proposal has a recorded reason in the report and
    no business sitting in a population's inbox.
    """
    by_factory: dict[str, list[Proposal]] = {}
    for p in proposals:
        if p.accepted:
            by_factory.setdefault(p.factory, []).append(p)
    landed = 0
    for factory, rows in by_factory.items():
        path = _queue_path(factory)
        have = _read_json(path, [])
        have = have if isinstance(have, list) else []
        seen = {json.dumps(r.get("payload"), sort_keys=True, default=str) for r in have
                if isinstance(r, dict)}
        for p in rows:
            key = json.dumps(p.payload, sort_keys=True, default=str)
            if key in seen:
                continue
            have.append(p.to_row())
            seen.add(key)
            landed += 1
        _atomic(path, have[-cap:])
    return landed


def take(factory: str, *, limit: int = 1) -> list[dict[str, Any]]:
    """Drain up to `limit` parked proposals for this factory. [] when there are none or it is off.

    DRAINED, NOT READ. A proposal handed to a factory has entered the population and must not be
    handed to the next pass as well -- a prior that keeps re-proposing the same skeleton charges
    the same trial forever and looks like a productive seat while testing one idea.
    """
    if os.environ.get("QUANT_PROPOSER_SEAT", "1") == "0":
        return []
    path = _queue_path(factory)
    have = _read_json(path, [])
    if not isinstance(have, list) or not have:
        return []
    taken = [r for r in have[:max(1, int(limit))] if isinstance(r, dict)]
    _atomic(path, have[len(taken):])
    return taken


def queue_depth() -> dict[str, int]:
    out: dict[str, int] = {}
    for factory in FACTORIES:
        have = _read_json(_queue_path(factory), [])
        out[factory] = len(have) if isinstance(have, list) else 0
    return out


# ------------------------------------------------------------------------------ order hints
def order_hint(factory: str, options: Sequence[str], *, question: str,
               timeout: float = 90.0) -> tuple[list[str], dict[str, Any]]:
    """Reorder a factory's OWN option list by the seat's priority. Never adds, never removes.

    THIS IS THE WEAKEST THING A PRIOR CAN DO AND THAT IS WHY IT IS SAFE. The option set is the
    factory's; every option is still searched; only the ORDER changes, which matters solely when
    a budget truncates the sweep. A name the model invents is not in the set, so it is discarded
    with a reason -- the seat cannot smuggle an unregistered model family or representation into
    a search by naming it.
    """
    opts = [str(o) for o in options]
    if not enabled() or not opts:
        return opts, {"verdict": UNMEASURED if not enabled() else "EMPTY",
                      "why": "seat dark" if not enabled() else "no options to order"}
    grammar = ("A JSON array of strings, each EXACTLY one of: " + ", ".join(sorted(opts)) +
               ". No other values. No commentary.")
    props = propose(factory, role="classify", task=question, grammar=grammar,
                    context=[f"option: {o}" for o in opts], n=1, kind="order_hint",
                    validate=lambda p: None if isinstance(p, list) and p else
                    "not a non-empty JSON array", timeout=timeout)
    if props:
        _log_inline(factory, props)
    accepted = [p for p in props if p.accepted]
    if not accepted:
        return opts, {"verdict": "NO_HINT",
                      "why": (props[0].reason if props else "no proposal"),
                      "proposals": [p.to_row() for p in props]}
    wanted = [str(x) for x in accepted[0].payload if isinstance(x, (str, int, float))]
    known = [w for w in wanted if w in opts]
    unknown = [w for w in wanted if w not in opts]
    ordered = known + [o for o in opts if o not in known]
    return ordered, {"verdict": "ORDERED", "hint": known, "discarded_unknown": unknown,
                     "trials_charged": charge_trials(props),
                     "discarded": sum(1 for p in props if not p.accepted),
                     "reasons": _reasons(props),
                     "why": ("names outside the factory's own option set are discarded: a seat "
                             "may reorder a search, never widen it"),
                     "proposals": [p.to_row() for p in props]}


# ------------------------------------------------------------------------------ mechanism names
def name_mechanisms(factory: str, effects: Sequence[dict[str, Any]], *, n: int = 6,
                    timeout: float = 120.0) -> list[Proposal]:
    """Candidate mechanism NAMES for relations the factory already found.

    A NAME IS NOT A NAMING. The desk's rule is that an unnamed measured effect may not trade;
    that rule is satisfied by a named cause WITH EVIDENCE, judged by the same gates. What this
    returns is a hypothesis about the cause, to be tested -- which is why the payload carries no
    number and why `verdict_leak` refuses one that does.
    """
    if not effects:
        return []
    grammar = ('{"key": "<the effect key given>", "mechanism": "<short economic cause, '
               '<=120 chars>", "falsifier": "<what observation would refute it>"}')
    context = []
    for e in effects[:40]:
        bits = [f"{k}={e.get(k)}" for k in ("key", "symbol", "feature", "band", "horizon",
                                            "side", "claim", "target", "tradition")
                if e.get(k) not in (None, "")]
        if bits:
            context.append("; ".join(str(b) for b in bits))
    task = ("Name the economic mechanism that would cause each measured relation below, and "
            "state what observation would refute it. If you cannot name a cause for one, omit "
            "it -- an omission is worth more than a guess dressed as a cause.")
    return propose(factory, role="mechanism", task=task, grammar=grammar, context=context,
                   n=max(1, int(n)), kind="mechanism_name",
                   validate=_valid_mechanism, timeout=timeout)


#: Where a factory that calls the seat INLINE (on its own clock, mid-pass) records what it asked
#: for. The leg's own report folds this in, so `PROPOSER_SEAT.json` carries every factory's
#: proposals whether they came from the parked queue or from a live call inside the factory.
INLINE_LOG = QUEUE_DIR / "inline_passes.jsonl"


def _log_inline(factory: str, props: Sequence[Proposal]) -> None:
    row = {"utc": datetime.now(UTC).isoformat(timespec="seconds"), "factory": factory,
           "requested": len(props), "accepted": sum(1 for p in props if p.accepted),
           "discarded": sum(1 for p in props if not p.accepted),
           "trials_charged": charge_trials(props),
           "reasons": sorted({p.reason[:120] for p in props if p.reason})[:6]}
    try:
        INLINE_LOG.parent.mkdir(parents=True, exist_ok=True)
        with INLINE_LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=str) + "\n")
    except OSError:
        pass                    # a log write must never take down the factory that made it


def names_for(factory: str, records: Sequence[dict[str, Any]], *, n: int = 6
              ) -> dict[str, dict[str, Any]]:
    """{key: {mechanism, falsifier, by}} for the records the seat could name. {} when dark.

    THE FACTORY'S OWN CALL SITE. A lab holds objects whose interpretation status is already
    `uninterpreted`; this hands those to the seat and hands back candidate causes keyed by
    whatever the caller used as `key`. The caller attaches them AS PROPOSALS -- the desk's rule
    that an unnamed effect may not trade is satisfied by evidence, never by a label, so nothing
    here may set an interpretation status or clear a gate.
    """
    if not records:
        return {}
    props = name_mechanisms(factory, records, n=n)
    if props:
        _log_inline(factory, props)
    out: dict[str, dict[str, Any]] = {}
    for p in props:
        if not (p.accepted and isinstance(p.payload, dict)):
            continue
        out[str(p.payload.get("key"))] = {
            "mechanism": str(p.payload.get("mechanism")),
            "falsifier": str(p.payload.get("falsifier")),
            "by": p.provenance.to_row(),
            "discipline": ("a CANDIDATE cause to be tested by the same gates; it is not an "
                           "interpretation, not evidence, and clears nothing"),
        }
    return out


# --------------------------------------------------------------------- THE SHARED ENTRY POINT
@dataclass(frozen=True)
class SeatReply:
    """What one `ask` returned. Every field has a NEUTRAL value, and that is the design.

    A consumer writes `reply = ask(...)` and then uses `reply.ordered` / `reply.names` /
    `reply.terms` / `reply.items` unconditionally. When the seat is dark every one of those is
    exactly what the organ would have used anyway -- the option list it passed in, and nothing
    else -- so the absent path needs no branch at the call site and therefore cannot be got
    wrong by the next organ to be wired.

    NOTE WHAT IS NOT HERE, again: no score, no rank, no confidence, no verdict. `trials_charged`
    is a COST, not a judgement.
    """

    organ: str
    kind: str
    verdict: str
    ordered: list[str] = field(default_factory=list)
    names: dict[str, dict[str, Any]] = field(default_factory=dict)
    terms: list[str] = field(default_factory=list)
    items: list[Any] = field(default_factory=list)
    trials_charged: float = 0.0
    discarded: int = 0
    reasons: list[str] = field(default_factory=list)
    why: str = ""

    @property
    def measured(self) -> bool:
        return self.verdict == "RAN"

    def to_row(self) -> dict[str, Any]:
        row = asdict(self)
        row["measured"] = self.measured
        return row


def ask(organ: str, kind: str, *, options: Sequence[str] = (),
        records: Sequence[dict[str, Any]] = (), task: str = "", grammar: str = "",
        context: Sequence[str] = (), n: int = 6,
        validate: Callable[[Any], str | None] | None = None,
        timeout: float = 120.0) -> SeatReply:
    """THE ONE CALL. Any research process gets the proposer seat by calling this and nothing else.

    WHY ONE FUNCTION AND NOT A PATTERN TO COPY. The seat is meant to reach every miner, crawler,
    sandbox, dig and controller on this desk, and the desk has already paid for the alternative:
    `llm_route`'s own docstring records eleven organs that each resolved a model their own way,
    of which one was dead for weeks with no artifact and no complaint. A prior that is wired by
    copy-paste is a prior that is wired eleven slightly different ways, and the differences will
    all be in the guard.

    So the guard lives here, once: an unknown organ, a dark panel, a refused prompt, an
    unparseable reply and an invalid proposal all return a SeatReply whose fields are the neutral
    values the caller already had. A consumer needs no try/except of its own for correctness --
    it keeps one only because an import of this module must not be able to break it either.

    Every ask is logged to the inline census, so `run()` can report which organs actually used
    the seat and how much they charged. An organ registered in ORGANS that never appears in that
    census reads UNMEASURED, which is the honest answer to "is it wired?" when nothing ran.
    """
    opts = [str(o) for o in options]
    if kind not in KINDS:
        return SeatReply(organ, kind, UNMEASURED, ordered=opts,
                         why=f"unknown kind {kind!r}; expected one of {KINDS}")
    if organ not in ORGANS:
        return SeatReply(organ, kind, UNMEASURED, ordered=opts,
                         why=(f"{organ!r} is not in ORGANS. Register it with one line saying "
                              "what a proposal MEANS to it, so the artifact can report it"))
    if not enabled():
        return SeatReply(organ, kind, UNMEASURED, ordered=opts,
                         why=("no panel resolves on this host (or QUANT_PROPOSER_SEAT=0). The "
                              "organ runs exactly as it does without the seat"))

    if kind == "order":
        ordered, hint = order_hint(organ, opts, question=task or "Order these, best first.",
                                   timeout=timeout)
        return SeatReply(organ, kind, str(hint.get("verdict") or UNMEASURED), ordered=ordered,
                         items=list(hint.get("hint") or []),
                         trials_charged=float(hint.get("trials_charged") or 0.0),
                         discarded=int(hint.get("discarded") or 0),
                         reasons=list(hint.get("reasons") or []),
                         why=str(hint.get("why") or ""))

    if kind == "names":
        got = names_for(organ, records, n=n)
        return SeatReply(organ, kind, "RAN" if got else UNMEASURED, ordered=opts, names=got,
                         trials_charged=float(len(got)),
                         why="" if got else "the seat named nothing this pass")

    if kind == "terms":
        props = _asked(organ, role="hunt",
                       task=task or "Propose search terms worth trying.",
                       grammar=grammar or (
                           '{"term": "<a query string or a source NAME, <=80 chars>", '
                           '"why": "<what you expect it to surface, <=120 chars>"}'),
                       context=context, n=n, label="term",
                       validate=validate or _valid_term, timeout=timeout)
        terms = [str(p.payload["term"]) for p in props
                 if p.accepted and isinstance(p.payload, dict)]
        return SeatReply(organ, kind, "RAN" if props else UNMEASURED, ordered=opts, terms=terms,
                         trials_charged=charge_trials(props),
                         discarded=sum(1 for p in props if not p.accepted),
                         reasons=_reasons(props),
                         why=("a term is a SEARCH STRING, never a permission: the organ's own "
                              "source registry and legality router still decide what may be "
                              "fetched"))

    props = _asked(organ, role="generation", task=task, grammar=grammar, context=context, n=n,
                   label="candidate", validate=validate, timeout=timeout)
    return SeatReply(organ, kind, "RAN" if props else UNMEASURED, ordered=opts,
                     items=[p.payload for p in props if p.accepted],
                     trials_charged=charge_trials(props),
                     discarded=sum(1 for p in props if not p.accepted),
                     reasons=_reasons(props))


def _asked(organ: str, *, role: str, task: str, grammar: str, context: Sequence[str], n: int,
           label: str, validate: Callable[[Any], str | None] | None,
           timeout: float) -> list[Proposal]:
    """propose(), logged to the inline census on the way past, so `run()` can report the organ."""
    props = propose(organ, role=role, task=task, grammar=grammar, context=context, n=n,
                    kind=label, validate=validate, timeout=timeout)
    if props:
        _log_inline(organ, props)
    return props


def _reasons(props: Sequence[Proposal]) -> list[str]:
    return sorted({p.reason[:140] for p in props if p.reason})[:6]


def _valid_term(payload: Any) -> str | None:
    """A proposed term is a STRING TO SEARCH FOR, and never an address to fetch.

    THE RULE THAT MATTERS. Terms are the one additive kind -- an order hint cannot widen a search
    and a mechanism name cannot open a door, but a term names something new. So a term that looks
    like a URL, a host or a path is refused outright: the desk's grounds live in its own source
    registry, which vets machine_use_allowed and the legality router before anything is fetched,
    and a model must not be able to route a crawler by typing an address into a field.
    """
    if not isinstance(payload, dict):
        return "not a JSON object"
    term = str(payload.get("term") or "").strip()
    if len(term) < 2:
        return "empty term"
    if len(term) > 120:
        return "term longer than 120 characters is a sentence, not a query"
    low = term.lower()
    if re.search(r"https?://|www\.|\.com|\.org|\.net|\.cn|\.ru|\.io|/", low):
        return ("looks like an address: a term is a search string, never a ground. New grounds "
                "are added to the source registry, which vets them")
    if any(tok in low for tok in FORBIDDEN_PROMPT_TOKENS):
        return "term names sealed data or a credential"
    return None


def _valid_mechanism(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return "not a JSON object"
    mech = str(payload.get("mechanism") or "").strip()
    if len(mech) < 12:
        return "mechanism shorter than 12 characters is a label, not a cause"
    if len(mech) > 400:
        return "mechanism longer than 400 characters is an essay, not a name"
    if not str(payload.get("key") or "").strip():
        return "no key: a name with nothing to attach to cannot be judged"
    if not str(payload.get("falsifier") or "").strip():
        return "no falsifier: a cause nothing could refute is not a claim"
    return None


# ------------------------------------------------------------------------------ the leg
def _naming_pass(n: int) -> tuple[list[Proposal], dict[str, Any]]:
    """Propose names for the desk's OWN unnamed-effect queue, and write them back as candidates.

    The queue is `edge_search`'s: measured out-of-sample effects with no named cause, which
    `scripts/convert_question_queues.py` already converts into research questions. A proposed
    name is parked on the row as `proposed_mechanism` with its provenance; `mechanism_status`
    is NOT touched, so nothing downstream reads the proposal as a naming.
    """
    rows = _read_json(NAMING_QUEUE, [])
    if not isinstance(rows, list) or not rows:
        return [], {"verdict": UNMEASURED, "why": f"{NAMING_QUEUE.name} absent or empty",
                    "open_rows": 0}
    open_rows = [r for r in rows if isinstance(r, dict) and not r.get("proposed_mechanism")]
    if not open_rows:
        return [], {"verdict": "CLEAR", "why": "every queued effect already carries a proposal",
                    "open_rows": 0, "total_rows": len(rows)}
    effects = []
    for r in open_rows[-n:]:
        key = "|".join(str(r.get(k, "")) for k in ("symbol", "feature", "band", "horizon",
                                                   "side"))
        effects.append({"key": key, "symbol": r.get("symbol"), "feature": r.get("feature"),
                        "band": r.get("band"), "horizon": r.get("horizon"),
                        "side": r.get("side")})
    props = name_mechanisms("mechanism_naming_queue", effects, n=len(effects))
    by_key = {str(p.payload.get("key")): p for p in props
              if p.accepted and isinstance(p.payload, dict)}
    written = 0
    for r in open_rows:
        key = "|".join(str(r.get(k, "")) for k in ("symbol", "feature", "band", "horizon",
                                                   "side"))
        p = by_key.get(key)
        if p is None:
            continue
        r["proposed_mechanism"] = str(p.payload.get("mechanism"))
        r["proposed_falsifier"] = str(p.payload.get("falsifier"))
        r["proposed_by"] = p.provenance.to_row()
        r["proposal_discipline"] = ("a CANDIDATE cause to be tested by the same ten gates, "
                                    "never a naming and never evidence")
        written += 1
    if written:
        _atomic(NAMING_QUEUE, rows)
    return props, {"verdict": "RAN", "open_rows": len(open_rows), "total_rows": len(rows),
                   "asked": len(effects), "written": written}


def _skeleton_pass(n: int) -> list[Proposal]:
    """Expression skeletons in the expression factory's own grammar, parked for it to drain.

    VALIDATED AGAINST `alpha_grammar` HERE, because that is the door the factory itself uses
    (`ag.is_valid`) -- a skeleton this module accepted and the factory then rejected would be a
    trial charged for nothing, every pass, invisibly.
    """
    try:
        from libs.research import alpha_grammar as ag
    except Exception:                                    # pragma: no cover - import guard
        return []
    ops = sorted(set(getattr(ag, "UNARY", ()) + getattr(ag, "WINDOWED", ()) +
                     getattr(ag, "BINARY", ())))
    windows = list(getattr(ag, "WINDOWS", (5, 12, 24, 48, 120, 240)))
    leaves = list(getattr(ag, "BAR_TERMINALS", ("close", "ret")))
    grammar = (
        f"A JSON expression tree. A leaf is one of these bar terminals: {', '.join(leaves)}. "
        "A node is a JSON array [op, child, ...args]. "
        f"Operators: {', '.join(ops)}. Windowed operators take an integer window from "
        f"{windows}. Depth at most 5. Example: [\"div\", [\"delta\", \"close\", 24], "
        "[\"std\", \"ret\", 120]]. Return {\"expr\": <tree>, \"idea\": \"<=80 chars\"}.")
    task = ("Propose expression skeletons whose SHAPE encodes a distinct market mechanism "
            "(trend persistence, mean reversion around a level, volatility normalisation, "
            "range position, asymmetry). Each must be structurally different from the others.")

    def valid(payload: Any) -> str | None:
        if not isinstance(payload, dict) or "expr" not in payload:
            return "no 'expr' key"
        expr = payload["expr"]
        try:
            ok = bool(ag.is_valid(expr))
        except Exception as exc:
            return f"grammar raised {type(exc).__name__}: {str(exc)[:80]}"
        if not ok:
            return "syntactically or dimensionally invalid in alpha_grammar"
        try:
            depth = int(ag.depth(expr))
        except Exception:
            depth = 0
        if depth > 5:
            return f"depth {depth} exceeds the tradeable depth of 5"
        return None

    return propose("expression_factory", role="generation", task=task, grammar=grammar,
                   context=[f"operators available: {len(ops)}",
                            f"windows available: {windows}"],
                   n=max(1, int(n)), kind="skeleton", validate=valid)


def run(*, budget_s: float = 300.0, max_proposals: int = 8) -> dict[str, Any]:
    """One pass: propose into the queues, charge the trials, publish what happened."""
    started = time.time()
    status = seat_status()
    doc: dict[str, Any] = {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "law": ("THE SEAT PROPOSES, THE DESK JUDGES. A proposal is a candidate with provenance "
                "and a charged trial; it is never a verdict, a score or a promotion, and it is "
                "judged by exactly the deterministic path every machine-generated candidate is."),
        "seat": status,
        "budget_s": float(budget_s),
        "factories": {},
    }
    if not status.get("enabled"):
        doc["verdict"] = UNMEASURED
        doc["why"] = str(status.get("why") or "seat switched off")
        doc["factories"] = {f: {"verdict": UNMEASURED, "requested": 0, "accepted": 0,
                                "discarded": 0, "trials_charged": 0.0} for f in FACTORIES}
        doc["organs"] = _organ_census({})
        doc["queue_depth"] = queue_depth()
        doc["seat_health"] = _seat_health()
        doc["seconds"] = round(time.time() - started, 2)
        _atomic(REPORT, doc)
        return doc

    all_props: list[Proposal] = []
    per: dict[str, dict[str, Any]] = {}

    skeletons = _skeleton_pass(max_proposals)
    all_props += skeletons
    per["expression_factory"] = _summarise(skeletons)

    if time.time() - started < budget_s:
        names, naming = _naming_pass(max_proposals)
        all_props += names
        per["mechanism_naming_queue"] = {**_summarise(names), "queue": naming}
    else:
        per["mechanism_naming_queue"] = {"verdict": "BUDGET", "requested": 0, "accepted": 0,
                                         "discarded": 0, "trials_charged": 0.0}

    inline = _inline_census()
    for factory in ("math_lab", "physics_lab", "factor_model_coevolution", "model_search"):
        row = inline.get(factory)
        per.setdefault(factory, row or {
            "verdict": UNMEASURED,
            "why": ("this factory calls the seat inline on its own clock (order_hint / "
                    "names_for) and has not called it since this log was last rotated -- an "
                    "absence of calls, not a failure of them"),
            "requested": 0, "accepted": 0, "discarded": 0, "trials_charged": 0.0})

    landed = enqueue(all_props)
    doc["factories"] = per
    doc["organs"] = _organ_census(inline, per)
    doc["queued_for_factories"] = landed
    doc["queue_depth"] = queue_depth()
    doc["trials_charged_total"] = charge_trials(all_props)
    doc["seat_health"] = _seat_health()
    doc["verdict"] = "RAN"
    doc["seconds"] = round(time.time() - started, 2)
    _atomic(REPORT, doc)
    return doc


def _organ_census(inline: dict[str, dict[str, Any]],
                  per: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """EVERY registered organ with its proposal counts -- which is how "is it everywhere?" is
    answered by measurement rather than by a claim.

    An organ that has never called the seat is listed with zeros and UNMEASURED. That is the
    honest state of a newly wired organ whose clock has not come round yet, and it is what makes
    a REGRESSION visible: an organ that used to appear and stops is a wiring that broke, not an
    organ that had nothing to say.
    """
    rows: dict[str, Any] = {}
    for organ, consumes in ORGANS.items():
        row = dict((per or {}).get(organ) or inline.get(organ) or {})
        rows[organ] = {
            "consumes": consumes,
            "verdict": str(row.get("verdict") or UNMEASURED),
            "requested": int(row.get("requested") or 0),
            "accepted": int(row.get("accepted") or 0),
            "discarded": int(row.get("discarded") or 0),
            "trials_charged": float(row.get("trials_charged") or 0.0),
            "last_utc": row.get("last_utc") or None,
        }
    wired = sum(1 for r in rows.values() if r["verdict"] != UNMEASURED)
    return {"n_registered": len(ORGANS), "n_with_proposals_this_window": wired,
            "rule": ("an organ is WIRED when it calls proposer_seat.ask(); it is MEASURED when "
                     "that call produced proposals. Zero is UNMEASURED, never a pass"),
            "by_organ": rows}


def _inline_census(limit: int = 500) -> dict[str, dict[str, Any]]:
    """What the INLINE call sites did, rolled up per factory from their append-only log."""
    out: dict[str, dict[str, Any]] = {}
    try:
        lines = INLINE_LOG.read_text("utf-8").splitlines()[-limit:]
    except (OSError, ValueError):
        return out
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        f = str(row.get("factory") or "")
        if f not in ORGANS:
            continue
        acc = out.setdefault(f, {"verdict": "RAN", "requested": 0, "accepted": 0,
                                 "discarded": 0, "trials_charged": 0.0, "calls": 0,
                                 "last_utc": "", "discard_reasons": []})
        acc["requested"] = int(acc["requested"]) + int(row.get("requested") or 0)
        acc["accepted"] = int(acc["accepted"]) + int(row.get("accepted") or 0)
        acc["discarded"] = int(acc["discarded"]) + int(row.get("discarded") or 0)
        acc["trials_charged"] = round(
            float(acc["trials_charged"]) + float(row.get("trials_charged") or 0.0), 4)
        acc["calls"] = int(acc["calls"]) + 1
        acc["last_utc"] = str(row.get("utc") or acc["last_utc"])
        reasons = acc["discard_reasons"]
        if isinstance(reasons, list):
            for r in row.get("reasons") or []:
                if r not in reasons and len(reasons) < 8:
                    reasons.append(r)
    return out


def _summarise(props: Sequence[Proposal]) -> dict[str, Any]:
    acc = [p for p in props if p.accepted]
    disc = [p for p in props if not p.accepted]
    reasons: dict[str, int] = {}
    for p in disc:
        reasons[p.reason[:120]] = reasons.get(p.reason[:120], 0) + 1
    return {"verdict": "RAN" if props else UNMEASURED,
            "requested": len(props), "accepted": len(acc), "discarded": len(disc),
            "discard_reasons": reasons,
            "trials_charged": charge_trials(props),
            "accepted_rows": [p.to_row() for p in acc[:12]]}


def _seat_health() -> dict[str, Any]:
    """The seat-health measurement, read from the checker that owns it.

    DELEGATED, NOT COPIED. `scripts/check_seat_health.py` is the fence the law gate runs; a
    second implementation of "is this seat donating" here would drift from it, and the first
    time they disagreed nobody would know which was right.
    """
    try:
        from scripts import check_seat_health as csh
    except Exception:
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "check_seat_health", ROOT / "scripts" / "check_seat_health.py")
            if spec is None or spec.loader is None:
                return {"verdict": UNMEASURED, "why": "check_seat_health.py not importable"}
            csh = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(csh)
        except Exception as exc:                          # pragma: no cover - defensive
            return {"verdict": UNMEASURED,
                    "why": f"check_seat_health unimportable: {type(exc).__name__}: {exc}"}
    try:
        doc = csh.audit()
    except Exception as exc:                              # pragma: no cover - defensive
        return {"verdict": UNMEASURED, "why": f"{type(exc).__name__}: {str(exc)[:160]}"}
    return {"verdict": doc.get("verdict", UNMEASURED), "census": doc.get("census", {}),
            "overdue": [r.get("seat") for r in doc.get("seats", [])
                        if r.get("verdict") == "OVERDUE"]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--once", action="store_true",
                    help="one pass and exit (the only mode; accepted for leg symmetry)")
    ap.add_argument("--budget-s", type=float, default=300.0)
    ap.add_argument("--max-proposals", type=int, default=8)
    args = ap.parse_args(argv)
    doc = run(budget_s=float(args.budget_s), max_proposals=int(args.max_proposals))
    print(f"proposer seat: {doc['verdict']}  seat={doc['seat'].get('n_seats', 0)} "
          f"queued={doc.get('queued_for_factories', 0)} "
          f"trials={doc.get('trials_charged_total', 0.0)}")
    organs = doc.get("organs") or {}
    print(f"  organs registered {organs.get('n_registered', 0)}, with proposals this window "
          f"{organs.get('n_with_proposals_this_window', 0)}")
    for name, row in sorted((organs.get("by_organ") or doc["factories"]).items()):
        print(f"  {name:28} {row.get('verdict')!s:10} "
              f"accepted {row.get('accepted', 0)}/{row.get('requested', 0)} "
              f"trials {row.get('trials_charged', 0.0)}")
    print(f"  -> {REPORT}")
    return 0


if __name__ == "__main__":                                # pragma: no cover
    raise SystemExit(main())
